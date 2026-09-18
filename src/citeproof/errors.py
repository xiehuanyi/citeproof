from __future__ import annotations

from urllib.parse import urlparse


class HttpError(Exception):
    def __init__(self, code: str, http_status: int | None = None, host: str | None = None, url: str | None = None):
        super().__init__(code)
        self.code = code
        self.http_status = http_status
        self.host = host
        self.url = url


def host_of(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return urlparse(url).hostname
    except Exception:
        return None


def looks_like_html(text: str) -> bool:
    s = (text or "").strip()[:280].lower()
    return (
        s.startswith("<!doctype")
        or s.startswith("<html")
        or "you're not a bot" in s
        or "making sure you" in s
        or "anubis" in s
    )


def classify_error(err, host: str | None = None, url: str | None = None) -> dict:
    resolved = host or getattr(err, "host", None) or host_of(url)
    status = getattr(err, "http_status", None) or getattr(err, "status", None)
    if isinstance(err, HttpError) and err.code:
        return {"code": err.code, "http_status": err.http_status, "host": err.host or resolved}
    if isinstance(err, TimeoutError) or getattr(err, "code", None) == "TIMEOUT":
        return {"code": "timeout", "http_status": None, "host": resolved}
    if status == 429:
        return {"code": "rate_limited", "http_status": 429, "host": resolved}
    if status == 403:
        return {"code": "http_403", "http_status": 403, "host": resolved}
    if status == 401:
        return {"code": "http_401", "http_status": 401, "host": resolved}
    if status == 404:
        return {"code": "http_404", "http_status": 404, "host": resolved}
    if status and int(status) >= 500:
        return {"code": "http_5xx", "http_status": int(status), "host": resolved}
    if status:
        return {"code": "http_other", "http_status": int(status), "host": resolved}
    msg = f"{err}"
    if any(tok in msg.lower() for tok in ("timed out", "timeout")):
        return {"code": "timeout", "http_status": None, "host": resolved}
    if any(tok in msg.lower() for tok in ("name or service not known", "temporary failure", "connection refused", "network")):
        return {"code": "network", "http_status": None, "host": resolved}
    return {"code": "unknown", "http_status": status, "host": resolved}


def serialize_error(err, host: str | None = None) -> dict:
    info = classify_error(err, host=host)
    return {"code": info["code"], "httpStatus": info.get("http_status"), "host": info.get("host")}


_RANK = {
    "rate_limited": 1,
    "http_5xx": 2,
    "http_403": 3,
    "timeout": 7,
    "network": 8,
    "parse": 10,
    "blocked": 5,
    "unknown": 12,
}


def pick_worst(errors: list) -> object:
    return sorted(errors, key=lambda e: _RANK.get(classify_error(e)["code"], 50))[0]
