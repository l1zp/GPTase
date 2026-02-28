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
Convert CHEBI:30616 to URL format: `http://purl.obolibrary.org/obo/CHEBI_30616` → URL encode → `http%253A%252F%252Fpurl.obolibrary.org%252Fobo%252FCHEBI_30616`

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

### Trace pathway
1. Query KEGG for EC: `https://rest.kegg.jp/get/ec:{EC_NUMBER}`
2. Find linked pathways: `https://rest.kegg.jp/link/pathway/ec:{EC_NUMBER}`
3. Get pathway details: `https://rest.kegg.jp/get/path:{PATHWAY_ID}`

### Find proteins by EC number
1. Query UniProt: `https://rest.uniprot.org/uniprotkb?query=ec:{EC_NUMBER}&format=json&size=10`
2. Get protein sequences, organisms, and annotations
