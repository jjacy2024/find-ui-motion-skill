#!/usr/bin/env python3
"""Create a read-only shallow health report for catalog URLs."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from check_example_health import restriction_marker


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = REPO_ROOT / "skills" / "find-ui-motion" / "references" / "sites.json"
DEFAULT_EXAMPLES = REPO_ROOT / "skills" / "find-ui-motion" / "references" / "examples.jsonl"
RESTRICTED_REDIRECT_HOSTS = {"office-sec.alibaba-inc.com"}


def iter_urls(site: dict[str, Any]):
    yield "homepage", site["homepage"]
    for name, value in site["routes"].items():
        if name == "categories":
            for category, url in value.items():
                yield f"category:{category}", url
        else:
            yield name, value
    if site["license"].get("url"):
        yield "license", site["license"]["url"]


def check(target: tuple[str, str, str], timeout: float) -> dict[str, Any]:
    site_id, label, template = target
    url = template.replace("{query}", "button%20animation")
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 find-ui-motion-health/0.7"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(32768)
            final_url = response.geturl()
            marker = restriction_marker(body)
            final_host = (urlsplit(final_url).hostname or "").lower()
            status = "restricted" if marker is not None or final_host in RESTRICTED_REDIRECT_HOSTS else "reachable"
            result = {
                "site_id": site_id,
                "route": label,
                "url": url,
                "status": status,
                "http_status": response.status,
                "final_url": final_url,
            }
            if marker is not None:
                result["restriction_marker"] = marker
            return result
    except HTTPError as exc:
        return {
            "site_id": site_id,
            "route": label,
            "url": url,
            "status": "http_error",
            "http_status": exc.code,
            "final_url": exc.geturl(),
        }
    except (URLError, socket.timeout, TimeoutError, OSError) as exc:
        return {
            "site_id": site_id,
            "route": label,
            "url": url,
            "status": "unreachable",
            "error": exc.__class__.__name__,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when any route is not reachable")
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    examples = [json.loads(line) for line in args.examples.read_text(encoding="utf-8").splitlines() if line.strip()]
    targets = [
        (site["id"], route_name, url)
        for site in catalog["sites"]
        for route_name, url in iter_urls(site)
    ]
    targets.extend((example["site_id"], f"example:{example['id']}", example["url"]) for example in examples)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        results = list(executor.map(lambda item: check(item, args.timeout), targets))
    summary: dict[str, int] = {}
    for result in results:
        summary[result["status"]] = summary.get(result["status"], 0) + 1
    report = {
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "catalog_version": catalog["catalog_version"],
        "example_count": len(examples),
        "summary": summary,
        "results": results,
        "note": "Shallow HTTP evidence only; restricted network pages, anti-bot responses, and timeouts require browser review.",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    unhealthy = any(result["status"] != "reachable" for result in results)
    return 2 if args.strict and unhealthy else 0


if __name__ == "__main__":
    raise SystemExit(main())
