#!/usr/bin/env python3
"""Build non-Rive candidates from allowlisted links on public index pages."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

from check_example_health import check
from expand_public_sitemaps import _classify, _normalize_url, _slugify, _title_from_slug


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXAMPLES = REPO_ROOT / "skills" / "find-ui-motion" / "references" / "examples.jsonl"

SOURCE_CONFIGS: dict[str, dict[str, Any]] = {
    "aceternity-ui": {
        "indexes": ["https://ui.aceternity.com/components"],
        "host": "ui.aceternity.com",
        "path": re.compile(r"^/components/[a-z0-9-]+/?$"),
        "transport": "browser",
        "limit": 111,
        "stacks": ["react", "typescript"],
        "preview_strategy": "live-capture",
        "rights_note": "Exact public Aceternity UI component URL was discovered from the current official components index in a normal browser and shallow-checked. Verify the live demo, copy path, dependencies, and current item or site terms before reuse.",
    },
    "animate-ui": {
        "indexes": [
            "https://animate-ui.com/docs/components",
            "https://animate-ui.com/docs/primitives",
        ],
        "host": "animate-ui.com",
        "path": re.compile(
            r"^/docs/(?:components|primitives)/(?:animate|radix|base|headless|buttons|backgrounds|community|texts|effects)/[a-z0-9-]+/?$"
        ),
        "transport": "curl",
        "limit": 80,
        "stacks": ["react", "typescript"],
        "preview_strategy": "live-capture",
        "rights_note": "Exact public Animate UI documentation URL was discovered from a current official index page and shallow-checked. Verify the live demo, dependencies, and current MIT plus Commons Clause restrictions before reuse.",
    },
    "21st-dev": {
        "indexes": [
            "https://21st.dev/community/components/s/animated-hero",
            "https://21st.dev/community/components/s/background",
            "https://21st.dev/community/components/s/carousel",
            "https://21st.dev/community/components/s/cursor",
            "https://21st.dev/community/components/s/dock",
            "https://21st.dev/community/components/s/marquee",
            "https://21st.dev/community/components/s/spinner",
            "https://21st.dev/community/components/s/text",
        ],
        "host": "21st.dev",
        "path": re.compile(r"^/@[^/]+/components/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)?/?$"),
        "transport": "curl",
        "limit": 30,
        "stacks": ["react"],
        "preview_strategy": "live-capture",
        "rights_note": "Exact public 21st.dev item URL was discovered from a current public component category page and shallow-checked. Verify the live preview, author-level implementation, dependencies, and item terms before reuse.",
    },
    "motion-primitives": {
        "indexes": ["https://motion-primitives.com/docs"],
        "host": "motion-primitives.com",
        "path": re.compile(r"^/docs/[a-z0-9-]+/?$"),
        "exclude_slugs": {"installation"},
        "transport": "browser",
        "enabled": False,
        "limit": 40,
        "stacks": ["react", "typescript"],
        "preview_strategy": "live-capture",
        "rights_note": "Exact public Motion Primitives documentation URL was discovered from the current official docs index in a normal browser and shallow-checked. Verify the live demo, package version, dependencies, and current MIT terms before reuse.",
    },
    "fancy-components": {
        "indexes": ["https://www.fancycomponents.dev/"],
        "host": "www.fancycomponents.dev",
        "path": re.compile(r"^/docs/components/(?:blocks|text)/[a-z0-9-]+/?$"),
        "transport": "browser",
        "enabled": False,
        "limit": 10,
        "stacks": ["react", "typescript"],
        "preview_strategy": "live-capture",
        "rights_note": "Exact public Fancy Components documentation URL was discovered from the current official homepage in a normal browser and shallow-checked. Verify the live demo, public implementation, dependencies, and current repository license before reuse.",
    },
}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if isinstance(href, str) and href:
            self.hrefs.append(href)


def _fetch_index(url: str, timeout: float, config: dict[str, Any]) -> list[str]:
    if config.get("transport") == "browser":
        helper = Path(__file__).with_name("discover_public_index_links.js")
        completed = subprocess.run(
            [
                "node",
                str(helper),
                "--index",
                url,
                "--host",
                config["host"],
                "--path-regex",
                config["path"].pattern,
                "--timeout",
                str(int(timeout * 1000)),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or f"browser discovery failed: {url}")
        report = json.loads(completed.stdout)
        if report.get("state") != "reachable":
            raise RuntimeError(f"public index is not reachable in Chrome: {url} ({report.get('state')})")
        return [value for value in report.get("links", []) if isinstance(value, str)]
    curl = shutil.which("curl")
    if curl is None:
        raise RuntimeError("curl is required")
    completed = subprocess.run(
        [
            curl,
            "-LsS",
            "--fail-with-body",
            "--retry",
            "2",
            "--retry-delay",
            "1",
            "--max-time",
            str(timeout),
            "--user-agent",
            "Mozilla/5.0 find-ui-motion-catalog/1.0",
            url,
        ],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace").strip() or f"curl failed: {url}")
    parser = LinkParser()
    parser.feed(completed.stdout.decode("utf-8", errors="replace"))
    return parser.hrefs


def _allowed_url(site_id: str, url: str) -> bool:
    config = SOURCE_CONFIGS[site_id]
    parsed = urlparse(url)
    slug = unquote(parsed.path.rstrip("/").rsplit("/", 1)[-1])
    return (
        parsed.scheme == "https"
        and parsed.hostname == config["host"]
        and not parsed.query
        and not parsed.fragment
        and bool(config["path"].fullmatch(unquote(parsed.path)))
        and slug not in config.get("exclude_slugs", set())
    )


def _record_id(site_id: str, path: str) -> str:
    if site_id == "21st-dev":
        return f"{site_id}-{_slugify(unquote(path).lstrip('/'))}"
    return f"{site_id}-{_slugify(unquote(path).removeprefix('/docs/'))}"


def _record(site_id: str, url: str, index_url: str, checked_at: str) -> dict[str, Any]:
    config = SOURCE_CONFIGS[site_id]
    url = _normalize_url(url)
    parsed = urlparse(url)
    slug = unquote(parsed.path.rstrip("/").rsplit("/", 1)[-1])
    title = _title_from_slug(slug)
    motion_ids, trigger = _classify(site_id, parsed.path, slug)
    clip = trigger == "loop"
    if trigger == "hover":
        frame_labels = ["rest", "hover-peak", "reset"]
        settle_ms = 800
    elif trigger == "scroll":
        frame_labels = ["before-scroll", "mid-scroll", "settled"]
        settle_ms = 1200
    elif trigger == "mount":
        frame_labels = ["before-replay", "mid-motion", "settled"]
        settle_ms = 1200
    else:
        frame_labels = ["before", "activated", "settled"]
        settle_ms = 1000
    search_terms = sorted(
        {
            token
            for token in re.findall(r"[a-z0-9][a-z0-9-]+", f"{parsed.path} {slug} {title.lower()}")
            if len(token) > 1
        }
    )[:24]
    return {
        "id": _record_id(site_id, parsed.path),
        "site_id": site_id,
        "title": title,
        "url": url,
        "motion_ids": motion_ids,
        "stacks": config["stacks"],
        "preview_strategy": config["preview_strategy"],
        "trigger": {
            "kind": trigger,
            "target_hint": f"the visible {title} example preview",
            "settle_ms": 1600 if clip else settle_ms,
            "reset_hint": "use the public replay or reset control when available; otherwise restore the initial visible state",
        },
        "capture": {
            "recommended_evidence": "clip" if clip else "storyboard",
            "frame_labels": ["cycle-start", "cycle-peak", "cycle-return"] if clip else frame_labels,
            "clip_seconds": 5 if clip else 4,
        },
        "rights": {"status": "reference-only", "note": config["rights_note"]},
        "source_evidence": {
            "kind": "public-index-page",
            "index_url": index_url,
            "discovered_at": checked_at,
        },
        "search_terms": search_terms,
        "last_shallow_check": checked_at,
        "last_verified": None,
    }


def _discover(site_id: str, timeout: float, checked_at: str, limit_override: int | None) -> list[dict[str, Any]]:
    config = SOURCE_CONFIGS[site_id]
    limit = limit_override or config["limit"]
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index_url in config["indexes"]:
        for href in _fetch_index(index_url, timeout, config):
            url = _normalize_url(urljoin(index_url, href))
            if url in seen or not _allowed_url(site_id, url):
                continue
            seen.add(url)
            records.append(_record(site_id, url, index_url, checked_at))
            if len(records) == limit:
                return records
    return records


def _read_exclusions(paths: list[Path]) -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    urls: set[str] = set()
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            record = item.get("record") if isinstance(item, dict) and isinstance(item.get("record"), dict) else item
            if not isinstance(record, dict):
                continue
            if isinstance(record.get("id"), str):
                ids.add(record["id"])
            if isinstance(record.get("url"), str):
                urls.add(record["url"].rstrip("/"))
    return ids, urls


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES, help="Existing active catalog used only for duplicate exclusion")
    parser.add_argument("--output", type=Path, required=True, help="Independent candidate JSONL; the active catalog is never modified")
    parser.add_argument("--source", action="append", choices=sorted(SOURCE_CONFIGS), help="Repeat to select sources; defaults to all")
    parser.add_argument("--per-source-limit", type=int, default=None, help="Override each source's conservative default")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--checked-at", default=date.today().isoformat())
    parser.add_argument("--exclude-jsonl", action="append", type=Path, default=[], help="Additional active or quarantine JSONL to exclude")
    parser.add_argument("--apply", action="store_true", help="Shallow-check wrappers and write only shell-reachable candidates")
    args = parser.parse_args()
    if args.per_source_limit is not None and not 1 <= args.per_source_limit <= 1000:
        parser.error("--per-source-limit must be between 1 and 1000")
    if not 1 <= args.workers <= 16:
        parser.error("--workers must be between 1 and 16")
    if not 5 <= args.timeout <= 30:
        parser.error("--timeout must be between 5 and 30 seconds")
    try:
        date.fromisoformat(args.checked_at)
    except ValueError:
        parser.error("--checked-at must be YYYY-MM-DD")

    selected_sources = args.source or [site_id for site_id, config in SOURCE_CONFIGS.items() if config.get("enabled", True)]
    excluded_ids, excluded_urls = _read_exclusions([args.examples, *args.exclude_jsonl])
    discovered_by_source: dict[str, int] = {}
    candidates: list[dict[str, Any]] = []
    seen_ids = set(excluded_ids)
    seen_urls = set(excluded_urls)
    for site_id in selected_sources:
        discovered = _discover(site_id, args.timeout, args.checked_at, args.per_source_limit)
        discovered_by_source[site_id] = len(discovered)
        for record in discovered:
            if record["id"] in seen_ids or record["url"].rstrip("/") in seen_urls:
                continue
            seen_ids.add(record["id"])
            seen_urls.add(record["url"].rstrip("/"))
            candidates.append(record)

    states: dict[str, int] = {}
    accepted: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    if args.apply:
        browser_linked = [record for record in candidates if SOURCE_CONFIGS[record["site_id"]].get("transport") == "browser"]
        accepted.extend(browser_linked)
        if browser_linked:
            states["browser-index-linked"] = len(browser_linked)
        health_candidates = [record for record in candidates if record not in browser_linked]
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_record = {executor.submit(check, record, args.timeout): record for record in health_candidates}
            for future in as_completed(future_to_record):
                result = future.result()
                states[result["state"]] = states.get(result["state"], 0) + 1
                if result["state"] == "shell-reachable":
                    accepted.append(future_to_record[future])
                else:
                    failures.append(result)
        accepted.sort(key=lambda record: (record["site_id"], record["id"]))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in accepted),
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "selected_sources": selected_sources,
                "discovered_by_source": discovered_by_source,
                "new_candidates": len(candidates),
                "health_states": states,
                "accepted_count": len(accepted),
                "checked_at": args.checked_at,
                "applied": args.apply,
                "output": str(args.output),
                "failure_sample": failures[:30],
                "note": "Public index discovery plus outer-wrapper health for curl-accessible sources. Browser-only sources are staged from exact visible public links and still require exact-page motion audit. The active catalog is unchanged until browser motion curation passes.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not args.apply or not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
