from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from .errors import serialize_error
from .match import decide, score_candidate
from .normalize import normalize_entry, scholar_url
from .parse import parse_bibtex
from .providers import PROVIDERS

LIMITS = {"max_chars": 400_000, "max_entries": 200, "default_workers": 3, "max_workers": 6}


def parse_job(bibtex: str) -> list[dict]:
    if not isinstance(bibtex, str) or not bibtex.strip():
        raise ValueError("Paste a BibTeX bibliography, or pass a .bib file.")
    if len(bibtex) > LIMITS["max_chars"]:
        raise ValueError("Please keep the bibliography under 400 KB.")
    entries = parse_bibtex(bibtex)
    if not entries:
        raise ValueError("No BibTeX entries found. Expected blocks like @article{...}.")
    if len(entries) > LIMITS["max_entries"]:
        raise ValueError(f"This version checks up to {LIMITS['max_entries']} references at a time.")
    refs = [normalize_entry(e) for e in entries]
    for i, ref in enumerate(refs):
        ref["index"] = i
    return refs


def _uniq(cands: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for c in cands:
        key = (c.get("source"), c.get("doi"), c.get("arxiv_id"), (c.get("title") or "").lower(), c.get("year"), c.get("via"))
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def _can_query(provider: dict, ref: dict) -> bool:
    fields = provider.get("query_fields", ("title", "doi", "arxiv_id"))
    return any(ref.get(field) for field in fields)


def _resolve_provider(provider: dict, ref: dict) -> dict:
    if not _can_query(provider, ref):
        return {
            "id": provider["id"],
            "label": provider["label"],
            "status": "skipped",
            "reason": "missing_query_fields",
            "error": None,
            "candidates": [],
        }
    try:
        candidates = provider["resolve"](ref) or []
        return {
            "id": provider["id"],
            "label": provider["label"],
            "status": "ok" if candidates else "empty",
            "error": None,
            "candidates": candidates,
        }
    except Exception as err:
        return {
            "id": provider["id"],
            "label": provider["label"],
            "status": "error",
            "error": serialize_error(err),
            "candidates": [],
        }


def verify_one(ref: dict, providers=None, on_event=None) -> dict:
    providers = providers or PROVIDERS
    if on_event:
        on_event({"type": "ref_start", "ref": ref})
    reports = []
    with ThreadPoolExecutor(max_workers=len(providers)) as pool:
        futs = {}
        for p in providers:
            if on_event and _can_query(p, ref):
                on_event({"type": "source_start", "ref": ref, "id": p["id"], "label": p["label"]})
            futs[pool.submit(_resolve_provider, p, ref)] = p
        for fut in as_completed(futs):
            report = fut.result()
            reports.append(report)
            if on_event:
                on_event({"type": "source_done", "ref": ref, "report": report})
    reports.sort(key=lambda r: [p["id"] for p in providers].index(r["id"]))
    scored = []
    for report in reports:
        for cand in _uniq(report["candidates"]):
            scored.append(score_candidate(ref, cand))
    public = []
    for report in reports:
        matches = [
            {"title": c["title"], "year": c.get("year"), "overall": round(c["overall"], 3), "url": c.get("url")}
            for c in scored
            if c.get("source") == report["id"]
        ][:3]
        public.append({k: v for k, v in report.items() if k != "candidates"} | {"matches": matches})
    decision = decide(ref, scored, public)
    best = decision.get("best")
    item = {
        "key": ref.get("key"),
        "index": ref.get("index"),
        "bib": {
            "title": ref.get("title"),
            "authors": ref.get("authors"),
            "year": ref.get("year"),
            "venue": ref.get("venue"),
            "doi": ref.get("doi"),
            "arxivId": ref.get("arxiv_id"),
        },
        "verdict": decision["verdict"],
        "type": decision.get("type"),
        "reason": decision.get("reason"),
        "confidence": round(float(decision.get("confidence") or 0), 3),
        "note": decision.get("note"),
        "diffs": decision.get("diffs") or [],
        "best": None
        if not best
        else {
            "source": best.get("source"),
            "title": best.get("title"),
            "authors": best.get("authors"),
            "year": best.get("year"),
            "venue": best.get("venue"),
            "doi": best.get("doi"),
            "arxivId": best.get("arxiv_id"),
            "url": best.get("url"),
            "overall": round(best["overall"], 3),
            "scores": {k: round(v, 3) for k, v in (best.get("scores") or {}).items()},
        },
        "sources": decision.get("sources"),
        "scholarUrl": scholar_url(ref),
    }
    if on_event:
        on_event({"type": "ref_done", "item": item})
    return item


def summarize(results: list[dict]) -> dict:
    counts = {
        "scanned": len(results),
        "verified": 0,
        "metadata_mismatch": 0,
        "inconclusive": 0,
        "likely_hallucinated": 0,
    }
    for row in results:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    return counts


def verify_bibliography(bibtex: str, workers: int | None = None, on_item=None, on_event=None, providers=None) -> dict:
    refs = parse_job(bibtex)
    workers = max(1, min(int(workers or LIMITS["default_workers"]), LIMITS["max_workers"], len(refs) or 1))
    results: list[dict | None] = [None] * len(refs)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(verify_one, ref, providers, on_event): ref for ref in refs}
        for fut in as_completed(futs):
            item = fut.result()
            results[item["index"]] = item
            if on_item:
                on_item(item, len(refs))
    done = [r for r in results if r is not None]
    return {"summary": summarize(done), "results": done, "workers": workers}
