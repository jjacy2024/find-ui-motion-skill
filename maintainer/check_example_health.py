#!/usr/bin/env python3
"""Shallow-check concrete example URLs without changing verification dates."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXAMPLES = REPO_ROOT / "skills" / "find-ui-motion" / "references" / "examples.jsonl"
RESTRICTED_BODY_MARKERS = {
    "alibaba-domain-block": "<title>域名拦截</title>".encode(),
    "alibaba-policy-block": "域名不在安全策略默认允许的范围内".encode(),
    "alibaba-verification-block": "长期未使用或首次查看拦截详情时".encode(),
}


def restriction_marker(body: bytes) -> str | None:
    for name, marker in RESTRICTED_BODY_MARKERS.items():
        if marker in body:
            return name
    return None


def canonical_path(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    return parts.hostname.lower() if parts.hostname else "", parts.path.rstrip("/") or "/"


def classify_redirect(url: str, final_url: str) -> str:
    original_host, original_path = canonical_path(url)
    final_host, final_path = canonical_path(final_url)
    if final_host != original_host or (original_path != "/" and final_path == "/"):
        return "redirected-away"
    return "ok"


def check_with_curl(record: dict[str, Any], timeout: float, original_error: Exception) -> dict[str, Any] | None:
    curl = shutil.which("curl")
    if curl is None:
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="find-ui-motion-health-") as temp_dir:
            body_path = Path(temp_dir) / "body"
            result = subprocess.run(
                [
                    curl,
                    "-LsS",
                    "--range",
                    "0-32767",
                    "--max-time",
                    str(timeout),
                    "--user-agent",
                    "Mozilla/5.0 find-ui-motion-example-health/0.7",
                    "--output",
                    str(body_path),
                    "--write-out",
                    "%{http_code}\n%{url_effective}",
                    record["url"],
                ],
                capture_output=True,
                text=True,
                timeout=timeout + 2,
                check=False,
            )
            body = body_path.read_bytes()[:32768] if body_path.exists() else b""
    except Exception:
        return None
    lines = result.stdout.splitlines()
    if result.returncode != 0 or len(lines) < 2 or not lines[0].isdigit():
        return None
    status = int(lines[0])
    final_url = lines[1]
    state = classify_redirect(record["url"], final_url)
    if status in {401, 403, 429}:
        state = "restricted"
    elif status in {404, 410}:
        state = "missing"
    elif status >= 400:
        state = "http-error"
    marker = restriction_marker(body)
    if marker is not None:
        state = "restricted"
    response = {
        "id": record["id"],
        "site_id": record["site_id"],
        "url": record["url"],
        "status": status,
        "state": state,
        "final_url": final_url,
        "transport": "curl-fallback",
        "urllib_error": str(original_error),
    }
    if marker is not None:
        response["restriction_marker"] = marker
    return response


def check(record: dict[str, Any], timeout: float) -> dict[str, Any]:
    url = record["url"]
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 find-ui-motion-example-health/0.7",
            "Accept": "text/html,application/xhtml+xml,*/*",
            "Range": "bytes=0-32767",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(32768)
            status = response.status
            final_url = response.geturl()
        state = classify_redirect(url, final_url)
        marker = restriction_marker(body)
        if marker is not None:
            state = "restricted"
        result = {"id": record["id"], "site_id": record["site_id"], "url": url, "status": status, "state": state, "final_url": final_url}
        if marker is not None:
            result["restriction_marker"] = marker
        return result
    except HTTPError as exc:
        state = "restricted" if exc.code in {401, 403, 429} else "missing" if exc.code in {404, 410} else "http-error"
        return {"id": record["id"], "site_id": record["site_id"], "url": url, "status": exc.code, "state": state}
    except Exception as exc:
        fallback = check_with_curl(record, timeout, exc)
        if fallback is not None:
            return fallback
        return {"id": record["id"], "site_id": record["site_id"], "url": url, "status": None, "state": "unreachable", "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        parser.error("--workers must be between 1 and 16")
    if not 1 <= args.timeout <= 30:
        parser.error("--timeout must be between 1 and 30")

    records = [json.loads(line) for line in args.examples.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit is not None:
        records = records[: max(0, args.limit)]
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(check, record, args.timeout) for record in records]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: (item["site_id"], item["id"]))

    counts: dict[str, int] = {}
    for result in results:
        counts[result["state"]] = counts.get(result["state"], 0) + 1
    print(json.dumps({"checked": len(results), "states": counts, "results": results}, ensure_ascii=False, indent=2))
    return 1 if counts.get("missing", 0) or counts.get("redirected-away", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
