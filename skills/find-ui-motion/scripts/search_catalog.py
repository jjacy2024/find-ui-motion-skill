#!/usr/bin/env python3
"""Search the local motion catalog with deterministic retrieval escalation."""

from __future__ import annotations

import argparse
import json
import sys

from catalog_lib import ALLOWED_CAPABILITIES, ALLOWED_KINDS, search_catalog


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("query", help="Natural-language motion request in Chinese or English")
    result.add_argument("--stack", help="Required target stack, for example react, css, or lottie")
    result.add_argument("--capability", choices=sorted(ALLOWED_CAPABILITIES))
    result.add_argument("--kind", choices=sorted(ALLOWED_KINDS))
    result.add_argument("--limit", type=int, default=6)
    result.add_argument("--sites-per-motion", type=int, default=3)
    result.add_argument("--examples-per-motion", type=int, default=10)
    result.add_argument("--candidate-limit", type=int, default=48, help="Deduplicated staged-recall pool, default 48 and maximum 64")
    result.add_argument(
        "--strategy",
        choices=("auto", "taxonomy", "global", "expanded"),
        default="auto",
        help="auto runs taxonomy, full-index lexical, then local query expansion only as needed",
    )
    result.add_argument("--target-count", type=int, default=8, help="Desired exact local candidates, default 8 and maximum 10")
    result.add_argument("--trace", action="store_true", help="Show local escalation, coverage, and external-search recommendation")
    result.add_argument(
        "--candidate-pool-only",
        action="store_true",
        help="With --json, emit only the deduplicated candidate pool and catalog provenance",
    )
    result.add_argument("--json", action="store_true", help="Emit JSON instead of readable text")
    return result


def render_text(data: dict, *, show_trace: bool = False) -> str:
    lines = [
        f"query: {data['query']}",
        f"catalog: {data['catalog_version']} ({data['catalog_source']})",
        f"retrieval: {data['retrieval_level']} | coverage={data['coverage']['status']} "
        + f"exact={data['coverage']['exact_count']}/{data['coverage']['target_count']}",
        "",
    ]
    if show_trace:
        lines.append("retrieval trace:")
        for stage in data["retrieval_trace"]:
            if stage["status"] == "completed":
                lines.append(
                    "   - "
                    + f"{stage['stage']}: scanned={stage['examples_scanned']} "
                    + f"exact={stage['exact_count']} adjacent={stage['adjacent_count']}"
                )
            else:
                lines.append(f"   - {stage['stage']}: skipped | {stage['reason']}")
        external = data["external_search"]
        lines.append(
            "   - external: "
            + ("recommended" if external["recommended"] else "not recommended")
            + f" | {external['reason']}"
        )
        lines.append("")
    for index, match in enumerate(data["matches"], 1):
        motion = match["motion"]
        lines.append(f"{index}. {motion['labels'][0]} [{motion['id']}] score={match['score']}")
        lines.append(
            "   "
            + f"category={motion['category']} target={','.join(motion['targets'])} "
            + f"trigger={','.join(motion['triggers'])} feel={','.join(motion['feel'])}"
        )
        lines.append(f"   channels={','.join(motion['channels'])}")
        for site in match["sites"]:
            lines.append(
                "   - "
                + f"{site['name']} | {site['kind']} | auth={site['auth']} | "
                + f"{','.join(site['capabilities'])} | {site['url']}"
            )
        for example in match.get("examples", []):
            if example.get("link_scope") == "source-with-category-preview":
                lines.append(
                    "   * "
                    + f"source-linked example: {example['title']} | evidence={example['preview_strategy']} | "
                    + f"trigger={example['trigger']['kind']} | source={example['url']} | "
                    + f"category-preview={example['preview_url']}"
                )
            elif example.get("preview_strategy") == "official-media" and example.get("preview_url"):
                lines.append(
                    "   * "
                    + f"exact example: {example['title']} | evidence=official-media | "
                    + f"trigger={example['trigger']['kind']} | watch={example['preview_url']} | source={example['url']}"
                )
            else:
                lines.append(
                    "   * "
                    + f"exact example: {example['title']} | evidence={example['preview_strategy']} | "
                    + f"trigger={example['trigger']['kind']} | {example['url']}"
                )
        if not match["sites"]:
            lines.append("   - no site matches the requested filters")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parser().parse_args()
    if args.limit < 1 or args.limit > 20:
        raise SystemExit("--limit must be between 1 and 20")
    if args.sites_per_motion < 1 or args.sites_per_motion > 10:
        raise SystemExit("--sites-per-motion must be between 1 and 10")
    if args.examples_per_motion < 1 or args.examples_per_motion > 20:
        raise SystemExit("--examples-per-motion must be between 1 and 20")
    if args.candidate_limit < 1 or args.candidate_limit > 64:
        raise SystemExit("--candidate-limit must be between 1 and 64")
    if args.target_count < 1 or args.target_count > 10:
        raise SystemExit("--target-count must be between 1 and 10")
    if args.candidate_pool_only and not args.json:
        raise SystemExit("--candidate-pool-only requires --json")
    try:
        data = search_catalog(
            args.query,
            stack=args.stack,
            capability=args.capability,
            kind=args.kind,
            limit=args.limit,
            sites_per_motion=args.sites_per_motion,
            examples_per_motion=args.examples_per_motion,
            candidate_limit=args.candidate_limit,
            strategy=args.strategy,
            target_count=args.target_count,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    if args.json:
        if args.candidate_pool_only:
            data = {
                "query": data["query"],
                "filters": data["filters"],
                "catalog_version": data["catalog_version"],
                "catalog_source": data["catalog_source"],
                "example_source": data["example_source"],
                "catalog_warnings": data["catalog_warnings"],
                "strategy": data["strategy"],
                "retrieval_level": data["retrieval_level"],
                "examples_total": data["examples_total"],
                "query_variants": data["query_variants"],
                "query_expansion_groups": data["query_expansion_groups"],
                "coverage": data["coverage"],
                "retrieval_trace": data["retrieval_trace"],
                "external_search": data["external_search"],
                "candidate_pool": data["candidate_pool"],
            }
            print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        else:
            print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(render_text(data, show_trace=args.trace), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
