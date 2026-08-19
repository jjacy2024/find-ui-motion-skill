#!/usr/bin/env python3
"""Validate a catalog and create its small immutable release manifest."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO_ROOT / "skills" / "find-ui-motion"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from catalog_lib import (  # noqa: E402
    atomic_write_bytes,
    dump_json_bytes,
    load_examples,
    load_motions,
    sha256_bytes,
    validate_catalog_data,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=SKILL_ROOT / "references" / "sites.json")
    parser.add_argument("--catalog-url", required=True)
    parser.add_argument("--examples", type=Path)
    parser.add_argument("--examples-url")
    parser.add_argument("--min-skill-version", default="0.1.0")
    parser.add_argument("--output-manifest", type=Path, required=True)
    parser.add_argument("--added", type=int, default=0)
    parser.add_argument("--removed", type=int, default=0)
    parser.add_argument("--updated", type=int, default=0)
    args = parser.parse_args()

    parsed = urlparse(args.catalog_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise SystemExit("--catalog-url must be an HTTPS URL")
    payload = args.catalog.read_bytes()
    catalog = json.loads(payload.decode("utf-8"))
    errors, warnings = validate_catalog_data(catalog)
    if errors:
        print(json.dumps({"status": "fail", "errors": errors}, ensure_ascii=False, indent=2))
        return 2
    manifest = {
        "catalog_version": catalog["catalog_version"],
        "schema_version": catalog["schema_version"],
        "min_skill_version": args.min_skill_version,
        "published_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "catalog_url": args.catalog_url,
        "sha256": sha256_bytes(payload),
        "summary": {"added": args.added, "removed": args.removed, "updated": args.updated},
    }
    example_count = None
    if (args.examples is None) != (args.examples_url is None):
        raise SystemExit("--examples and --examples-url must be provided together")
    if args.examples is not None:
        example_url = urlparse(args.examples_url)
        if example_url.scheme != "https" or not example_url.hostname:
            raise SystemExit("--examples-url must be an HTTPS URL")
        motions, motion_errors = load_motions()
        examples, example_errors = load_examples(
            args.examples,
            site_ids={site["id"] for site in catalog["sites"]},
            motion_ids={motion["id"] for motion in motions},
        )
        all_example_errors = motion_errors + example_errors
        if all_example_errors:
            print(json.dumps({"status": "fail", "errors": all_example_errors}, ensure_ascii=False, indent=2))
            return 2
        examples_payload = args.examples.read_bytes()
        manifest["examples_url"] = args.examples_url
        manifest["examples_sha256"] = sha256_bytes(examples_payload)
        example_count = len(examples)
    atomic_write_bytes(args.output_manifest, dump_json_bytes(manifest))
    print(
        json.dumps(
            {
                "status": "pass",
                "manifest": str(args.output_manifest.resolve()),
                "catalog_version": catalog["catalog_version"],
                "site_count": len(catalog["sites"]),
                "example_count": example_count,
                "warnings": warnings,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
