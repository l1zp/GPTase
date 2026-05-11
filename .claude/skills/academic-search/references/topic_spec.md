# Topic specification format

A topic spec is a JSON file describing what counts as on-topic for the sweep. It drives every filter decision in every script. Save under your project (e.g. `papers/kemp_topic.json`) so the spec is versioned with the corpus.

## Schema

```json
{
  "topic": "<human-readable name>",
  "queries": [ "<OpenAlex search expression>", ... ],
  "positive_title_terms": [ "<lowercase substring>", ... ],
  "exclude_title_terms":  [ "<lowercase substring>", ... ],
  "exclude_doi_prefixes": [ "<DOI prefix>", ... ],
  "use_europepmc": true | false
}
```

| Field | Required | Notes |
|---|---|---|
| `topic` | Yes | Free-text label, used in logs only |
| `queries` | Yes | List of OpenAlex search strings. Use `+` for AND, quotes for phrases (URL-encode them yourself if needed). Aim for 5-10 distinct facets. |
| `positive_title_terms` | Yes | Lowercased substrings. ANY match in the title makes the candidate strongly on-topic. Include canonical entity names, variant identifiers, substrate names. |
| `exclude_title_terms` | No | Lowercased substrings that automatically disqualify. Critical for narrow topics (e.g. excluding `pillararene` for "Kemp eliminase enzymes"). |
| `exclude_doi_prefixes` | No | Drop these DOI namespaces wholesale. See bundled defaults below. |
| `use_europepmc` | No | If true, also query Europe PMC. Use for biomedical / clinical topics. Default false. |

## Bundled defaults you should usually include in `exclude_doi_prefixes`

```json
[
  "10.2210/pdb",            // PDB structure depositions
  "10.5281/zenodo",         // Zenodo data deposits
  "10.13018/bmr",           // BMRB chemical-shift deposits
  "10.3410/f.",             // F1000/Faculty Opinions recommendations
  "10.26434/chemrxiv",      // ChemRxiv preprints
  "10.21203/",              // Research Square preprints
  "10.1101/",               // bioRxiv (drop UNLESS you want preprints)
  "10.25911/",              // ANU thesis repository
  "10.25549/",              // USC thesis
  "10.17760/",              // Northeastern thesis
  "10.7907/",               // Caltech thesis
  "10.17863/",              // Cambridge thesis
  "10.5962/",               // Biodiversity Heritage Library
  "10.1093/gmo/",           // Grove Music
  "10.1093/gao/",           // Grove Art
  "10.1093/ww/",            // Who's Who
  "10.1093/odnb/",          // Oxford DNB
  "10.1093/nq/"             // Notes & Queries
]
```

These are not topic-specific — they're noise classes that show up in any chemistry/biology query.

## Worked example: Kemp eliminase enzymes

```json
{
  "topic": "Kemp eliminase enzymes",
  "queries": [
    "Kemp+eliminase",
    "Kemp+elimination",
    "5-nitrobenzisoxazole",
    "designer+enzyme+Kemp",
    "HG3.17",
    "KE07+OR+KE59+OR+KE70",
    "AlleyCat"
  ],
  "positive_title_terms": [
    "kemp elimin", "nitrobenzisoxazole",
    "ke07", "ke15", "ke16", "ke59", "ke70",
    "hg3.17", "hg-3.17", "alleycat"
  ],
  "exclude_title_terms": [
    "pillararene", "cyclodextrin", "calixarene",
    "coordination cage", "cage-catalys",
    "micelle", "vesicle", "amphiphil",
    "ionic liquid", "natural coal", "membrane mimetic",
    "nanogel", "nanorod", "self-assembly", "self-organized",
    "copper-catalyz", "n-alkylation",
    "anion-π", "anion-pi"
  ],
  "exclude_doi_prefixes": [
    "10.2210/pdb", "10.5281/zenodo", "10.13018/bmr",
    "10.3410/f.", "10.26434/chemrxiv", "10.21203/",
    "10.1101/", "10.25911/", "10.25549/", "10.17760/",
    "10.7907/", "10.17863/", "10.1096/fasebj"
  ],
  "use_europepmc": false
}
```

The exclude list above was derived empirically — every term was added after a real candidate matched the positive regex but turned out to be off-topic. **Tune the exclude list iteratively**: when validation surfaces an off-topic paper that passed the filter, add the discriminating term.

## Discovering positive terms

When you don't know what the canonical entity names are, run a low-precision sweep first with only generic queries (e.g. "Kemp+elimination"), inspect the top 20-50 hits, and pull out:
- Variant identifiers (KE07, HG3.17, AlleyCat) — usually appear as `\b<letters><digits>\b` in titles
- Substrate names — usually long compound words appearing in many titles
- Author-coined family names

Once you have those, add them to `positive_title_terms` and re-run. Recall typically jumps 10-30%.

## Discovering exclude terms

After your first full sweep, look at every paper you'd manually drop and find the one word in its title that's specific to its (off-topic) subfield. Add that word — case folded — to `exclude_title_terms`. This is how the Kemp-eliminase exclude list was built (each entry corresponds to a real false-positive candidate).
