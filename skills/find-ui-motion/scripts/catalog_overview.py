#!/usr/bin/env python3
"""Report bundled Catalog counts and optionally render its source-site links."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from catalog_lib import EXAMPLES_FILE, BUNDLED_CATALOG, load_examples, load_json, validate_catalog_data


def build_catalog_overview(
    *,
    sites_path: Path = BUNDLED_CATALOG,
    examples_path: Path = EXAMPLES_FILE,
    include_sites: bool = False,
) -> dict[str, Any]:
    catalog = load_json(sites_path)
    catalog_errors, _ = validate_catalog_data(catalog)
    if catalog_errors:
        raise ValueError("invalid bundled catalog: " + "; ".join(catalog_errors))

    site_ids = {site["id"] for site in catalog["sites"]}
    examples, example_errors = load_examples(examples_path, site_ids=site_ids)
    if example_errors:
        raise ValueError("invalid bundled examples: " + "; ".join(example_errors))

    version = str(catalog["catalog_version"])
    source_count = len(catalog["sites"])
    case_count = len(examples)
    announcement = (
        f"当前版本 {version} 的内置清单共收录 {source_count} 个来源网站，"
        f"案例库中共有 {case_count} 个案例。"
        "如果你有兴趣，可以查看网站清单，并手动点击链接访问任意来源网站。"
    )
    result: dict[str, Any] = {
        "catalog_version": version,
        "source_count": source_count,
        "case_count": case_count,
        "announcement": announcement,
    }
    if include_sites:
        result["sites"] = [
            {
                "name": site["name"],
                "homepage": site["homepage"],
                "status": site["status"],
            }
            for site in catalog["sites"]
        ]
    return result


def _escape_markdown_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def render_markdown(overview: dict[str, Any]) -> str:
    lines = [overview["announcement"]]
    sites = overview.get("sites")
    if sites is not None:
        lines.extend(["", "### 网站清单", ""])
        for site in sites:
            label = _escape_markdown_label(str(site["name"]))
            status = "" if site["status"] == "active" else f" · {site['status']}"
            lines.append(f"- [{label}]({site['homepage']}){status}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show the bundled find-ui-motion Catalog size and optional source links."
    )
    parser.add_argument("--list-sites", action="store_true", help="Include every source homepage.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--sites", type=Path, default=BUNDLED_CATALOG)
    parser.add_argument("--examples", type=Path, default=EXAMPLES_FILE)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    overview = build_catalog_overview(
        sites_path=args.sites,
        examples_path=args.examples,
        include_sites=args.list_sites,
    )
    if args.format == "markdown":
        print(render_markdown(overview))
    else:
        print(json.dumps(overview, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
