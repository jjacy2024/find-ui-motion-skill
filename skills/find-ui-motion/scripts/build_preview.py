#!/usr/bin/env python3
"""Build a self-contained synthetic direction board from local motion results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from catalog_lib import SKILL_ROOT, atomic_write_bytes, search_catalog


TEMPLATE = SKILL_ROOT / "assets" / "preview.html"
PLACEHOLDER = "__FIND_UI_MOTION_DATA__"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--stack")
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 12:
        raise SystemExit("--limit must be between 1 and 12")

    data = search_catalog(args.query, stack=args.stack, limit=args.limit, sites_per_motion=1)
    preview_data = {
        "query": data["query"],
        "catalog_version": data["catalog_version"],
        "generated_note": "Local synthesis only. These generic shapes are not source-site evidence.",
        "matches": [
            {
                "score": match["score"],
                "motion": {
                    key: match["motion"][key]
                    for key in (
                        "id",
                        "category",
                        "labels",
                        "targets",
                        "triggers",
                        "feel",
                        "channels",
                        "search_terms",
                    )
                },
            }
            for match in data["matches"]
        ],
    }
    template = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        raise SystemExit("preview template placeholder is missing")
    payload = json.dumps(preview_data, ensure_ascii=False).replace("</", "<\\/")
    output = template.replace(PLACEHOLDER, payload)
    destination = args.output.expanduser().resolve()
    atomic_write_bytes(destination, output.encode("utf-8"))
    print(
        json.dumps(
            {
                "status": "pass",
                "output": str(destination),
                "motion_count": len(preview_data["matches"]),
                "catalog_version": data["catalog_version"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
