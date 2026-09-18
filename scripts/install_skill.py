#!/usr/bin/env python3
"""Install the skill, preserving existing installations unless --update is used."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timezone
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


def _install(dest: Path, *, update: bool) -> None:
    if dest.is_symlink() or (dest.exists() and not dest.is_dir()):
        raise OSError(f"refusing to replace a symlink or non-directory: {dest}")
    if dest.exists() and not update:
        print(f"kept existing {dest} (use --update to merge with a backup)")
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    # Prepare the complete merged directory before changing the installed skill.
    with tempfile.TemporaryDirectory(prefix=".citeproof-stage-", dir=dest.parent) as work:
        staged = Path(work) / dest.name
        if dest.exists():
            shutil.copytree(dest, staged, symlinks=True)
        else:
            staged.mkdir()
        for source in sorted(SRC.rglob("*")):
            target = staged / source.relative_to(SRC)
            if source.is_symlink() or target.is_symlink():
                raise OSError(f"refusing to overwrite or follow a bundled-file symlink: {source.relative_to(SRC)}")
            if source.is_dir():
                target.mkdir(exist_ok=True)
            elif source.is_file():
                if target.is_dir():
                    raise OSError(f"a custom directory conflicts with a bundled file: {source.relative_to(SRC)}")
                shutil.copy2(source, target)

        backup = None
        if dest.exists():
            backup_root = dest.parent.parent / "skill-backups"
            backup_root.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = backup_root / f"{dest.name}-{stamp}-{uuid.uuid4().hex[:8]}"
            dest.rename(backup)
            print(f"backup {backup}")
        try:
            staged.rename(dest)
        except OSError:
            if backup is not None and not dest.exists() and not dest.is_symlink():
                backup.rename(dest)
            raise
    print(f"installed {dest}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="Merge updates into existing skills, keeping a full backup and custom files")
    args = parser.parse_args(argv)
    if not (SRC / "SKILL.md").is_file():
        print("citeproof: skill source missing", SRC)
        return 1
    failed = False
    for dest in _destinations():
        try:
            _install(dest, update=args.update)
        except OSError as err:
            print(f"citeproof: could not install {dest}: {err}", file=sys.stderr)
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
