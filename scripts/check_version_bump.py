#!/usr/bin/env python3
"""Fail-closed semver/date gate for versioned JSON data files."""
import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def die(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], text=True, capture_output=True)


def metadata(raw: str, label: str):
    try:
        value = json.loads(raw)
        version, updated = value["version"], value["updated"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(f"{label} is not a catalog with version/updated: {exc}") from exc
    match = SEMVER.fullmatch(version) if isinstance(version, str) else None
    if not match:
        raise ValueError(f"{label} version is not semver")
    if not isinstance(updated, str) or not DATE.fullmatch(updated):
        raise ValueError(f"{label} updated is not YYYY-MM-DD")
    try:
        parsed_date = datetime.date.fromisoformat(updated)
    except ValueError as exc:
        raise ValueError(f"{label} updated is not a real date") from exc
    return tuple(map(int, match.groups())), version, parsed_date


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--path", required=True)
    parser.add_argument("--initial-version")
    parser.add_argument("--today", default=datetime.datetime.now(datetime.timezone.utc).date().isoformat())
    args = parser.parse_args()

    if git("rev-parse", "--verify", f"{args.base_ref}^{{tree}}").returncode:
        return die(f"base ref {args.base_ref!r} is unavailable")
    diff = git("diff", "--quiet", args.base_ref, "HEAD", "--", args.path)
    if diff.returncode == 0:
        print(f"OK: {args.path} unchanged")
        return 0
    if diff.returncode != 1:
        return die(f"git diff failed: {diff.stderr.strip()}")
    try:
        head_tuple, head_version, head_date = metadata(Path(args.path).read_text(encoding="utf-8"), "head")
        today = datetime.date.fromisoformat(args.today)
    except (OSError, ValueError) as exc:
        return die(str(exc))
    if head_date > today:
        return die(f"updated {head_date} is in the future")

    listing = git("ls-tree", "--name-only", args.base_ref, "--", args.path)
    if listing.returncode:
        return die(f"cannot inspect base tree: {listing.stderr.strip()}")
    if not listing.stdout.strip():
        if not args.initial_version:
            return die(f"{args.path} did not exist at the base ref")
        if head_version != args.initial_version:
            return die(f"first publication must use version {args.initial_version}")
        print(f"OK: first publication of {args.path} at {head_version}")
        return 0

    shown = git("show", f"{args.base_ref}:{args.path}")
    if shown.returncode:
        return die(f"cannot read base catalog: {shown.stderr.strip()}")
    try:
        base_tuple, base_version, base_date = metadata(shown.stdout, "base")
    except ValueError as exc:
        return die(str(exc))
    if head_tuple <= base_tuple:
        return die(f"version must increase monotonically ({base_version} -> {head_version})")
    if head_date <= base_date:
        return die(f"updated must advance ({base_date} -> {head_date})")
    print(f"OK: {args.path} {base_version}/{base_date} -> {head_version}/{head_date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
