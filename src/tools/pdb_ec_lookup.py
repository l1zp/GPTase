"""
PDB → EC Lookup Utility

Retrieves Enzyme Commission (EC) numbers associated with a given PDB ID using
the RCSB Protein Data Bank Data API. Provides robust request handling,
timeouts, simple rate limiting, input validation, and structured results.

Usage (sync):

    from src.tools.pdb_ec_lookup import get_ec_numbers_for_pdb_sync
    result = get_ec_numbers_for_pdb_sync("4FB7")
    print(result)

Usage (async):

    import asyncio
    from src.tools.pdb_ec_lookup import get_ec_numbers_for_pdb

    async def main():
        print(await get_ec_numbers_for_pdb("4FB7"))
    asyncio.run(main())

Returned structure:

    {
      "pdb_id": "4FB7",
      "ec_numbers": ["1.1.1.1"],
      "entities": {"4FB7_1": ["1.1.1.1"]},
      "source": "rcsb",
      "errors": []
    }

If no EC numbers are found, "ec_numbers" will be an empty list.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

# RCSB Data API endpoints
ENTRY_URL = "https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
ENTITY_URL = "https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id}/{entity_id}"

# Basic rate limiting (concurrent requests)
_SEMAPHORE = asyncio.Semaphore(4)


def validate_pdb_id(pdb_id: str) -> str:
    """Validate a PDB ID (typical 4-character alphanumeric code).

    Rules:
    - Length 4, alphanumeric
    - At least one letter among the last 3 characters to avoid false positives (e.g., years)
    - Normalize to uppercase

    Raises ValueError if invalid.
    """
    if not isinstance(pdb_id, str):
        raise ValueError("PDB ID must be a string")
    pid = pdb_id.strip().upper()
    if len(pid) != 4 or not pid.isalnum():
        raise ValueError("Invalid PDB ID format: must be 4 alphanumeric characters")
    if not any(ch.isalpha() for ch in pid[1:]):
        raise ValueError("Invalid PDB ID: last three characters must contain a letter")
    return pid


def _extract_ec_numbers_from_text(text: str) -> List[str]:
    """Extract EC numbers from arbitrary text using a strict pattern.

    Matches canonical EC formats like "1.1.1.1" or partials with hyphens like "1.1.-.-".
    """
    # Canonical EC number: a.b.c.d where each is digits or '-'
    pattern = r"\b\d+\.\d+\.(\d+|-)\.(\d+|-)\b"
    found = re.findall(pattern, text)  # returns only groups; we need full match
    # Use finditer to capture full match strings
    return sorted({m.group(0) for m in re.finditer(pattern, text)})


def _walk_and_collect_ec(json_obj: Any) -> Set[str]:
    """Walk a JSON object to collect EC numbers appearing as strings."""
    ec: Set[str] = set()
    if isinstance(json_obj, dict):
        for v in json_obj.values():
            ec |= _walk_and_collect_ec(v)
    elif isinstance(json_obj, list):
        for v in json_obj:
            ec |= _walk_and_collect_ec(v)
    elif isinstance(json_obj, str):
        for val in _extract_ec_numbers_from_text(json_obj):
            ec.add(val)
    return ec


async def _get_json(client: httpx.AsyncClient, url: str, timeout: float, max_retries: int = 3) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """GET JSON with retries and timeout. Returns (json, error)."""
    backoff = 0.5
    for attempt in range(1, max_retries + 1):
        try:
            async with _SEMAPHORE:
                resp = await client.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp.json(), None
            elif resp.status_code == 404:
                return None, "Not found"
            # Retry on 5xx or unexpected statuses
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            if attempt == max_retries:
                return None, err
        await asyncio.sleep(backoff)
        backoff *= 2
    return None, "Max retries exceeded"


async def get_ec_numbers_for_pdb(
    pdb_id: str,
    *,
    timeout: float = 10.0,
    max_retries: int = 3,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Fetch EC numbers for a PDB ID from RCSB.

    - Validates the PDB ID.
    - Fetches entry metadata to get polymer entity IDs.
    - Queries each entity for EC annotations.
    - Returns structured results with per-entity and overall EC number lists.
    - Handles missing data and errors gracefully.

    Returns dict: {"pdb_id", "ec_numbers", "entities", "source", "errors"}
    """
    errors: List[str] = []
    pid = validate_pdb_id(pdb_id)

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(headers={"Accept": "application/json"})

    try:
        entry_url = ENTRY_URL.format(pdb_id=pid)
        entry_json, err = await _get_json(client, entry_url, timeout,
                                          max_retries)
        if err:
            errors.append(f"entry:{err}")
        if not entry_json:
            return {
                "pdb_id": pid,
                "ec_numbers": [],
                "entities": {},
                "source": "rcsb",
                "errors": errors,
            }

        # polymer_entity_ids may appear at top-level or under rcsb_entry_container_identifiers
        polymer_entity_ids: List[str] = []
        if isinstance(entry_json.get("polymer_entity_ids"), list):
            polymer_entity_ids = entry_json["polymer_entity_ids"]
        else:
            cont = entry_json.get("rcsb_entry_container_identifiers") or {}
            ids = cont.get("polymer_entity_ids")
            if isinstance(ids, list):
                polymer_entity_ids = ids

        entities_map: Dict[str, List[str]] = {}
        all_ec: Set[str] = set()
        for entity in polymer_entity_ids:
            eid = str(entity)
            entity_url = ENTITY_URL.format(pdb_id=pid, entity_id=eid)
            entity_json, eerr = await _get_json(client, entity_url, timeout, max_retries)
            if eerr or not entity_json:
                errors.append(f"entity:{pid}_{eid}:{eerr or 'no_data'}")
                continue

            # Try to locate common EC fields, otherwise fall back to deep scan
            ec_set: Set[str] = set()
            # Prefer explicit fields when available
            entity_poly = entity_json.get("entity_poly")
            if isinstance(entity_poly, dict):
                for key in ("pdbx_ec", "ec"):
                    val = entity_poly.get(key)
                    if isinstance(val, str):
                        ec_set.update(_extract_ec_numbers_from_text(val))
                    elif isinstance(val, list):
                        for item in val:
                            if isinstance(item, str):
                                ec_set.update(_extract_ec_numbers_from_text(item))

            ann = entity_json.get("rcsb_polymer_entity_annotation")
            if isinstance(ann, dict):
                ec_vals = ann.get("ec_numbers")
                if isinstance(ec_vals, list):
                    for v in ec_vals:
                        if isinstance(v, str):
                            ec_set.update(_extract_ec_numbers_from_text(v))
                        elif isinstance(v, dict):
                            # In some payloads, entries may be dicts with value fields
                            for s in _walk_and_collect_ec(v):
                                ec_set.add(s)
                elif isinstance(ec_vals, str):
                    ec_set.update(_extract_ec_numbers_from_text(ec_vals))

            # Also search other places (e.g., "pdbx_entity_poly" or free text annotations)
            if not ec_set:
                ec_set |= _walk_and_collect_ec(entity_json)

            entities_map[f"{pid}_{eid}"] = sorted(ec_set)
            all_ec |= ec_set

        # Fallback to legacy customReport API if no EC found via core endpoints
        if not all_ec:
            legacy_url = (
                "https://www.rcsb.org/pdb/rest/customReport.json?"
                f"structureId={pid}&customReportColumns=ecNo,entityId")
            legacy_json, lerr = await _get_json(client, legacy_url, timeout,
                                                max_retries)
            if lerr:
                errors.append(f"legacy:{lerr}")
            else:
                try:
                    records = legacy_json.get("customReport",
                                              {}).get("reportItems", [])
                    for rec in records:
                        # Format varies; try typical fields
                        ec_field = rec.get("ecNo") or rec.get(
                            "ecno") or rec.get("EC Number")
                        ent_field = rec.get("entityId") or rec.get("entity")
                        ecs = []
                        if isinstance(ec_field, str):
                            ecs = _extract_ec_numbers_from_text(ec_field)
                        elif isinstance(ec_field, list):
                            for item in ec_field:
                                if isinstance(item, str):
                                    ecs.extend(
                                        _extract_ec_numbers_from_text(item))
                        if ecs:
                            all_ec |= set(ecs)
                            if ent_field:
                                eid = str(ent_field)
                                if "_" not in eid:
                                    eid = f"{pid}_{eid}"
                                entities_map.setdefault(eid, [])
                                entities_map[eid] = sorted(
                                    set(entities_map[eid]) | set(ecs))
                except Exception as e:
                    errors.append(f"legacy_parse:{type(e).__name__}:{e}")

        return {
            "pdb_id": pid,
            "ec_numbers": sorted(all_ec),
            "entities": entities_map,
            "source": "rcsb",
            "errors": errors,
        }
    finally:
        if own_client and client is not None:
            await client.aclose()


def get_ec_numbers_for_pdb_sync(
    pdb_id: str,
    *,
    timeout: float = 10.0,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """Synchronous wrapper around the async lookup function."""
    return asyncio.run(get_ec_numbers_for_pdb(pdb_id, timeout=timeout, max_retries=max_retries))


# Optional: simple CLI when running this module directly
if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) < 2:
        print("Usage: python -m src.tools.pdb_ec_lookup <PDB_ID>")
        _sys.exit(1)
    pid = _sys.argv[1]
    try:
        res = get_ec_numbers_for_pdb_sync(pid)
        print(res)
    except Exception as exc:
        print(f"Error: {exc}")
        _sys.exit(2)
