"""PubChem SMILES Lookup Tool.

This tool searches PubChem database for compound information and retrieves
SMILES strings and CAS numbers by compound name using PubChem PUG REST API.
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from src.tools.base import BaseTool
from src.tools.base import ToolResult
from src.tools.base import ToolStatus

logger = logging.getLogger(__name__)

# CAS number pattern: XXXXX-XX-X (2-5 digits, then 2 digits, then 1 digit)
CAS_PATTERN = re.compile(r"^\d{2,5}-\d{2}-\d$")


class PubChemSMILESLookupTool(BaseTool):
    """Tool for looking up compound SMILES from PubChem database.

    This tool uses the PubChem PUG REST API to:
    1. Search for compounds by name
    2. Retrieve SMILES strings and other properties
    3. Handle multiple search results with ranking

    API Documentation: https://pubchemdocs.ncbi.nlm.nih.gov/pug-rest
    """

    TOOL_NAME = "pubchem_smiles_lookup"

    # PubChem API endpoints
    PUBCHEM_BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
    PUBCHEM_COMPOUND_URL = f"{PUBCHEM_BASE_URL}/compound"

    # Request timeout (seconds)
    DEFAULT_TIMEOUT = 10

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_BACKOFF = 0.5

    def __init__(self):
        """Initialize PubChem SMILES Lookup Tool."""
        super().__init__(
            name=self.TOOL_NAME,
            description="Look up compound SMILES from PubChem database",
        )
        self._session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create HTTP session with retry logic.

        Returns:
            Configured requests.Session with retry adapter
        """
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.MAX_RETRIES,
            backoff_factor=self.RETRY_BACKOFF,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    async def execute(
        self,
        compound_names: List[str],
        properties: Optional[List[str]] = None,
        search_type: str = "name",
    ) -> ToolResult:
        """Execute SMILES lookup for compound names.

        Args:
            compound_names: List of compound names to search for
            properties: Additional properties to retrieve (e.g., ["MolecularFormula", "MolecularWeight"])
            search_type: Type of search ("name", "cid", or "smiles")
            - "name": Search by compound name (default)
            - "cid": Search by PubChem CID
            - "smiles": Search by SMILES (reverse lookup)

        Returns:
            ToolResult with data containing:
                {
                    "compounds": [
                        {
                            "name": str,
                            "cid": int,
                            "smiles": str,
                            "properties": dict,
                            "match_score": float
                        },
                        ...
                    ],
                    "summary": {
                        "total_searched": int,
                        "found": int,
                        "not_found": int
                    }
                }
        """
        start_time = time.time()

        try:
            if not compound_names:
                return ToolResult.from_error("No compound names provided")

            # Default properties to retrieve
            if properties is None:
                properties = ["IsomericSMILES", "MolecularFormula", "MolecularWeight"]

            results = []
            found_count = 0
            not_found_count = 0

            for name in compound_names:
                try:
                    compound_data = await self._lookup_compound(
                        name, properties, search_type)

                    if compound_data:
                        results.append(compound_data)
                        found_count += 1
                    else:
                        # Record not found
                        results.append({
                            "name": name,
                            "cid": None,
                            "smiles": None,
                            "cas": None,
                            "properties": None,
                            "match_score": 0.0,
                            "error": "Not found in PubChem",
                        })
                        not_found_count += 1

                except Exception as e:
                    logger.error(f"Error looking up {name}: {e}")
                    results.append({
                        "name": name,
                        "cid": None,
                        "smiles": None,
                        "cas": None,
                        "properties": None,
                        "match_score": 0.0,
                        "error": str(e),
                    })
                    not_found_count += 1

            execution_time = time.time() - start_time

            # Prepare summary data
            data = {
                "compounds": results,
                "summary": {
                    "total_searched": len(compound_names),
                    "found": found_count,
                    "not_found": not_found_count,
                },
            }

            logger.info(
                f"PubChem lookup completed: {found_count}/{len(compound_names)} found")

            return ToolResult.success(
                data=data,
                metadata={
                    "search_type": search_type,
                    "properties_requested": properties,
                },
                execution_time=execution_time,
            )

        except Exception as e:
            logger.error(f"PubChem lookup failed: {e}", exc_info=True)
            return ToolResult.from_error(
                error_message=f"PubChem lookup failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    async def _lookup_compound(
        self,
        name: str,
        properties: List[str],
        search_type: str,
    ) -> Optional[Dict[str, Any]]:
        """Look up a single compound in PubChem.

        Args:
            name: Compound name or identifier
            properties: List of properties to retrieve
            search_type: Type of search ("name", "cid", "smiles")

        Returns:
            Compound data dictionary or None if not found
        """
        try:
            # URL encode the compound name
            encoded_name = quote(name)

            # Step 1: Search for compound CID
            if search_type == "name":
                cid_url = f"{self.PUBCHEM_COMPOUND_URL}/name/{encoded_name}/cids/JSON"
            elif search_type == "smiles":
                cid_url = f"{self.PUBCHEM_COMPOUND_URL}/smiles/{encoded_name}/cids/JSON"
            elif search_type == "cid":
                # Already have CID, skip search
                cid_list = [int(name)]
            else:
                raise ValueError(f"Invalid search_type: {search_type}")

            if search_type != "cid":
                response = self._session.get(cid_url, timeout=self.DEFAULT_TIMEOUT)
                response.raise_for_status()
                cid_data = response.json()

                # Extract CID list
                cid_list = cid_data.get("IdentifierList", {}).get("CID", [])

                if not cid_list:
                    return None

                # Use first (best) match
                cid = cid_list[0]
            else:
                cid = cid_list[0]

            # Step 2: Retrieve properties for the CID
            props_str = ",".join(properties)
            props_url = (
                f"{self.PUBCHEM_COMPOUND_URL}/cid/{cid}/property/{props_str}/JSON")

            response = self._session.get(props_url, timeout=self.DEFAULT_TIMEOUT)
            response.raise_for_status()
            props_data = response.json()

            # Extract properties
            # PubChem returns PropertyTable.Properties[0]
            props_items = props_data.get("PropertyTable", {}).get("Properties", [])
            if props_items:
                props_dict = props_items[0]  # First result
            else:
                props_dict = {}

            # Get SMILES (prioritize IsomericSMILES, fallback to CanonicalSMILES)
            smiles = props_dict.get("IsomericSMILES") or props_dict.get(
                "CanonicalSMILES") or props_dict.get("SMILES")

            if not smiles:
                # Fallback: fetch SMILES directly
                smiles_url = f"{self.PUBCHEM_COMPOUND_URL}/cid/{cid}/property/IsomericSMILES/JSON"
                response = self._session.get(smiles_url, timeout=self.DEFAULT_TIMEOUT)
                response.raise_for_status()
                smiles_data = response.json()
                smiles = (smiles_data.get("Properties", {}).get("Information",
                                                                [{}])[0].get("Value"))

            # Step 3: Fetch synonyms to extract CAS number
            cas_number = None
            try:
                synonyms_url = f"{self.PUBCHEM_COMPOUND_URL}/cid/{cid}/synonyms/TXT"
                response = self._session.get(synonyms_url, timeout=self.DEFAULT_TIMEOUT)
                response.raise_for_status()
                synonyms_text = response.text.strip()

                # Extract CAS number from synonyms
                for synonym in synonyms_text.split("\n"):
                    if CAS_PATTERN.match(synonym.strip()):
                        cas_number = synonym.strip()
                        break
            except Exception as e:
                logger.debug(f"Could not fetch synonyms for {name}: {e}")

            return {
                "name": name,
                "cid": cid,
                "smiles": smiles,
                "cas": cas_number,
                "properties": props_dict,
                "match_score": 1.0,  # Perfect match for direct lookup
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error looking up {name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error looking up {name}: {e}")
            return None

    async def get_synonyms(self, cid: int) -> ToolResult:
        """Get synonyms for a compound by CID.

        Args:
            cid: PubChem Compound ID

        Returns:
            ToolResult with list of synonyms
        """
        try:
            url = f"{self.PUBCHEM_COMPOUND_URL}/cid/{cid}/synonyms/TXT"
            response = self._session.get(url, timeout=self.DEFAULT_TIMEOUT)
            response.raise_for_status()

            synonyms = response.text.strip().split("\n")

            return ToolResult.success(data={
                "cid": cid,
                "synonyms": synonyms,
                "count": len(synonyms),
            })

        except Exception as e:
            logger.error(f"Error getting synonyms for CID {cid}: {e}")
            return ToolResult.from_error(f"Error getting synonyms: {str(e)}")

    async def close(self):
        """Close the HTTP session."""
        if self._session:
            self._session.close()
            self._session = None

    def get_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters.

        Returns:
            JSON schema dictionary
        """
        return {
            "type": "object",
            "properties": {
                "compound_names": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of compound names to search for",
                },
                "properties": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Additional properties to retrieve",
                    "default":
                    ["IsomericSMILES", "MolecularFormula", "MolecularWeight"],
                },
                "search_type": {
                    "type": "string",
                    "enum": ["name", "cid", "smiles"],
                    "description": "Type of search to perform",
                    "default": "name",
                },
            },
            "required": ["compound_names"],
        }


# Convenience function for direct usage
async def lookup_smiles(
    compound_names: List[str],
    properties: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Convenience function to look up SMILES for compound names.

    Args:
        compound_names: List of compound names to search
        properties: Optional additional properties to retrieve

    Returns:
        Dictionary with lookup results

    Example:
        >>> result = await lookup_smiles(["acetone", "ethanol"])
        >>> for compound in result["compounds"]:
        ...     if compound["smiles"]:
        ...         print(f"{compound['name']}: {compound['smiles']}")
    """
    tool = PubChemSMILESLookupTool()
    result = await tool.execute(compound_names=compound_names, properties=properties)
    await tool.close()
    return result.data
