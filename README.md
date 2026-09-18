# CiteProof

Check whether every work in a BibTeX file actually exists, whether its metadata is right, and which scholarly sources support the match.

This is the **command-line package**. It is **not on PyPI**. Install it from this GitHub repository.

Human UI (queries run in your browser): **https://citeproof.pocketplay.win**

## Install

Python 3.10+, no third-party dependencies.

```sh
pip install "citeproof @ git+https://github.com/xiehuanyi/citeproof.git"
```

To upgrade, run `pip install --upgrade "citeproof @ git+https://github.com/xiehuanyi/citeproof.git"`. There is no `pip install citeproof` from PyPI.

## CLI

```sh
citeproof paper.bib
citeproof paper.bib --json
citeproof paper.bib --workers 3 --verbose
citeproof - --json < paper.bib
```

`--json` is the interface for scripts and LLM agents.

Exit codes: `0` none likely-hallucinated, `1` at least one `likely_hallucinated`, `2` bad input.

A source timeout, HTTP 429, or network error is **not** evidence the paper is missing. The tool says so in the output.

## Workers (threads)

`--workers` is how many **references** run in parallel. Each reference still talks to Crossref, DBLP, Semantic Scholar, OpenAlex and arXiv. CPU cores barely matter; scholarly APIs do.

Measured on three mixed real/fake entries (this machine, 2026-09-17):

| `--workers` | Wall time | Notes |
|---|---|---|
| 1 | ~47 s | Quietest. No 429s in that run. |
| 2 | ~13 s | Fast, still clean. |
| **3 (default)** | ~4 s | Fastest useful setting. Occasional Semantic Scholar HTTP 429, other sources still decided the verdict. |
| 4+ | no faster | Extra 429s. Capped at 6, and at the number of references. |

Use **3** unless Semantic Scholar is already throttling you, then use **2**. Do not set 8 because you have 8 cores.

## Verdicts

| Verdict | Meaning |
|---|---|
| `verified` | Work exists, metadata matches |
| `metadata_mismatch` | Work exists; author / year / venue / DOI / arXiv ID disagrees |
| `inconclusive` | Missing query fields, insufficient evidence, an unconfirmed arXiv ID, or a web reference needing manual review |
| `likely_hallucinated` | Several sources responded; nothing close matched |

Mismatch `type` values: `metadata_hallucination`, `franken_citation`, `invalid_identifier`, `version_confusion`.

Google Scholar is **not** queried. JSON includes `scholarUrl` for a human to open.

For model cards, blogs and project pages without a DOI or arXiv ID, a missing scholarly match produces `inconclusive` with `reason: web_check_required`. Text output includes the original HTTP(S) link when available and a regular web search link; JSON exposes `originalUrl` and `webSearchUrl`. These links are not fetched or treated as proof that the reference exists. Check the page's title, author, date and recommended citation manually. Strong scholarly matches and identifier conflicts retain their existing verdicts.

The browser UI queries Crossref, DBLP, Semantic Scholar and OpenAlex. Direct arXiv API queries are disabled there; this CLI continues to query arXiv.

## Agent skill

```sh
python scripts/install_skill.py
```

Installs `skills/citeproof` into `~/.grok/skills/citeproof`, `~/.codex/skills/citeproof`, and `~/.agents/skills/citeproof`, creating the parent directories as needed. Existing skill directories are left untouched by default.

To update an existing installation:

```sh
python scripts/install_skill.py --update
```

The update is prepared before replacing the installed directory. Custom files are retained; bundled files such as `SKILL.md` are updated. The complete old directory is kept under the corresponding tool's `skill-backups` directory (for example, `~/.codex/skill-backups/citeproof-...`), and its path is printed. If replacement fails, the installer restores the original directory when the destination remains free. Conflicting symlinks or file/directory types are refused without modifying the installation.

The skill tells an agent to run `citeproof FILE --json --workers 3` and how to read the result. A source with no supported query fields has status `skipped`; no request was sent, so it is not evidence that the work is missing. A result with `reason: missing_query_fields` is `inconclusive`. An arXiv ID conflict is an `invalid_identifier` metadata mismatch; an ID that could not be confirmed is `inconclusive`, not verified or declared wrong.

## Library

```python
from citeproof import verify_bibliography

report = verify_bibliography(open("paper.bib").read(), workers=3)
print(report["summary"])
```

## Website

https://citeproof.pocketplay.win — upload or paste a `.bib`, watch each source in a scrolling evidence log. The page never sends your bibliography to the CiteProof server.

## License

MIT
