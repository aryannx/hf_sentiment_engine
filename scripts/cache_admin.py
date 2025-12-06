#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import List

from src.core.logging_utils import get_logger

LOG = get_logger("cache_admin")


def list_entries(root: Path, provider: str | None, symbol: str | None) -> List[Path]:
    if not root.exists():
        return []
    if provider:
        root = root / provider
    matches = []
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if symbol and symbol not in path.as_posix():
            continue
        matches.append(path)
    return matches


def purge(root: Path, provider: str | None, symbol: str | None) -> int:
    matches = list_entries(root, provider, symbol)
    count = 0
    for path in matches:
        try:
            path.unlink()
            count += 1
        except Exception:  # pragma: no cover - defensive
            LOG.error({"event": "purge_failed", "path": str(path)})
    # clean empty dirs
    for dirpath in sorted(root.rglob("*"), reverse=True):
        if dirpath.is_dir() and not any(dirpath.iterdir()):
            shutil.rmtree(dirpath, ignore_errors=True)
    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cache admin utility")
    parser.add_argument(
        "--root",
        default="data/cache",
        help="Cache root directory",
    )
    parser.add_argument(
        "--provider",
        help="Provider folder to target (e.g., finnhub, polygon)",
    )
    parser.add_argument(
        "--symbol",
        help="Optional symbol filter",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List matching cache files instead of purging",
    )
    parser.add_argument(
        "--purge",
        action="store_true",
        help="Delete matching cache files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root)
    if not (args.list or args.purge):
        raise SystemExit("Specify --list or --purge")

    matches = list_entries(root, args.provider, args.symbol)
    if args.list:
        for path in matches:
            print(path)
        LOG.info({"event": "cache_list", "count": len(matches)})
    if args.purge:
        count = purge(root, args.provider, args.symbol)
        LOG.info({"event": "cache_purge", "deleted": count})


if __name__ == "__main__":
    main()

