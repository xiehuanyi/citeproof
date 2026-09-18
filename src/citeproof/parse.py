from __future__ import annotations

import re

_ENTRY_RE = re.compile(r"@(\w+)\s*\{")


def _skip_ws(s: str, i: int) -> int:
    while i < len(s) and s[i].isspace():
        i += 1
    return i


def _read_braced(s: str, i: int) -> tuple[str, int]:
    if i >= len(s) or s[i] != "{":
        return "", i
    depth = 0
    j = i
    while j < len(s):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1 : j], j + 1
        j += 1
    return s[i + 1 :], j


def _read_quoted(s: str, i: int) -> tuple[str, int]:
    j = i + 1
    out = []
    while j < len(s):
        if s[j] == "\\" and j + 1 < len(s):
            out.append(s[j + 1])
            j += 2
            continue
        if s[j] == '"':
            return "".join(out), j + 1
        out.append(s[j])
        j += 1
    return "".join(out), j


def _read_bare(s: str, i: int) -> tuple[str, int]:
    j = i
    while j < len(s) and s[j] not in " \t\n\r,#}":
        j += 1
    return s[i:j], j


def _read_value(s: str, i: int) -> tuple[str, int]:
    i = _skip_ws(s, i)
    parts: list[str] = []
    while i < len(s):
        i = _skip_ws(s, i)
        if i >= len(s):
            break
        if s[i] == "{":
            val, i = _read_braced(s, i)
            parts.append(val)
        elif s[i] == '"':
            val, i = _read_quoted(s, i)
            parts.append(val)
        elif s[i].isalnum() or s[i] in "-+:./":
            val, i = _read_bare(s, i)
            parts.append(val)
        else:
            break
        i = _skip_ws(s, i)
        if i < len(s) and s[i] == "#":
            i += 1
            continue
        break
    return "".join(parts), i


def _parse_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    i = 0
    while i < len(body):
        i = _skip_ws(body, i)
        if i >= len(body) or body[i] == "}":
            break
        start = i
        while i < len(body) and (body[i].isalnum() or body[i] in "-_+"):
            i += 1
        name = body[start:i].lower()
        i = _skip_ws(body, i)
        if i >= len(body) or body[i] != "=":
            i += 1
            continue
        i += 1
        value, i = _read_value(body, i)
        if name:
            fields[name] = value.strip()
        i = _skip_ws(body, i)
        if i < len(body) and body[i] == ",":
            i += 1
    return fields


def parse_bibtex(text: str) -> list[dict]:
    if not isinstance(text, str):
        raise TypeError("Bibliography must be text.")
    src = text.lstrip("\ufeff")
    entries: list[dict] = []
    for match in _ENTRY_RE.finditer(src):
        typ = match.group(1).lower()
        if typ in {"comment", "preamble", "string"}:
            continue
        i = _skip_ws(src, match.end())
        key_start = i
        while i < len(src) and src[i] not in ",}":
            i += 1
        key = src[key_start:i].strip() or f"entry{len(entries) + 1}"
        if i < len(src) and src[i] == ",":
            i += 1
        body, _end = _read_braced("{" + src[i:], 0)
        entries.append({"key": key, "type": typ, "fields": _parse_fields(body)})
    return entries
