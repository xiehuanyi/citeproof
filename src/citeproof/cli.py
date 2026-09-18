from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .pipeline import LIMITS, parse_job, verify_bibliography

WEBSITE = "https://citeproof.pocketplay.win"


def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="citeproof",
        description="Verify whether each BibTeX cited work actually exists. Try the website at " + WEBSITE,
    )
    parser.add_argument("bib", help="Path to a .bib file, or - for stdin")
    parser.add_argument(
        "--workers",
        type=int,
        default=LIMITS["default_workers"],
        help=f"Parallel references (default {LIMITS['default_workers']}, max {LIMITS['max_workers']}). 3 is the usual sweet spot; 4+ often trips Semantic Scholar 429s.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON (for agents and scripts)")
    parser.add_argument("--verbose", action="store_true", help="Print per-source progress to stderr")
    parser.add_argument("--version", action="version", version=f"citeproof {__version__}")
    args = parser.parse_args(argv)

    try:
        bibtex = _read_input(args.bib)
        parse_job(bibtex)
    except FileNotFoundError:
        print(f"citeproof: file not found: {args.bib}", file=sys.stderr)
        return 2
    except ValueError as err:
        print(f"citeproof: {err}", file=sys.stderr)
        return 2

    def on_event(ev):
        if not args.verbose:
            return
        if ev["type"] == "source_start":
            print(f"  querying {ev['label']} · {ev['ref'].get('key')}", file=sys.stderr)
        elif ev["type"] == "source_done":
            r = ev["report"]
            extra = r["error"]["code"] if r.get("error") else r["status"]
            print(f"  {r['label']}: {extra} · {ev['ref'].get('key')}", file=sys.stderr)

    result = verify_bibliography(bibtex, workers=args.workers, on_event=on_event if args.verbose else None)
    if args.json:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        s = result["summary"]
        print(
            f"scanned {s['scanned']}  verified {s['verified']}  metadata {s['metadata_mismatch']}  "
            f"inconclusive {s['inconclusive']}  likely-hallucinated {s['likely_hallucinated']}  workers {result['workers']}"
        )
        for item in result["results"]:
            mark = {
                "verified": "OK",
                "metadata_mismatch": "META",
                "inconclusive": "?",
                "likely_hallucinated": "FAKE?",
            }.get(item["verdict"], item["verdict"])
            title = (item["bib"].get("title") or item["key"])[:88]
            kind = f" / {item['type']}" if item.get("type") else ""
            print(f"[{mark}] {item['key']}{kind}")
            print(f"      {title}")
            if item.get("note"):
                print(f"      {item['note']}")
            for src in item.get("sources") or []:
                if src["status"] == "error":
                    code = (src.get("error") or {}).get("code")
                    print(f"      - {src['label']}: {code} (not a missing paper)")
                elif src["status"] == "ok" and src.get("matches"):
                    print(f"      - {src['label']}: {round(src['matches'][0]['overall'] * 100)}%")
                else:
                    print(f"      - {src['label']}: no hit")
        print(f"\nTry the browser UI: {WEBSITE}")
        print("A failed source (timeout, 429, network) is not evidence the paper is missing.")

    if any(i["verdict"] == "likely_hallucinated" for i in result["results"]):
        return 1
    return 0
