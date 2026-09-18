from __future__ import annotations

import re
from urllib.parse import quote

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
ARXIV_RE = re.compile(r"(?:arxiv[:\s]*)?(\d{4}\.\d{4,5})(v\d+)?", re.I)


def strip_latex(value) -> str:
    text = str(value or "")
    text = re.sub(r"\\[a-zA-Z]+\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\s*", "", text)
    text = re.sub(r"[{}$]", "", text)
    text = text.replace("~", " ").replace("\\", "")
    text = re.sub(r"\s+([:,;])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_text(value) -> str:
    text = strip_latex(value).lower()
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize(value) -> list[str]:
    return [tok for tok in normalize_text(value).split(" ") if tok]


def split_authors(raw: str) -> list[str]:
    text = strip_latex(raw)
    if not text:
        return []
    parts = re.split(r"\s+and\s+|\s*;\s+", text, flags=re.I)
    out = []
    for part in parts:
        name = re.sub(r"\s+", " ", part).strip()
        if name and name.lower() not in {"others", "..."}:
            out.append(name)
    return out


def author_last_name(name: str) -> str:
    clean = re.sub(r"\s+", " ", strip_latex(name).replace(".", " ")).strip()
    if not clean:
        return ""
    if "," in clean:
        return normalize_text(clean.split(",", 1)[0])
    parts = [p for p in clean.split(" ") if p]
    return normalize_text(parts[-1] if parts else "")


def normalize_doi(value) -> str | None:
    if not value:
        return None
    text = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", str(value), flags=re.I).strip()
    m = DOI_RE.search(text)
    return m.group(0).rstrip("/").lower() if m else None


def normalize_arxiv(value) -> str | None:
    if not value:
        return None
    m = ARXIV_RE.search(str(value))
    return m.group(1) if m else None


def normalize_entry(entry: dict) -> dict:
    f = entry.get("fields") or {}
    title = strip_latex(f.get("title") or f.get("booktitle") or "")
    authors = split_authors(f.get("author") or f.get("editor") or "")
    year_m = re.search(r"(\d{4})", str(f.get("year") or f.get("date") or ""))
    venue = strip_latex(f.get("journal") or f.get("booktitle") or f.get("publisher") or f.get("howpublished") or f.get("school") or "")
    url = str(f.get("url") or f.get("link") or "").strip()
    doi = normalize_doi(f.get("doi") or "")
    arxiv_id = normalize_arxiv(f.get("eprint") or f.get("arxiv") or "")
    if url:
        doi = doi or normalize_doi(url)
        arxiv_id = arxiv_id or normalize_arxiv(url)
    return {
        "key": entry.get("key"),
        "type": entry.get("type"),
        "title": title,
        "authors": authors,
        "author_last_names": [author_last_name(a) for a in authors if author_last_name(a)],
        "year": int(year_m.group(1)) if year_m else None,
        "venue": venue,
        "doi": doi,
        "arxiv_id": arxiv_id,
        "url": url or None,
    }


def scholar_url(ref: dict) -> str:
    last = (ref.get("author_last_names") or [""])[0]
    q = f"\"{ref.get('title') or ''}\" {last}".strip()
    return "https://scholar.google.com/scholar?q=" + quote(q)
