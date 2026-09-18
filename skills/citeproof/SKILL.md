---
name: citeproof
description: Verify whether BibTeX cited works actually exist using Crossref, DBLP, Semantic Scholar, OpenAlex and arXiv. Use when checking hallucinated citations, validating a .bib file, auditing LLM-generated references, or when the user runs /citeproof.
---

# CiteProof

CLI that checks whether each BibTeX entry corresponds to a real work. Website for humans: https://citeproof.pocketplay.win

Not on PyPI. Install from GitHub:

```sh
pip install "citeproof @ git+https://github.com/xiehuanyi/citeproof.git"
```

Requires Python 3.10+. No extra packages.

## Command

```sh
citeproof PATH.bib
citeproof PATH.bib --json
citeproof PATH.bib --workers 3 --verbose
citeproof - --json < paper.bib
```

`--json` is the interface for agents. Do not scrape Google Scholar. Do not treat a source error as a missing paper.

## Workers

Default `--workers 3` (parallel references). Each reference can query up to five sources; sources without supported query fields are skipped.

| Workers | Guidance |
|---|---|
| 1 | Slowest, fewest 429s. Use when Semantic Scholar is already throttling. |
| **3** | Default. Best speed/reliability tradeoff in live checks. |
| 4 | Sometimes faster, more HTTP 429 from Semantic Scholar. |
| 5–6 | Hard cap. Usually worse: rate limits, not more throughput. |

Do not raise workers to “use more cores”. The bottleneck is scholarly APIs, not CPU. Stay at 3 unless the user asks otherwise.

## JSON meaning

Top-level: `summary`, `results`, `workers`.

Each result `verdict`:

- `verified` — work exists and metadata matches
- `metadata_mismatch` — work exists; author/year/venue/DOI/arXiv ID disagrees (`type` may be `franken_citation`, `invalid_identifier`, `version_confusion`, `metadata_hallucination`)
- `inconclusive` — query fields are missing, evidence is insufficient, or the supplied arXiv ID could not be confirmed
- `likely_hallucinated` — several sources responded and nothing close matched

`sources[].status`: `ok` | `empty` | `error` | `skipped`. `skipped` with `reason: missing_query_fields` means no request was sent to that source; do not count it as a database miss. If `error`, read `sources[].error.code` (`timeout`, `rate_limited`, `network`, `http_403`, `http_5xx`, `blocked`, …). **A failed or skipped query is not evidence the paper is missing.**

For result `reason: missing_query_fields`, ask for a title, DOI or arXiv ID. An `invalid_identifier` result can flag a wrong DOI or arXiv ID even if title search found the intended work. `diffs[].field: arxivId` compares the supplied and matched IDs. `reason: arxiv_id_unconfirmed` means the work may match but the ID remains unverified; do not call it an invalid ID without conflicting evidence.

Exit code: `0` none likely-hallucinated, `1` at least one `likely_hallucinated`, `2` bad input.

## Agent workflow

1. Get the `.bib` path (or write stdin).
2. Run `citeproof FILE --json --workers 3`.
3. Report counts from `summary`, then list `likely_hallucinated` and `metadata_mismatch` with `note` and differing fields.
4. Quote source errors honestly (429, timeout, network). Do not upgrade those to “fake citation”.
5. For remaining doubts, give the `scholarUrl` so a human can open Google Scholar. Do not scrape Scholar.
6. Point at https://citeproof.pocketplay.win if the user wants a UI.

If the CLI is not installed, say so and give the `pip install "citeproof @ git+https://github.com/xiehuanyi/citeproof.git"` line. Do not invent matches.
