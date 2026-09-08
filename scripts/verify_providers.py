#!/usr/bin/env python3
"""Measure verified_on freshness and probe active provider catalogs.

Scheduled drift detector (Issue #3 Item 5): queries provider endpoints
(starting with OpenRouter /api/v1/models) to detect retired slugs and stale verified_on
dates without blocking PR CI. Report-only; does not auto-mutate data.
"""
import argparse
import datetime
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
MAX_AGE_DAYS = 90


def fetch_openrouter_models(timeout_s: int = 15) -> set:
    req = urllib.request.Request(
        OPENROUTER_MODELS_URL,
        headers={"User-Agent": "HiQS-Model-Catalog-Verifier/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {m["id"] for m in data.get("data", [])}
    except Exception as exc:
        print(f"WARN: could not fetch OpenRouter models: {exc}", file=sys.stderr)
        return set()


def verify(models_path: Path, offline: bool = False) -> dict:
    models = json.loads(models_path.read_text())
    today = datetime.date.today()

    openrouter_live = set()
    if not offline:
        openrouter_live = fetch_openrouter_models()

    results = {
        "verified_count": 0,
        "null_count": 0,
        "stale_count": 0,
        "active_live_count": 0,
        "missing_live_count": 0,
        "entries": []
    }

    for model_key, model_data in sorted(models.items()):
        provider = model_data.get("provider", "unknown")
        status = model_data.get("status", "ga")
        for target, target_data in model_data.get("targets", {}).items():
            model_id = target_data["id"]
            vo = target_data.get("verified_on")
            is_stale = False
            age_days = None

            if vo:
                results["verified_count"] += 1
                try:
                    d = datetime.date.fromisoformat(vo)
                    age_days = (today - d).days
                    if age_days > MAX_AGE_DAYS:
                        is_stale = True
                        results["stale_count"] += 1
                except ValueError:
                    is_stale = True
            else:
                results["null_count"] += 1

            live_status = "unprobed"
            if target == "openrouter" and openrouter_live:
                # Check base slug without optional :free or variant suffix
                base_id = model_id.split(":")[0]
                if model_id in openrouter_live or base_id in openrouter_live:
                    live_status = "active"
                    results["active_live_count"] += 1
                else:
                    live_status = "missing"
                    results["missing_live_count"] += 1

            results["entries"].append({
                "model_key": model_key,
                "target": target,
                "provider": provider,
                "status": status,
                "id": model_id,
                "verified_on": vo,
                "age_days": age_days,
                "is_stale": is_stale,
                "live_status": live_status
            })

    return results


def format_markdown(report: dict) -> str:
    lines = [
        "## Model Catalog Provider Verification Report",
        f"**Date:** {datetime.date.today().isoformat()}",
        "",
        "### Summary",
        f"- **Total pins probed:** {len(report['entries'])}",
        f"- **Pins with verified_on date:** {report['verified_count']}",
        f"- **Pins unverified (null):** {report['null_count']}",
        f"- **Stale pins (> {MAX_AGE_DAYS} days):** {report['stale_count']}",
        f"- **OpenRouter active in live catalog:** {report['active_live_count']}",
        f"- **OpenRouter missing from live catalog:** {report['missing_live_count']}",
        "",
        "### Pin Status Details",
        "| Model Key | Target | Model ID | Status | Verified On | Age | Live Status |",
        "|---|---|---|---|---|---|---|"
    ]

    for e in report["entries"]:
        vo_str = e["verified_on"] or "*null*"
        age_str = f"{e['age_days']}d" if e["age_days"] is not None else "-"
        lines.append(
            f"| `{e['model_key']}` | {e['target']} | `{e['id']}` | {e['status']} | {vo_str} | {age_str} | {e['live_status']} |"
        )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, default=ROOT / "data" / "models.json")
    parser.add_argument("--output", type=Path, help="Path to write report")
    parser.add_argument("--json", action="store_true", help="Emit raw JSON")
    parser.add_argument("--offline", action="store_true", help="Skip live API probes")
    args = parser.parse_args()

    report = verify(args.models, offline=args.offline)

    if args.json:
        out = json.dumps(report, indent=2)
    else:
        out = format_markdown(report)

    if args.output:
        args.output.write_text(out + "\n")
        print(f"Report written to {args.output}")
    else:
        print(out)

    return 0


if __name__ == "__main__":
    sys.exit(main())
