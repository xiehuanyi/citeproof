#!/usr/bin/env python3
"""Copy the CiteProof agent skill into local Grok / Codex skill dirs."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "skills" / "citeproof"


def _destinations() -> list[Path]:
    home = Path.home()
    grok = Path.home() / ".grok"
    return [
        grok / "skills" / "citeproof",
        home / ".codex" / "skills" / "citeproof",
        home / ".agents" / "skills" / "citeproof",
    ]


def main() -> int:
    if not (SRC / "SKILL.md").is_file():
        print("citeproof: skill source missing", SRC)
        return 1
    copied = 0
    for dest in _destinations():
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(SRC, dest)
        print(f"installed {dest}")
        copied += 1
    if not copied:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
