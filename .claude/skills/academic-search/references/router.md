# Backend Router

Use this file when the right backend is ambiguous.

## Choose One First

| Need | Preferred backend | Fallback |
| --- | --- | --- |
| DOI, publisher, funder, license metadata | Crossref | OpenAlex |
| Biomedical papers, PMID, PMCID, PMC links | Europe PMC | OpenAlex |
| Highly cited general papers, source filters, broad literature search | OpenAlex | Crossref |
| Quick known-paper title lookup, one-paper detail | Semantic Scholar SDK | OpenAlex |
| Download or full-text enrichment after search | Europe PMC or OpenAlex | Crossref |

## Fast Heuristics

- Query mentions `PMID`, `PMCID`, `PubMed`, disease biomarkers, drug/gene/protein clinical literature: start with Europe PMC.
- Query starts from a DOI or asks for publisher/license/funder data: start with Crossref.
- Query asks for "most cited", "latest papers", "from Nature", or a broad literature set: start with OpenAlex.
- Query names one paper title and wants the best match fast: use Semantic Scholar SDK first if available.
- Query names a famous paper title: do not trust the first hit blindly; compare year, venue, DOI, and version type.
- Query asks for PDFs or full text in addition to search: still choose the best search backend first, then enrich download links afterward.

## Fallback Rules

- Semantic Scholar `429` or SDK failure -> OpenAlex
- Missing DOI metadata in OpenAlex or Semantic Scholar -> Crossref
- Biomedical query on a generic backend with weak identifier coverage -> Europe PMC
- Europe PMC returns only very new zero-citation papers and the user asked for citation signal -> widen the date window or cross-check counts in OpenAlex

## Scope Rules

- Do not mix multiple backends unless the first backend is missing a field the user explicitly asked for.
- Keep the first pass narrow and cheap.
- Only enrich metadata after selecting the correct paper or result set.
- Treat downloadability as enrichment, not primary routing.
