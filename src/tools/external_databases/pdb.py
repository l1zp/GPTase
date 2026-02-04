"""PDB → EC Lookup Tool.

Retrieves Enzyme Commission (EC) numbers associated with a given PDB ID using
the RCSB Protein Data Bank Data API.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

from src.tools.base import BaseTool
from src.tools.base import ToolResult

logger = logging.getLogger(__name__)

# RCSB Data API endpoints
ENTRY_URL = "https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
ENTITY_URL = "https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id}/{entity_id}"

# Basic rate limiting (concurrent requests)
_SEMAPHORE = asyncio.Semaphore(4)


def validate_pdb_id(pdb_id: str) -> str:
    """Validate a PDB ID (typical 4-character alphanumeric code)."""
    if not isinstance(pdb_id, str):
        raise ValueError("PDB ID must be a string")
    pid = pdb_id.strip().upper()
    if len(pid) != 4 or not pid.isalnum():
        raise ValueError("Invalid PDB ID format: must be 4 alphanumeric characters")
    if not any(ch.isalpha() for ch in pid[1:]):
        raise ValueError("Invalid PDB ID: last three characters must contain a letter")
    return pid


def _extract_ec_numbers_from_text(text: str) -> List[str]:
    """Extract EC numbers from arbitrary text."""
    pattern = r"\b\d+\.\d+\.(\d+|-)\.(\d+|-)\b"
    return sorted({m.group(0) for m in re.finditer(pattern, text)})


def _walk_and_collect_ec(json_obj: Any) -> Set[str]:
    """Walk a JSON object to collect EC numbers."""
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


async def _get_json(
        client: httpx.AsyncClient,
        url: str,
        timeout: float,
        max_retries: int = 3) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """GET JSON with retries and timeout."""
    backoff = 0.5
    for attempt in range(1, max_retries + 1):
        try:
            async with _SEMAPHORE:
                resp = await client.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp.json(), None
            elif resp.status_code == 404:
                return None, "Not found"
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            if attempt == max_retries:
                return None, err
        await asyncio.sleep(backoff)
        backoff *= 2
    return None, "Max retries exceeded"


class PDBLookupTool(BaseTool):
    """Tool for looking up EC numbers and sequences from PDB."""

    def __init__(self):
        super().__init__(
            name="pdb_lookup",
            description="Look up EC numbers and protein sequences from PDB IDs",
        )

    async def execute(self, pdb_ids: List[str]) -> ToolResult:
        """Execute PDB lookup for multiple IDs."""
        try:
            results = []
            async with httpx.AsyncClient(
                    headers={"Accept": "application/json"}) as client:
                for pdb_id in pdb_ids:
                    data = await self._get_ec_numbers_for_pdb(pdb_id, client=client)
                    results.append(data)

            return ToolResult.success({"results": results, "count": len(results)})
        except Exception as e:
            return ToolResult.error(str(e))

    async def _get_ec_numbers_for_pdb(
        self,
        pdb_id: str,
        *,
        timeout: float = 10.0,
        max_retries: int = 3,
        client: httpx.AsyncClient,
    ) -> Dict[str, Any]:
        """Fetch EC numbers and sequence for a PDB ID from RCSB."""
        errors: List[str] = []
        try:
            pid = validate_pdb_id(pdb_id)
        except ValueError as e:
            return {"pdb_id": pdb_id, "error": str(e)}

        entry_url = ENTRY_URL.format(pdb_id=pid)
        entry_json, err = await _get_json(client, entry_url, timeout, max_retries)
        if err:
            errors.append(f"entry:{err}")
        if not entry_json:
            return {
                "pdb_id": pid,
                "ec_numbers": [],
                "entities": {},
                "sequence": "",
                "source": "rcsb",
                "errors": errors,
            }

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
        sequences: List[str] = []

        for entity in polymer_entity_ids:
            eid = str(entity)
            entity_url = ENTITY_URL.format(pdb_id=pid, entity_id=eid)
            entity_json, eerr = await _get_json(client, entity_url, timeout,
                                                max_retries)
            if eerr or not entity_json:
                errors.append(f"entity:{pid}_{eid}:{eerr or 'no_data'}")
                continue

            ec_set: Set[str] = set()
            entity_poly = entity_json.get("entity_poly")
            if isinstance(entity_poly, dict):
                seq = entity_poly.get("pdbx_seq_one_letter_code_can"
                                      ) or entity_poly.get("pdbx_seq_one_letter_code")
                if isinstance(seq, str):
                    seq = seq.replace('\n', '').replace(' ', '').strip()
                    if seq:
                        sequences.append(seq)

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
                            for s in _walk_and_collect_ec(v):
                                ec_set.add(s)
                elif isinstance(ec_vals, str):
                    ec_set.update(_extract_ec_numbers_from_text(ec_vals))

            if not ec_set:
                ec_set |= _walk_and_collect_ec(entity_json)

            entities_map[f"{pid}_{eid}"] = sorted(ec_set)
            all_ec |= ec_set

        sequence = sequences[0] if sequences else ""

        return {
            "pdb_id": pid,
            "ec_numbers": sorted(all_ec),
            "entities": entities_map,
            "sequence": sequence,
            "source": "rcsb",
            "errors": errors,
        }

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pdb_ids": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of 4-character PDB IDs"
                },
            },
            "required": ["pdb_ids"],
        }

        def get_ec_numbers_for_pdb_sync(
            pdb_id: str,
            *,
            timeout: float = 10.0,
            max_retries: int = 3,
        ) -> Dict[str, Any]:
            """Synchronous wrapper around the async lookup function."""

            async def _run():

                async with httpx.AsyncClient(
                        headers={"Accept": "application/json"}) as client:

                    tool = PDBLookupTool()

                    return await tool._get_ec_numbers_for_pdb(pdb_id,
                                                              timeout=timeout,
                                                              max_retries=max_retries,
                                                              client=client)

            return asyncio.run(_run())

        async def get_ec_numbers_for_pdb(
            pdb_id: str,
            *,
            timeout: float = 10.0,
            max_retries: int = 3,
            client: Optional[httpx.AsyncClient] = None,
        ) -> Dict[str, Any]:
            """Fetch EC numbers and sequence for a PDB ID from RCSB."""

            if client is None:

                async with httpx.AsyncClient(
                        headers={"Accept": "application/json"}) as client:

                    tool = PDBLookupTool()

                    return await tool._get_ec_numbers_for_pdb(pdb_id,
                                                              timeout=timeout,
                                                              max_retries=max_retries,
                                                              client=client)

            else:

                tool = PDBLookupTool()

                return await tool._get_ec_numbers_for_pdb(pdb_id,
                                                          timeout=timeout,
                                                          max_retries=max_retries,
                                                          client=client)
