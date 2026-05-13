---
name: biochem_databases
description: |
  ESSENTIAL for querying biochemical and molecular biology databases via REST APIs. CONSULT THIS SKILL whenever the user mentions enzymes, proteins, reactions, compounds, pathways, or molecular structures. These databases have specific URL patterns, response formats, and query syntax that require this skill's guidance.

  ALWAYS trigger when user asks about: EC numbers, enzyme classification/catalytic activity, protein structures/sequences, biochemical reactions, compound properties (SMILES, InChI, molecular weight), metabolic pathways, or any query mentioning Rhea, KEGG, PDB, ExPASy, UniProt, PubChem, or ChEBI.

  Do NOT trigger for: searching academic papers/literature (use openalex_search instead), reading PDF files, or general web searches.

  Triggers on: EC number, enzyme, protein, reaction, compound, pathway, KEGG, Rhea, PDB, UniProt, PubChem, ChEBI, ExPASy, SMILES, InChI, molecular weight, catalytic activity, metabolic, biochemical, substrate, product, kinase, protease, oxidoreductase, transferase.
---

# Biochemical Database Queries

This skill provides guidance for querying biochemical and molecular biology databases using their REST APIs. Use Claude's built-in WebFetch or WebSearch tools to query these databases directly.

## Rhea Database (Biochemical Reactions)

**Base URL:** `https://www.rhea-db.org/rhea`

### Query Types

| Query Type | URL Pattern | Example |
|------------|-------------|---------|
| By EC number | `?query=ec:{ec}&format=tsv` | `https://www.rhea-db.org/rhea?query=ec:2.7.1.1&format=tsv` |
| By compound | `?query={name}&format=tsv` | `https://www.rhea-db.org/rhea?query=ATP&format=tsv` |
| By ChEBI ID | `?query=CHEBI:{id}&format=tsv` | `https://www.rhea-db.org/rhea?query=CHEBI:30616&format=tsv` |
| By Rhea ID | `?id={rhea_id}&format=tsv` | `https://www.rhea-db.org/rhea?id=15109&format=tsv` |

### Response Format
Returns TSV (tab-separated values) with columns:
- `Reaction identifier`: Rhea reaction identifier (e.g., RHEA:15109)
- `Equation`: Reaction equation (e.g., D-glucose + ATP = D-glucose 6-phosphate + ADP + H(+))
- `Enzyme class`: EC number(s) and enzyme names
- `Enzymes`: Number of associated enzymes

### Example Usage
```
WebFetch("https://www.rhea-db.org/rhea?query=ec:2.7.1.1&format=tsv")
```

---

## KEGG Database (Pathways & Genes)

**Base URL:** `https://rest.kegg.jp`

### Common Operations

| Operation | URL Pattern | Example |
|-----------|-------------|---------|
| Get EC info | `/get/ec:1.1.1.1` | `https://rest.kegg.jp/get/ec:1.1.1.1` |
| Get compound | `/get/cpd:C00002` | `https://rest.kegg.jp/get/cpd:C00002` |
| Get pathway | `/get/path:map00010` | `https://rest.kegg.jp/get/path:map00010` |
| Get gene | `/get/hsa:124` | `https://rest.kegg.jp/get/hsa:124` |
| List pathways | `/list/pathway` | `https://rest.kegg.jp/list/pathway` |
| List organisms | `/list/organism` | `https://rest.kegg.jp/list/organism` |
| Find by keyword | `/find/compound glucose` | `https://rest.kegg.jp/find/compound/glucose` |
| Link entries | `/link/pathway ec:1.1.1.1` | `https://rest.kegg.jp/link/pathway/ec:1.1.1.1` |

### Response Format
Returns plain text in KEGG flat-file format with fields like:
- `ENTRY`: Entry identifier
- `NAME`: Common names
- `DEFINITION`: Reaction or pathway definition
- `EQUATION`: Reaction equation
- `PATHWAY`: Associated pathways
- `MODULE`: KEGG modules
- `DBLINKS`: Cross-references

### Rate Limiting
Keep 1 second between requests. KEGG API may block rapid successive calls.

### Example Usage
```
WebFetch("https://rest.kegg.jp/get/ec:1.1.1.1")
WebFetch("https://rest.kegg.jp/link/pathway/ec:2.7.1.1")
```

---

## PDB / RCSB Database (Protein Structures)

**RCSB Data API:** `https://data.rcsb.org/rest/v1/core`

### Common Endpoints

| Data Type | URL Pattern | Example |
|-----------|-------------|---------|
| Entry summary | `/entry/{pdb_id}` | `https://data.rcsb.org/rest/v1/core/entry/1abc` |
| Polymer entity | `/polymer_entity/{pdb_id}/{entity_id}` | `https://data.rcsb.org/rest/v1/core/polymer_entity/1abc/1` |
| Uniprot mapping | `/uniprot/{pdb_id}` | `https://data.rcsb.org/rest/v1/core/uniprot/1abc` |
| Assembly | `/assembly/{pdb_id}` | `https://data.rcsb.org/rest/v1/core/assembly/1abc/1` |

### Response Format
Returns JSON with:
- `struct`: Structure metadata
- `exptl`: Experimental method
- `entity`: Entity information
- `rcsb_polymer_entity`: Polymer details including EC numbers
- `rcsb_entry_info`: Entry-level information

### Finding EC Numbers
EC numbers are in `rcsb_polymer_entity.rcsb_polymer_entityrcsb_ec_lineage`:
```json
{
  "rcsb_polymer_entity": {
    "rcsb_polymer_entityrcsb_ec_lineage": [
      {"id": "2.7.1.1"}
    ]
  }
}
```

### Example Usage
```
WebFetch("https://data.rcsb.org/rest/v1/core/entry/1abc")
```

### Apo/Holo Detection and Holo Structure Search

**Step 1 — Check if a PDB is apo (no non-polymer ligands):**

```bash
curl -s "https://data.rcsb.org/rest/v1/core/entry/{PDB_ID}" \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
nlig = d.get('rcsb_entry_info', {}).get('nonpolymer_entity_count', 0)
print(f'nonpolymer_entity_count: {nlig}')
if nlig == 0:
    print('STATUS: apo (no ligands)')
else:
    # Check each nonpolymer entity
    for eid in range(1, nlig + 1):
        pass  # fetch nonpolymer_entity/{PDB_ID}/{eid} for details
"
```

If `nonpolymer_entity_count == 0`, the structure is apo. If > 0, check each nonpolymer entity to see if it's a real ligand or just a crystallization additive (common additives: GOL, PEG, MPD, SO4, PO4, EDO, ACT, CL, MG, ZN, CA, NA).

**Step 2 — Get nonpolymer entity details:**

```bash
curl -s "https://data.rcsb.org/rest/v1/core/nonpolymer_entity/{PDB_ID}/{ENTITY_ID}" \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
comp_id = d.get('pdbx_entity_nonpoly', {}).get('comp_id', '?')
name = d.get('rcsb_nonpolymer_entity', {}).get('pdbx_description', '?')
print(f'{comp_id}: {name}')
"
```

**Step 3 — Search for holo structures by sequence similarity:**

Use the RCSB Search API with the apo structure's sequence to find homologous structures that contain ligands.

```bash
# Get chain A sequence
SEQ=$(curl -s "https://www.rcsb.org/fasta/entry/{PDB_ID}/display" \
  | awk '/^>/{if(n++)exit}!/^>/{printf "%s",$0}')

# Search for structures with >=90% identity
curl -s -X POST "https://search.rcsb.org/rcsbsearch/v2/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "type": "terminal",
      "service": "sequence",
      "parameters": {
        "evalue_cutoff": 0.001,
        "identity_cutoff": 0.9,
        "sequence_type": "protein",
        "value": "'"$SEQ"'"
      }
    },
    "return_type": "entry",
    "request_options": {
      "results_content_type": ["experimental"],
      "return_all_hits": true
    }
  }'
```

**Step 4 — Filter hits for holo structures and rank by sequence identity:**

For each hit PDB, check `nonpolymer_entity_count > 0` and inspect ligand IDs to filter out crystallization additives. Then do pairwise sequence alignment (BioPython `pairwise2.align.globalms` or simple mismatch counting after stripping His-tags) to rank by closeness to the query sequence.

**Common crystallization additives to exclude:**
`GOL, PEG, MPD, SO4, PO4, EDO, ACT, CL, MG, ZN, CA, NA, MN, 15P, DMS, BME, FMT, IOD, NO3, SCN`

**Step 5 — Report best holo match:**

Report: PDB ID, resolution, ligand ID + name, sequence identity (%), number of mutations vs. query.

### Complete Apo-to-Holo Workflow Example

```python
import json
from urllib.request import urlopen

ADDITIVE_IDS = {"GOL","PEG","MPD","SO4","PO4","EDO","ACT","CL","MG","ZN",
                "CA","NA","MN","15P","DMS","BME","FMT","IOD","NO3","SCN"}

def is_apo(pdb_id):
    """Return True if structure has no non-additive ligands."""
    url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
    d = json.loads(urlopen(url).read())
    entity_ids = d.get("rcsb_entry_container_identifiers", {}).get(
        "non_polymer_entity_ids", [])
    if not entity_ids:
        return True
    for eid in entity_ids:
        ent = json.loads(urlopen(
            f"https://data.rcsb.org/rest/v1/core/nonpolymer_entity/{pdb_id}/{eid}"
        ).read())
        comp = ent.get("pdbx_entity_nonpoly", {}).get("comp_id", "")
        if comp not in ADDITIVE_IDS:
            return False
    return True

def get_chain_a_seq(pdb_id):
    """Get first chain sequence from FASTA."""
    fasta = urlopen(
        f"https://www.rcsb.org/fasta/entry/{pdb_id}/display"
    ).read().decode()
    lines = []
    started = False
    for line in fasta.splitlines():
        if line.startswith(">"):
            if started:
                break
            started = True
            continue
        lines.append(line.strip())
    return "".join(lines)

def _count_mutations(seq_a, seq_b):
    """Count residue mutations between two sequences via gapped alignment.

    Strips trailing His-tags (LEHHHHHH) before comparing. Uses BioPython
    pairwise2 if available, falls back to simple mismatch counting on the
    shorter length.
    """
    import re
    a = re.sub(r"(LE)?H{4,}$", "", seq_a)
    b = re.sub(r"(LE)?H{4,}$", "", seq_b)
    try:
        from Bio import pairwise2
        aln = pairwise2.align.globalms(a, b, 2, -1, -5, -0.5,
                                       one_alignment_only=True)[0]
        muts = []
        rp = 0
        for i in range(len(aln.seqA)):
            if aln.seqA[i] != "-":
                rp += 1
            if (aln.seqA[i] != "-" and aln.seqB[i] != "-"
                    and aln.seqA[i] != aln.seqB[i]):
                muts.append(f"{aln.seqA[i]}{rp}{aln.seqB[i]}")
        return muts
    except ImportError:
        muts = []
        for i in range(min(len(a), len(b))):
            if a[i] != b[i]:
                muts.append(f"{a[i]}{i+1}{b[i]}")
        return muts

def find_holo(pdb_id, identity_cutoff=0.9, max_check=20):
    """Find closest holo structures by sequence similarity.

    Returns a list sorted by fewest mutations, each with:
    pdb_id, score, resolution, ligands, num_mutations, mutations.
    """
    seq = get_chain_a_seq(pdb_id)
    query = {
        "query": {"type": "terminal", "service": "sequence",
                  "parameters": {"evalue_cutoff": 0.001,
                                 "identity_cutoff": identity_cutoff,
                                 "sequence_type": "protein", "value": seq}},
        "return_type": "entry",
        "request_options": {"results_content_type": ["experimental"],
                            "return_all_hits": True},
    }
    import urllib.request
    req = urllib.request.Request(
        "https://search.rcsb.org/rcsbsearch/v2/query",
        data=json.dumps(query).encode(),
        headers={"Content-Type": "application/json"},
    )
    hits = json.loads(urllib.request.urlopen(req).read())
    results = []
    checked = 0
    for h in hits.get("result_set", []):
        hit_id = h["identifier"]
        if hit_id == pdb_id:
            continue
        checked += 1
        if checked > max_check:
            break
        try:
            if not is_apo(hit_id):
                hit_seq = get_chain_a_seq(hit_id)
                muts = _count_mutations(seq, hit_seq)
                results.append({
                    "pdb_id": hit_id,
                    "score": h.get("score", 0),
                    "num_mutations": len(muts),
                    "mutations": muts,
                })
        except Exception:
            pass
    results.sort(key=lambda r: r["num_mutations"])
    return results
```

---

## ExPASy Enzyme Database

**Base URL:** `https://enzyme.expasy.org/EC`

### Query Types

| Operation | URL Pattern | Example |
|-----------|-------------|---------|
| Get by EC | `/{ec_number}.txt` | `https://enzyme.expasy.org/EC/1.1.1.1.txt` |
| Web page | `/{ec_number}` | `https://enzyme.expasy.org/EC/2.7.1.1` |

### Response Format (text format)
Returns text with fields:
- `ID`: EC number
- `DE`: Enzyme name (description)
- `AN`: Alternate names
- `CA`: Catalytic reaction
- `CC`: Comments
- `DR`: Cross-references to UniProt entries

### Example Usage
```
WebFetch("https://enzyme.expasy.org/EC/2.7.1.1.txt")
```

---

## UniProt (Protein Information)

**Base URL:** `https://rest.uniprot.org/uniprotkb`

### Query Types

| Operation | URL Pattern | Example |
|-----------|-------------|---------|
| Get by accession | `/{accession}.json` | `https://rest.uniprot.org/uniprotkb/P00533.json` |
| Search | `?query={term}&format=json` | `https://rest.uniprot.org/uniprotkb?query=kinase&format=json` |
| Search by EC | `?query=ec:{ec}&format=json` | `https://rest.uniprot.org/uniprotkb?query=ec:2.7.1.1&format=json` |

### Example Usage
```
WebFetch("https://rest.uniprot.org/uniprotkb?query=ec:2.7.1.1&format=json&size=5")
```

---

## PubChem Database (Compounds)

**REST API Base:** `https://pubchem.ncbi.nlm.nih.gov/rest/pug`

### Compound Information

| Operation | URL Pattern | Example |
|-----------|-------------|---------|
| By CID | `/compound/cid/{cid}/property/IUPACName,SMILES,InChI/JSON` | `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/2244/property/IUPACName,SMILES,InChI/JSON` |
| By name | `/compound/name/{name}/property/.../JSON` | `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/aspirin/property/SMILES/JSON` |
| By SMILES | `/compound/smiles/{smiles}/...` | URL encode SMILES string |
| Synonyms | `/compound/cid/{cid}/synonyms/JSON` | `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/2244/synonyms/JSON` |
| Description | `/compound/cid/{cid}/description/JSON` | `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/2244/description/JSON` |

### Properties Available
- `MolecularFormula`
- `MolecularWeight`
- `SMILES`
- `InChI`
- `InChIKey`
- `IUPACName`
- `XLogP`
- `TPSA` (Topological Polar Surface Area)

### Example Usage
```
WebFetch("https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/glucose/property/SMILES,MolecularWeight/JSON")
```

---

## ChEBI Database (Chemical Entities)

**OLS4 API:** `https://www.ebi.ac.uk/ols4/api/ontologies/chebi/terms`

### Query by ChEBI ID
Convert CHEBI:30616 to URL format: `http://purl.obolibrary.org/obo/CHEBI_30616` -> URL encode -> `http%253A%252F%252Fpurl.obolibrary.org%252Fobo%252FCHEBI_30616`

| Operation | URL Pattern |
|-----------|-------------|
| Get compound | `/http%253A%252F%252Fpurl.obolibrary.org%252Fobo%252FCHEBI_{id}` |

### Example Usage
```
# Get ATP (CHEBI:30616)
WebFetch("https://www.ebi.ac.uk/ols4/api/ontologies/chebi/terms/http%253A%252F%252Fpurl.obolibrary.org%252Fobo%252FCHEBI_30616")
```

### Response Format
Returns JSON with:
- `iri`: Ontology IRI
- `description`: Compound description
- `synonyms`: Alternative names
- `annotation`: Additional metadata (charge, formula, etc.)

### Common ChEBI IDs

| Compound | ChEBI ID |
|----------|----------|
| ATP | CHEBI:30616 |
| ADP | CHEBI:456216 |
| NAD+ | CHEBI:15846 |
| NADH | CHEBI:16908 |
| Glucose | CHEBI:17234 |

---

## Best Practices

1. **Rate Limiting**: Space requests 0.5-1 second apart to avoid being blocked
2. **Error Handling**: Check HTTP status codes - 404 means not found, 429 means rate limited
3. **Caching**: Cache results locally when doing multiple queries
4. **URL Encoding**: Always URL-encode query parameters, especially SMILES strings

## Common Workflows

### Find reaction by EC number
1. Query Rhea: `https://www.rhea-db.org/rhea?query=ec:{EC_NUMBER}&format=tsv`
2. Get reaction equation, substrates, products

### Find enzyme structure
1. Get EC from UniProt or literature
2. Query PDB for structures with that EC: `https://data.rcsb.org/rest/v1/core/entry/{PDB_ID}`
3. Check `rcsb_polymer_entity.rcsb_polymer_entityrcsb_ec_lineage`

### Get compound SMILES
1. Query PubChem: `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{NAME}/property/SMILES/JSON`
2. Extract SMILES from response

### Resolve reaction substrates/products to SMILES

Given substrate and product names from a paper (e.g., from enzyme extraction pipeline output), resolve each to a canonical SMILES via PubChem. This is essential for downstream QM calculations, docking, and AF3 ligand input.

**Step 1 — Query each compound name:**

```bash
for NAME in "5-nitrobenzisoxazole" "2-hydroxy-5-nitrobenzonitrile"; do
  curl -s "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/${NAME// /%20}/property/IUPACName,CanonicalSMILES,MolecularFormula,InChIKey/JSON"
done
```

**Step 2 — Cross-validate with PDB ligand (if available):**

If the paper references a PDB ligand code (e.g., `3NY` for the TS analog), cross-check against the RCSB Chemical Component Dictionary:

```bash
curl -s "https://data.rcsb.org/rest/v1/core/chemcomp/{LIGAND_CODE}"
```

Parse `pdbx_chem_comp_descriptor` array for SMILES and compare InChIKey with PubChem result.

**Step 3 — Mass conservation sanity check:**

Compare `MolecularFormula` of substrate and product. For intramolecular rearrangements (e.g., Kemp elimination), they should be identical. For additions/eliminations, the difference should account for the lost/gained atoms (H2O, CO2, etc.).

**Output format:**

| Role | Name | SMILES | Formula | InChIKey |
|------|------|--------|---------|----------|
| Substrate | 5-nitro-1,2-benzoxazole | `C1=CC2=C(C=C1[N+](=O)[O-])C=NO2` | C7H4N2O3 | TWOYWCWKYDYTIP |
| Product | 2-hydroxy-5-nitrobenzonitrile | `C1=CC(=C(C=C1[N+](=O)[O-])C#N)O` | C7H4N2O3 | MPQNPFJBRPRBFF |

**Common pitfalls:**
- PubChem name search is case-insensitive but sensitive to hyphens and spacing. Try common synonyms if the first query returns 404.
- SMILES from PubChem are canonical (unique representation). SMILES from PDB CCD may use different canonicalization — compare via InChIKey, not string equality.
- URL-encode compound names that contain spaces, parentheses, or special characters.

### Trace pathway
1. Query KEGG for EC: `https://rest.kegg.jp/get/ec:{EC_NUMBER}`
2. Find linked pathways: `https://rest.kegg.jp/link/pathway/ec:{EC_NUMBER}`
3. Get pathway details: `https://rest.kegg.jp/get/path:{PATHWAY_ID}`

### Find proteins by EC number
1. Query UniProt: `https://rest.uniprot.org/uniprotkb?query=ec:{EC_NUMBER}&format=json&size=10`
2. Get protein sequences, organisms, and annotations
