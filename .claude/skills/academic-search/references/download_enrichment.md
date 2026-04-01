# Download Enrichment

Use this file only after you have already identified the correct paper or result set.

## Goal

Prioritize finding the right papers first. Treat downloadability as optional enrichment.

## Enrichment Order

1. Europe PMC: use biomedical full-text and open-access signals first when available.
2. OpenAlex: inspect `best_oa_location`, `oa_url`, and `pdf_url`.
3. Crossref: inspect publisher URLs, license data, and any full-text or TDM links.
4. Semantic Scholar: use only as a supplementary landing-page signal, not as the primary download source.

## Output Labels

- `direct_pdf`: direct PDF or equivalent downloadable full text
- `oa_fulltext`: open-access full text or XML/HTML landing page
- `landing_page_only`: publisher or repository page exists, but direct download is not confirmed
- `metadata_only`: no clear full-text path found

## Rules

- Do not choose the search backend based mainly on downloadability.
- Do not suppress a more correct search result just because another result has an easier PDF link.
- When a direct download is not confirmed, say so explicitly.
- If multiple papers are returned, enrich only the selected or top-ranked results unless the user asked for download links for all of them.
