from __future__ import annotations

import re
from urllib.parse import quote, urlencode

from .http import gather, request_json, request_text
from .normalize import normalize_arxiv, normalize_doi, normalize_text, strip_latex


def _crossref_year(item: dict):
    parts = ((item.get("issued") or item.get("published") or {}).get("date-parts") or [[None]])[0]
    return int(parts[0]) if parts and parts[0] else None


def _crossref_authors(item: dict) -> list[str]:
    out = []
    for a in item.get("author") or []:
        name = " ".join(p for p in [a.get("given"), a.get("family")] if p).strip()
        if name:
            out.append(name)
    return out


def resolve_crossref(ref: dict) -> list[dict]:
    def doi():
        if not ref.get("doi"):
            return []
        data = request_json(f"https://api.crossref.org/works/{quote(ref['doi'])}")
        item = (data or {}).get("message")
        return [_to_crossref(item, "doi")] if item else []

    def search():
        if not ref.get("title"):
            return []
        params = urlencode(
            {
                "query.bibliographic": " ".join(
                    str(p) for p in [ref.get("title"), (ref.get("author_last_names") or [""])[0], ref.get("year") or ""] if p
                ),
                "rows": "5",
                "select": "DOI,title,author,issued,published,container-title,publisher,URL",
                "mailto": "citeproof@pocketplay.win",
            }
        )
        data = request_json(f"https://api.crossref.org/works?{params}")
        return [_to_crossref(item, "search") for item in ((data or {}).get("message") or {}).get("items") or []]

    return gather([doi, search])


def _to_crossref(item: dict, via: str) -> dict:
    return {
        "source": "crossref",
        "via": via,
        "title": strip_latex((item.get("title") or [""])[0]),
        "authors": _crossref_authors(item),
        "year": _crossref_year(item),
        "venue": strip_latex((item.get("container-title") or [""])[0] or item.get("publisher") or ""),
        "doi": normalize_doi(item.get("DOI")),
        "arxiv_id": None,
        "url": item.get("URL") or (f"https://doi.org/{item['DOI']}" if item.get("DOI") else None),
    }


def resolve_openalex(ref: dict) -> list[dict]:
    select = "id,doi,display_name,publication_year,authorships,primary_location,ids,type,is_retracted,cited_by_count"

    def doi():
        if not ref.get("doi"):
            return []
        data = request_json(
            f"https://api.openalex.org/works/doi:{quote(ref['doi'])}?select={select}&mailto=citeproof@pocketplay.win"
        )
        cand = _to_openalex(data, "doi")
        return [cand] if cand else []

    def search():
        if not ref.get("title"):
            return []
        params = urlencode(
            {
                "filter": f"display_name.search:{ref['title'].replace(',', ' ')}",
                "per_page": "8",
                "select": select,
                "mailto": "citeproof@pocketplay.win",
            }
        )
        data = request_json(f"https://api.openalex.org/works?{params}")
        return [c for c in (_to_openalex(w, "title") for w in (data or {}).get("results") or []) if c]

    return gather([doi, search])


def _to_openalex(work, via: str):
    if not work or not work.get("display_name"):
        return None
    ids = work.get("ids") or {}
    venue = ((work.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
    authors = [a.get("author", {}).get("display_name") for a in work.get("authorships") or [] if a.get("author")]
    return {
        "source": "openalex",
        "via": via,
        "title": strip_latex(work["display_name"]),
        "authors": [a for a in authors if a],
        "year": work.get("publication_year"),
        "venue": strip_latex(venue),
        "doi": normalize_doi(work.get("doi") or ids.get("doi")),
        "arxiv_id": normalize_arxiv(ids.get("arxiv") or ""),
        "url": ids.get("openalex") or work.get("id"),
        "retracted": bool(work.get("is_retracted")),
    }


S2_FIELDS = "title,year,authors,venue,externalIds,url,publicationTypes,publicationDate"


def resolve_semanticscholar(ref: dict) -> list[dict]:
    def by_id(kind: str, value: str, via: str):
        data = request_json(
            f"https://api.semanticscholar.org/graph/v1/paper/{kind}:{quote(value)}?fields={S2_FIELDS}"
        )
        cand = _to_s2(data, via)
        return [cand] if cand else []

    def match():
        if not ref.get("title"):
            return []
        data = request_json(
            "https://api.semanticscholar.org/graph/v1/paper/search/match?"
            + urlencode({"query": ref["title"], "fields": S2_FIELDS})
        )
        cand = _to_s2((data or {}).get("data", [None])[0] if isinstance((data or {}).get("data"), list) else data, "title-match")
        return [cand] if cand else []

    jobs = []
    if ref.get("doi"):
        jobs.append(lambda: by_id("DOI", ref["doi"], "doi"))
    if ref.get("arxiv_id"):
        jobs.append(lambda: by_id("ARXIV", ref["arxiv_id"], "arxiv"))
    jobs.append(match)
    return gather(jobs)


def _to_s2(paper, via: str):
    if not paper or paper.get("error") or not paper.get("title"):
        return None
    ext = paper.get("externalIds") or {}
    return {
        "source": "semanticscholar",
        "via": via,
        "title": strip_latex(paper["title"]),
        "authors": [a.get("name") for a in paper.get("authors") or [] if a.get("name")],
        "year": paper.get("year"),
        "venue": strip_latex(paper.get("venue") or ""),
        "doi": normalize_doi(ext.get("DOI")),
        "arxiv_id": normalize_arxiv(ext.get("ArXiv")),
        "url": paper.get("url") or (f"https://www.semanticscholar.org/paper/{paper['paperId']}" if paper.get("paperId") else None),
    }


def resolve_arxiv(ref: dict) -> list[dict]:
    def by_id():
        if not ref.get("arxiv_id"):
            return []
        xml = request_text(f"https://export.arxiv.org/api/query?id_list={quote(ref['arxiv_id'])}")
        return [_to_arxiv(e, "id") for e in _arxiv_entries(xml or "")]

    def search():
        if not ref.get("title"):
            return []
        q = f'ti:"{ref["title"].replace(chr(34), "")}"'
        xml = request_text(
            "https://export.arxiv.org/api/query?search_query=" + quote(q) + "&start=0&max_results=5"
        )
        return [_to_arxiv(e, "title") for e in _arxiv_entries(xml or "")]

    return gather([by_id, search])


def _tag(block: str, name: str) -> str:
    m = re.search(rf"<{name}[^>]*>([\s\S]*?)</{name}>", block, re.I)
    return _decode_xml(m.group(1) if m else "")


def _decode_xml(value: str) -> str:
    text = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", value or "", flags=re.S)
    return (
        text.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&amp;", "&")
        .strip()
    )


def _arxiv_entries(xml: str) -> list[str]:
    return [chunk.split("</entry>", 1)[0] for chunk in xml.split("<entry>")[1:]]


def _to_arxiv(block: str, via: str) -> dict:
    ident = _tag(block, "id")
    published = _tag(block, "published")
    authors = [_decode_xml(m.group(1)) for m in re.finditer(r"<name>([\s\S]*?)</name>", block, re.I)]
    return {
        "source": "arxiv",
        "via": via,
        "title": re.sub(r"\s+", " ", strip_latex(_tag(block, "title"))),
        "authors": authors,
        "year": int(published[:4]) if published[:4].isdigit() else None,
        "venue": "arXiv",
        "doi": None,
        "arxiv_id": normalize_arxiv(ident),
        "url": ident.replace("http://", "https://") or None,
    }


def _lit(node) -> str:
    if not node:
        return ""
    if isinstance(node, dict):
        return str(node.get("value") or "")
    return str(node)


def resolve_dblp(ref: dict) -> list[dict]:
    def sparql(query: str) -> list[dict]:
        data = request_json(
            "https://sparql.dblp.org/sparql?query=" + quote(query) + "&format=json",
            headers={"Accept": "application/sparql-results+json"},
            timeout=14.0,
        )
        return [_to_dblp(row) for row in ((data or {}).get("results") or {}).get("bindings") or [] if _lit(row.get("title"))]

    def by_doi():
        if not ref.get("doi"):
            return []
        return sparql(
            f"""PREFIX dblp: <https://dblp.org/rdf/schema#>
SELECT ?paper ?title ?year ?doi ?venue (GROUP_CONCAT(DISTINCT ?aname; separator="|") AS ?authors) WHERE {{
  ?paper dblp:doi <https://doi.org/{ref['doi']}> ; dblp:title ?title .
  OPTIONAL {{ ?paper dblp:yearOfPublication ?year }}
  OPTIONAL {{ ?paper dblp:doi ?doi }}
  OPTIONAL {{ ?paper dblp:publishedIn ?venue }}
  OPTIONAL {{ ?paper dblp:authoredBy/dblp:primaryCreatorName ?aname }}
}}
GROUP BY ?paper ?title ?year ?doi ?venue
LIMIT 5"""
        )

    def by_title():
        if not ref.get("title"):
            return []
        n = normalize_text(ref["title"]).replace('"', "")
        rows = sparql(_title_query(f'FILTER(LCASE(REPLACE(STR(?title), "[.]$", "")) = "{n}")'))
        if not rows:
            max_len = min(160, len(n) + 18)
            rows = sparql(_title_query(f'FILTER(CONTAINS(LCASE(STR(?title)), "{n}") && STRLEN(STR(?title)) <= {max_len})'))
        return rows

    return gather([by_doi, by_title])


def _title_query(filt: str) -> str:
    return f"""PREFIX dblp: <https://dblp.org/rdf/schema#>
SELECT ?paper ?title ?year ?doi ?venue (GROUP_CONCAT(DISTINCT ?aname; separator="|") AS ?authors) WHERE {{
  ?paper dblp:title ?title .
  {filt}
  OPTIONAL {{ ?paper dblp:yearOfPublication ?year }}
  OPTIONAL {{ ?paper dblp:doi ?doi }}
  OPTIONAL {{ ?paper dblp:publishedIn ?venue }}
  OPTIONAL {{ ?paper dblp:authoredBy/dblp:primaryCreatorName ?aname }}
}}
GROUP BY ?paper ?title ?year ?doi ?venue
LIMIT 8"""


def _to_dblp(row: dict) -> dict:
    title = strip_latex(_lit(row.get("title"))).rstrip(".")
    authors = [p.strip() for p in _lit(row.get("authors")).split("|") if p.strip()]
    year_raw = _lit(row.get("year"))
    return {
        "source": "dblp",
        "via": "sparql",
        "title": title,
        "authors": authors,
        "year": int(year_raw[:4]) if year_raw[:4].isdigit() else None,
        "venue": strip_latex(_lit(row.get("venue"))),
        "doi": normalize_doi(_lit(row.get("doi"))),
        "arxiv_id": None,
        "url": _lit(row.get("paper")) or None,
    }


PROVIDERS = [
    {"id": "crossref", "label": "Crossref", "resolve": resolve_crossref},
    {"id": "dblp", "label": "DBLP", "resolve": resolve_dblp},
    {"id": "semanticscholar", "label": "Semantic Scholar", "resolve": resolve_semanticscholar},
    {"id": "openalex", "label": "OpenAlex", "resolve": resolve_openalex},
    {"id": "arxiv", "label": "arXiv", "resolve": resolve_arxiv},
]
