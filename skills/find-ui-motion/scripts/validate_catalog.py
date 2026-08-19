#!/usr/bin/env python3
"""Validate the bundled or supplied website and motion catalogs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from catalog_lib import (
    BUNDLED_CATALOG,
    EXAMPLES_FILE,
    MOTIONS_FILE,
    load_examples,
    load_json,
    load_motions,
    validate_catalog_data,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=BUNDLED_CATALOG)
    parser.add_argument("--motions", type=Path, default=MOTIONS_FILE)
    parser.add_argument("--examples", type=Path, default=EXAMPLES_FILE)
    args = parser.parse_args()

    try:
        catalog = load_json(args.catalog)
        errors, warnings = validate_catalog_data(catalog)
        motions, motion_errors = load_motions(args.motions)
        errors.extend(motion_errors)
        examples, example_errors = load_examples(
            args.examples,
            site_ids={site["id"] for site in catalog.get("sites", [])},
            motion_ids={motion["id"] for motion in motions},
        )
        errors.extend(example_errors)
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "fail", "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 2

    result = {
        "status": "pass" if not errors else "fail",
        "catalog": str(args.catalog),
        "catalog_version": catalog.get("catalog_version") if isinstance(catalog, dict) else None,
        "site_count": len(catalog.get("sites", [])) if isinstance(catalog, dict) else 0,
        "motion_count": len(motions),
        "example_count": len(examples),
        "warnings": warnings,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
