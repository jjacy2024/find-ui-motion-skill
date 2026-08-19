#!/usr/bin/env python3
"""Report source distribution and enforce a dominant-source ceiling."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXAMPLES = REPO_ROOT / "skills" / "find-ui-motion" / "references" / "examples.jsonl"


def analyze(records: list[dict], max_source_share: float) -> dict:
    counts = Counter(record["site_id"] for record in records)
    total = len(records)
    sources = [
        {"site_id": site_id, "count": count, "share": round(count / total, 4) if total else 0.0}
        for site_id, count in counts.most_common()
    ]
    dominant = sources[0] if sources else {"site_id": None, "count": 0, "share": 0.0}
    return {
        "total": total,
        "source_count": len(sources),
        "dominant_source": dominant,
        "max_source_share": max_source_share,
        "status": "pass" if total and dominant["share"] <= max_source_share else "fail",
        "sources": sources,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    parser.add_argument("--max-source-share", type=float, default=0.80)
    args = parser.parse_args()
    if not 0.1 <= args.max_source_share <= 1.0:
        parser.error("--max-source-share must be between 0.1 and 1.0")
    records = [json.loads(line) for line in args.examples.read_text(encoding="utf-8").splitlines() if line.strip()]
    report = analyze(records, args.max_source_share)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
