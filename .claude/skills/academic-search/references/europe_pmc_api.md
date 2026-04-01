# Europe PMC API Reference

Use Europe PMC for biomedical and life-science literature.

## Base Endpoint

```text
https://www.ebi.ac.uk/europepmc/webservices/rest/search
```

## Common Patterns

### Keyword search

```text
https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=protein%20folding&format=json&pageSize=5
```

### Search by DOI

```text
https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:10.1038/s41586-024-07487-w&format=json&pageSize=1
```

### Search by PMID or PMCID

```text
https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:12345678%20AND%20SRC:MED&format=json
https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=PMCID:PMC1234567&format=json
```

### Recent biomedical papers

```text
https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=CRISPR%20AND%20FIRST_PDATE:[2023-01-01%20TO%202026-12-31]&format=json&pageSize=10
```

## Good Uses

- PubMed-like biomedical literature discovery
- PMC/PMID/PMCID-centric workflows
- Open-access full-text and biomedical preprint coverage
- Disease, gene, protein, drug, and clinical literature search

## Useful Fields

- `title`
- `authorString`
- `journalTitle`
- `pubYear`
- `doi`
- `pmid`
- `pmcid`
- `citedByCount`
- `isOpenAccess`
- `abstractText`

## Practical Notes

- Prefer Europe PMC when the query is clearly biomedical.
- Europe PMC often exposes identifiers and abstract text directly, so abstract reconstruction is usually unnecessary.
- Use exact identifiers when available: DOI, PMID, or PMCID.
- Very recent biomedical papers may have zero citations; if the user explicitly cares about citation signal, say so and optionally cross-check citation counts in OpenAlex.
- Europe PMC is also a strong source for full-text enrichment in biomedical results, but use that only after confirming the right papers.
