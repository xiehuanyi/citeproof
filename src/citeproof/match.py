from __future__ import annotations

from .normalize import author_last_name, normalize_text, tokenize

WEIGHTS = {"title": 0.55, "authors": 0.2, "year": 0.1, "venue": 0.1, "identifier": 0.05}
STOP = {"the", "a", "an", "of", "and", "in", "on", "for", "to", "with"}
VENUE_GROUPS = [
    ["neurips", "nips", "neural information processing systems", "advances in neural information processing systems"],
    ["icml", "international conference on machine learning"],
    ["iclr", "international conference on learning representations"],
    ["cvpr", "computer vision and pattern recognition"],
    ["iccv", "international conference on computer vision"],
    ["eccv", "european conference on computer vision"],
    ["acl", "association for computational linguistics", "annual meeting of the association for computational linguistics"],
    ["naacl", "north american chapter of the association for computational linguistics"],
    ["emnlp", "empirical methods in natural language processing"],
    ["aaai", "association for the advancement of artificial intelligence"],
    ["ijcai", "international joint conference on artificial intelligence"],
    ["kdd", "knowledge discovery and data mining"],
    ["www", "world wide web", "the web conference"],
    ["sigir", "international acm sigir"],
    ["chi", "human factors in computing systems"],
]


def _clamp(n: float) -> float:
    return max(0.0, min(1.0, n))


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    if len(a) > len(b):
        a, b = b, a
    row = list(range(len(a) + 1))
    for j, cb in enumerate(b, 1):
        prev = j - 1
        row[0] = j
        for i, ca in enumerate(a, 1):
            cur = row[i]
            row[i] = min(row[i] + 1, row[i - 1] + 1, prev + (0 if ca == cb else 1))
            prev = cur
    return row[len(a)]


def ratio(a: str, b: str) -> float:
    n = max(len(a), len(b))
    return 1 if not n else 1 - levenshtein(a, b) / n


def _token_sort_ratio(a: str, b: str) -> float:
    return ratio(" ".join(sorted(tokenize(a))), " ".join(sorted(tokenize(b))))


def _dice(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    def grams(s: str) -> dict[str, int]:
        t = f" {s} "
        g: dict[str, int] = {}
        for i in range(len(t) - 1):
            k = t[i : i + 2]
            g[k] = g.get(k, 0) + 1
        return g

    A, B = grams(a), grams(b)
    overlap = sum(min(n, B.get(k, 0)) for k, n in A.items())
    total = sum(A.values()) + sum(B.values())
    return (2 * overlap) / total if total else 0.0


def title_similarity(a: str, b: str) -> float:
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    base = max(ratio(na, nb), _token_sort_ratio(na, nb), _dice(na, nb))
    length = min(len(na), len(nb)) / max(len(na), len(nb))
    return _clamp(base * (0.62 + 0.38 * length))


def author_overlap(bib_names, cand_names) -> float:
    a = {author_last_name(n) for n in (bib_names or []) if len(author_last_name(n)) > 1}
    b = {author_last_name(n) for n in (cand_names or []) if len(author_last_name(n)) > 1}
    if not a and not b:
        return 0.5
    if not a or not b:
        return 0.0
    hit = len(a & b)
    recall = hit / len(a)
    precision = hit / len(b)
    if recall == 1 and len(a) >= 2:
        return 1.0
    return _clamp(0.65 * recall + 0.35 * precision)


def year_score(bib_year, cand_year) -> float:
    if not bib_year or not cand_year:
        return 0.5
    d = abs(int(bib_year) - int(cand_year))
    return {0: 1.0, 1: 0.62, 2: 0.35}.get(d, 0.0)


def _venue_key(value: str) -> str:
    n = normalize_text(value)
    if not n:
        return ""
    tokens = [t for t in n.split(" ") if t not in STOP]
    compact = " ".join(tokens)
    for group in VENUE_GROUPS:
        if any(alias in compact or compact in alias for alias in group):
            return group[0]
    return " ".join(tokens[:4])


def venue_score(a: str, b: str) -> float:
    ka, kb = _venue_key(a), _venue_key(b)
    if not ka or not kb:
        return 0.5
    if ka == kb:
        return 1.0
    return max(ratio(ka, kb), _dice(ka, kb))


def identifier_score(ref: dict, cand: dict) -> dict:
    matched = False
    conflict = False
    if ref.get("doi") and cand.get("doi"):
        if ref["doi"] == cand["doi"]:
            matched = True
        elif cand.get("via") == "doi":
            conflict = True
    if ref.get("arxiv_id") and cand.get("arxiv_id"):
        if ref["arxiv_id"] == cand["arxiv_id"]:
            matched = True
        elif cand.get("via") in {"arxiv", "id"}:
            conflict = True
    if not ref.get("doi") and not ref.get("arxiv_id"):
        return {"score": 0.5, "conflict": False, "matched": False}
    if matched:
        return {"score": 1.0, "conflict": False, "matched": True}
    if conflict:
        return {"score": 0.0, "conflict": True, "matched": False}
    return {"score": 0.5, "conflict": False, "matched": False}


def score_candidate(ref: dict, cand: dict) -> dict:
    title = title_similarity(ref.get("title") or "", cand.get("title") or "")
    authors = author_overlap(ref.get("authors") or [], cand.get("authors") or [])
    year = year_score(ref.get("year"), cand.get("year"))
    venue = venue_score(ref.get("venue") or "", cand.get("venue") or "")
    ident = identifier_score(ref, cand)
    overall = (
        title * WEIGHTS["title"]
        + authors * WEIGHTS["authors"]
        + year * WEIGHTS["year"]
        + venue * WEIGHTS["venue"]
        + ident["score"] * WEIGHTS["identifier"]
    )
    out = dict(cand)
    out["scores"] = {"title": title, "authors": authors, "year": year, "venue": venue, "identifier": ident["score"]}
    out["overall"] = overall
    out["identifier_conflict"] = ident["conflict"]
    out["identifier_matched"] = ident["matched"]
    return out


def _diffs(ref: dict, cand: dict) -> list[dict]:
    diffs = []
    if ref.get("title") and cand.get("title") and title_similarity(ref["title"], cand["title"]) < 0.97:
        diffs.append({"field": "title", "bib": ref["title"], "found": cand["title"]})
    if ref.get("authors") and cand.get("authors") and author_overlap(ref["authors"], cand["authors"]) < 0.85:
        diffs.append({"field": "authors", "bib": ", ".join(ref["authors"]), "found": ", ".join(cand["authors"])})
    if ref.get("year") and cand.get("year") and int(ref["year"]) != int(cand["year"]):
        diffs.append({"field": "year", "bib": str(ref["year"]), "found": str(cand["year"])})
    if ref.get("venue") and cand.get("venue") and venue_score(ref["venue"], cand["venue"]) < 0.82:
        diffs.append({"field": "venue", "bib": ref["venue"], "found": cand["venue"]})
    if ref.get("doi") and cand.get("doi") and ref["doi"] != cand["doi"]:
        diffs.append({"field": "doi", "bib": ref["doi"], "found": cand["doi"]})
    if ref.get("arxiv_id") and cand.get("arxiv_id") and ref["arxiv_id"] != cand["arxiv_id"]:
        diffs.append({"field": "arxivId", "bib": ref["arxiv_id"], "found": cand["arxiv_id"]})
    return diffs


def decide(ref: dict, scored: list[dict], source_statuses: list[dict]) -> dict:
    ok_sources = [s for s in source_statuses if s.get("status") in {"ok", "empty"}]
    error_sources = [s for s in source_statuses if s.get("status") == "error"]
    ranked = sorted(
        scored,
        key=lambda c: -(c["overall"] + (0.02 if ref.get("year") and c.get("year") == ref.get("year") else 0)),
    )
    best = ranked[0] if ranked else None
    diffs = _diffs(ref, best) if best else []
    base = {"best": best, "candidates": ranked[:4], "diffs": diffs, "sources": source_statuses}
    queried_ok = len(ok_sources)

    if not any(ref.get(field) for field in ("title", "doi", "arxiv_id")):
        return {
            **base,
            "verdict": "inconclusive",
            "type": None,
            "reason": "missing_query_fields",
            "confidence": 0.0,
            "note": "No title, DOI or arXiv ID was supplied. No scholarly source was queried.",
        }

    # Inspect every identifier match: a better title hit must not hide a wrong ID.
    id_conflict = next((c for c in ranked if ref.get("title") and c.get("title") and (
        (c.get("identifier_matched") and c["scores"]["title"] < 0.72)
        or (c.get("identifier_conflict") and c["scores"]["title"] < 0.78)
    )), None)
    arxiv_mismatch = next((c for c in ranked if (
        ref.get("arxiv_id") and c.get("arxiv_id") and ref["arxiv_id"] != c["arxiv_id"]
        and c["scores"]["title"] >= 0.9 and c["scores"]["authors"] >= 0.55
    )), None)
    if id_conflict or arxiv_mismatch:
        evidence = id_conflict or arxiv_mismatch
        return {
            **base,
            "best": evidence,
            "diffs": _diffs(ref, evidence),
            "verdict": "metadata_mismatch",
            "type": "invalid_identifier",
            "reason": None if id_conflict else "arxiv_id_mismatch",
            "confidence": max(evidence["scores"]["identifier"], 0.8),
            "note": "The identifier in the BibTeX record points at a different work than the title and authors."
            if id_conflict else "The arXiv ID in the BibTeX record differs from the matched work's arXiv ID.",
        }

    if not best or best["overall"] < 0.54:
        if queried_ok >= 3:
            return {
                **base,
                "verdict": "likely_hallucinated",
                "type": "fabricated_work",
                "confidence": 1 - best["overall"] if best else 0.9,
                "note": f"No convincing match across {queried_ok} scholarly sources. Not found is not proof of fabrication.",
            }
        return {
            **base,
            "verdict": "inconclusive",
            "type": None,
            "confidence": 0.35,
            "note": "Some databases failed or coverage is too thin to call this a hallucination.",
        }

    if best["scores"]["title"] >= 0.9 and best["scores"]["authors"] < 0.4 and ref.get("authors"):
        return {
            **base,
            "verdict": "metadata_mismatch",
            "type": "franken_citation",
            "confidence": best["scores"]["title"],
            "note": "A work with this title exists, but the authorship does not match.",
        }

    year_diff = abs(int(ref["year"]) - int(best["year"])) if ref.get("year") and best.get("year") else 0
    version_like = (
        1 <= year_diff <= 2
        and best["scores"]["title"] >= 0.9
        and best["scores"]["authors"] >= 0.7
        and (ref.get("arxiv_id") or best.get("arxiv_id") or "arxiv" in (best.get("venue") or "").lower())
    )
    if best["overall"] >= 0.86 and best["scores"]["title"] >= 0.84 and best["scores"]["authors"] >= 0.55:
        if not diffs:
            if ref.get("arxiv_id") and not any(
                c.get("arxiv_id") == ref["arxiv_id"]
                and c["scores"]["title"] >= 0.84 and c["scores"]["authors"] >= 0.55
                for c in ranked
            ):
                return {
                    **base,
                    "verdict": "inconclusive",
                    "type": None,
                    "reason": "arxiv_id_unconfirmed",
                    "confidence": best["overall"],
                    "note": "A matching work was found, but the supplied arXiv ID could not be confirmed. This does not establish that the ID is wrong.",
                }
            return {**base, "verdict": "verified", "type": None, "confidence": best["overall"], "note": "Strong evidence that this work exists."}
        if version_like:
            return {
                **base,
                "verdict": "metadata_mismatch",
                "type": "version_confusion",
                "confidence": best["overall"],
                "note": "Likely the same work in different versions, for example arXiv then a conference paper.",
            }
        return {
            **base,
            "verdict": "metadata_mismatch",
            "type": "metadata_hallucination",
            "confidence": best["overall"],
            "note": "The work exists, but one or more BibTeX fields disagree with the matched record.",
        }

    if best["overall"] >= 0.7 and best["scores"]["title"] >= 0.78:
        kind = "franken_citation" if best["scores"]["authors"] < 0.4 and any(d["field"] == "authors" for d in diffs) else "metadata_hallucination"
        return {**base, "verdict": "metadata_mismatch", "type": kind, "confidence": best["overall"], "note": "A possible match was found, but the metadata differs."}

    if len(error_sources) >= 2 or queried_ok < 2:
        return {**base, "verdict": "inconclusive", "type": None, "confidence": best["overall"], "note": "Not enough independent sources responded cleanly."}

    return {
        **base,
        "verdict": "likely_hallucinated",
        "type": "fabricated_work",
        "confidence": 1 - best["overall"],
        "note": f"No convincing match across {queried_ok} scholarly sources.",
    }
