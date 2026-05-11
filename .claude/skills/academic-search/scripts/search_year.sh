#!/usr/bin/env bash
# search_year.sh — Stage 1: multi-engine year-restricted keyword harvest
#
# Usage: search_year.sh <topic_spec.json> [year]
#
# Reads queries from topic_spec.json, runs each against OpenAlex (and optionally
# Europe PMC + Crossref). Writes raw JSON to ./harvest/y_<year>_<engine>_<query>.json
# and an aggregated TSV (doi, first_author, year, title) to stdout.
#
# Designed for use by paper-collection-sweep skill.

set -euo pipefail
shopt -s nullglob

SPEC="${1:?topic_spec.json required as arg 1}"
YEAR="${2:-}"

[ -f "$SPEC" ] || { echo "spec not found: $SPEC" >&2; exit 1; }

OUT_DIR="${OUT_DIR:-./harvest}"
mkdir -p "$OUT_DIR"

# Year filter (OpenAlex)
if [ -n "$YEAR" ]; then
  YEAR_FILTER="filter=from_publication_date:${YEAR}-01-01,to_publication_date:${YEAR}-12-31"
  YEAR_TAG="${YEAR}"
else
  YEAR_FILTER=""
  YEAR_TAG="all"
fi

# Read queries from spec
QUERIES=$(jq -r '.queries[]' "$SPEC")

# OpenAlex parallel batch
i=0
while IFS= read -r q; do
  qslug=$(echo "$q" | tr '+./ ' '____' | tr -cd '[:alnum:]_-')
  out="${OUT_DIR}/y_${YEAR_TAG}_oa_${qslug}.json"
  url="https://api.openalex.org/works?search=${q}"
  if [ -n "$YEAR_FILTER" ]; then url="${url}&${YEAR_FILTER}"; fi
  url="${url}&per-page=100&select=id,doi,title,publication_year,authorships,referenced_works,abstract_inverted_index"
  curl -s "$url" -o "$out" &
  i=$((i+1))
  if (( i % 6 == 0 )); then wait; fi
done <<< "$QUERIES"
wait

# Optional: Europe PMC for biomedical scope (if topic spec opts in)
USE_PMC=$(jq -r '.use_europepmc // false' "$SPEC")
if [ "$USE_PMC" = "true" ]; then
  while IFS= read -r q; do
    qslug=$(echo "$q" | tr '+./ ' '____' | tr -cd '[:alnum:]_-')
    out="${OUT_DIR}/y_${YEAR_TAG}_pmc_${qslug}.json"
    pmc_q=$(printf '%s' "$q" | sed 's/+/ /g')
    if [ -n "$YEAR" ]; then pmc_q="${pmc_q} AND PUB_YEAR:${YEAR}"; fi
    enc_q=$(printf '%s' "$pmc_q" | jq -sRr @uri)
    curl -s "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=${enc_q}&format=json&pageSize=100&resultType=core" \
      -o "$out" &
  done <<< "$QUERIES"
  wait
fi

# Aggregate to TSV: doi \t first_author \t year \t title
{
  for f in "${OUT_DIR}"/y_${YEAR_TAG}_oa_*.json; do
    jq -r '.results[]? | select(.doi != null and .title != null) |
      [.doi, (.authorships[0].author.display_name // "Unknown"),
       (.publication_year // 0|tostring), .title] | @tsv' "$f" 2>/dev/null
  done
  if [ "$USE_PMC" = "true" ]; then
    for f in "${OUT_DIR}"/y_${YEAR_TAG}_pmc_*.json; do
      jq -r '.resultList.result[]? | select(.doi != null and .title != null) |
        [.doi, (.authorString // "Unknown"),
         (.pubYear // 0|tostring), .title] | @tsv' "$f" 2>/dev/null
    done
  fi
} | awk -F'\t' '!seen[tolower($1)]++'
