from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from typing import Callable

from .errors import HttpError, classify_error, host_of, looks_like_html, pick_worst

UA = "CiteProof/0.1 (https://citeproof.pocketplay.win; mailto:citeproof@pocketplay.win)"
_INTERVALS = {
    "api.crossref.org": 0.16,
    "api.openalex.org": 0.14,
    "api.semanticscholar.org": 0.35,
    "export.arxiv.org": 0.35,
    "arxiv.org": 0.35,
    "sparql.dblp.org": 0.28,
    "dblp.org": 0.4,
}
_last: dict[str, float] = {}
_lock = threading.Lock()
_http_gate = threading.BoundedSemaphore(8)


def _pace(url: str) -> None:
    host = host_of(url) or ""
    wait_for = _INTERVALS.get(host, 0.12)
    with _lock:
        prev = _last.get(host, 0.0)
        delay = prev + wait_for - time.monotonic()
        _last[host] = time.monotonic() + max(delay, 0)
    if delay > 0:
        time.sleep(delay)


def request_text(url: str, timeout: float = 12.0, headers: dict | None = None, retries: int = 1) -> str | None:
    host = host_of(url)
    last_err: Exception | None = None
    hdrs = {"User-Agent": UA, "Accept": "application/json, application/atom+xml, application/xml, text/xml, */*"}
    if headers:
        hdrs.update(headers)
    for attempt in range(retries + 1):
        _pace(url)
        req = urllib.request.Request(url, headers=hdrs, method="GET")
        _http_gate.acquire()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as res:
                body = res.read().decode("utf-8", "replace")
                if looks_like_html(body):
                    raise HttpError("blocked", http_status=getattr(res, "status", 200), host=host, url=url)
                return body
        except urllib.error.HTTPError as err:
            raw = err.read().decode("utf-8", "replace") if err.fp else ""
            if err.code == 404:
                return None
            if err.code == 429 and attempt < retries:
                time.sleep(min(float(err.headers.get("Retry-After") or 1.6), 4.0))
                last_err = HttpError("rate_limited", http_status=429, host=host, url=url)
                continue
            last_err = HttpError(classify_error(err, host=host)["code"], http_status=err.code, host=host, url=url)
            if raw and looks_like_html(raw) and err.code not in {401, 403, 429}:
                last_err = HttpError("blocked", http_status=err.code, host=host, url=url)
        except TimeoutError as err:
            last_err = HttpError("timeout", host=host, url=url)
        except Exception as err:
            last_err = HttpError(classify_error(err, host=host, url=url)["code"], host=host, url=url)
        finally:
            _http_gate.release()
        if last_err and getattr(last_err, "code", "") in {"http_403", "blocked"}:
            break
        if attempt < retries:
            time.sleep(0.4 * (attempt + 1))
    raise last_err or HttpError("unknown", host=host, url=url)


def request_json(url: str, **opts):
    body = request_text(url, **opts)
    if body is None:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise HttpError("blocked" if looks_like_html(body) else "parse", host=host_of(url), url=url)


def gather(jobs: list[Callable[[], list]]) -> list:
    out: list = []
    errors: list = []
    for job in jobs:
        try:
            part = job()
            if part:
                out.extend(part)
        except Exception as err:
            errors.append(err)
    if out:
        return out
    if errors:
        worst = pick_worst(errors)
        if isinstance(worst, HttpError):
            raise worst
        info = classify_error(worst)
        raise HttpError(info["code"], http_status=info.get("http_status"), host=info.get("host"))
    return []
