#!/usr/bin/env python3
"""Range-check official Rive preview and runtime assets in examples.jsonl."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXAMPLES = REPO_ROOT / "skills" / "find-ui-motion" / "references" / "examples.jsonl"
WRITE_OUT = "%{url}\t%{url_effective}\t%{http_code}\t%{size_download}\t%{content_type}\n"


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _check_batch(urls: list[str], *, workers: int, timeout: float) -> dict[str, dict[str, Any]]:
    curl = shutil.which("curl")
    if curl is None:
        raise RuntimeError("curl is required")
    command = [
        curl,
        "--parallel",
        "--parallel-immediate",
        "--parallel-max",
        str(workers),
        "--location",
        "--silent",
        "--show-error",
        "--range",
        "0-31",
        "--connect-timeout",
        "5",
        "--max-time",
        str(timeout),
        "--retry",
        "2",
        "--retry-all-errors",
        "--write-out",
        WRITE_OUT,
    ]
    for url in urls:
        command.extend(("--url", url, "--output", "/dev/null"))
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    results: dict[str, dict[str, Any]] = {}
    for line in completed.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) != 5 or not fields[2].isdigit():
            continue
        original_url, effective_url, code_text, size_text, content_type = fields
        try:
            size = int(float(size_text))
        except ValueError:
            size = 0
        parsed = urlparse(effective_url)
        code = int(code_text)
        results[original_url] = {
            "effective_url": effective_url,
            "status": code,
            "bytes": size,
            "content_type": content_type,
            "ok": (
                code == 206
                and size == 32
                and parsed.scheme == "https"
                and parsed.hostname == "public.rive.app"
            ),
        }
    for url in urls:
        results.setdefault(
            url,
            {
                "effective_url": None,
                "status": None,
                "bytes": 0,
                "content_type": None,
                "ok": False,
            },
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retry-rounds", type=int, default=2, help="Recheck failed URLs with lower concurrency")
    parser.add_argument("--checked-at", default=date.today().isoformat())
    parser.add_argument("--apply", action="store_true", help="Record successful asset checks in examples.jsonl")
    args = parser.parse_args()
    if not 1 <= args.workers <= 32:
        parser.error("--workers must be between 1 and 32")
    if not 16 <= args.batch_size <= 512:
        parser.error("--batch-size must be between 16 and 512")
    if not 5 <= args.timeout <= 60:
        parser.error("--timeout must be between 5 and 60 seconds")
    if not 0 <= args.retry_rounds <= 4:
        parser.error("--retry-rounds must be between 0 and 4")
    try:
        date.fromisoformat(args.checked_at)
    except ValueError:
        parser.error("--checked-at must be YYYY-MM-DD")

    records = [json.loads(line) for line in args.examples.read_text(encoding="utf-8").splitlines() if line.strip()]
    generated = [record for record in records if str(record.get("id", "")).startswith("rive-marketplace-")]
    assets_by_id: dict[str, dict[str, str]] = {}
    urls: list[str] = []
    for record in generated:
        evidence = record.get("source_evidence") if isinstance(record.get("source_evidence"), dict) else {}
        media_url = evidence.get("official_media_url")
        runtime_url = evidence.get("runtime_file_url")
        if isinstance(media_url, str) and isinstance(runtime_url, str):
            assets_by_id[record["id"]] = {"media": media_url, "runtime": runtime_url}
            urls.extend((media_url, runtime_url))

    checks: dict[str, dict[str, Any]] = {}
    for batch in _chunks(urls, args.batch_size):
        checks.update(_check_batch(batch, workers=args.workers, timeout=args.timeout))
    retry_counts: list[int] = []
    for _ in range(args.retry_rounds):
        failed_urls = [url for url in urls if not checks[url]["ok"]]
        retry_counts.append(len(failed_urls))
        if not failed_urls:
            break
        retry_workers = min(4, args.workers)
        retry_batch_size = min(64, args.batch_size)
        for batch in _chunks(failed_urls, retry_batch_size):
            retried = _check_batch(batch, workers=retry_workers, timeout=args.timeout)
            for url, result in retried.items():
                if result["ok"] or not checks[url]["ok"]:
                    checks[url] = result

    failures: list[dict[str, Any]] = []
    verified_ids: set[str] = set()
    for record in generated:
        assets = assets_by_id.get(record["id"])
        if assets is None:
            failures.append({"id": record["id"], "asset": "metadata", "reason": "missing asset URL"})
            continue
        media = checks[assets["media"]]
        runtime = checks[assets["runtime"]]
        if media["ok"] and runtime["ok"]:
            verified_ids.add(record["id"])
        else:
            if not media["ok"]:
                failures.append({"id": record["id"], "asset": "media", "url": assets["media"], **media})
            if not runtime["ok"]:
                failures.append({"id": record["id"], "asset": "runtime", "url": assets["runtime"], **runtime})

    if args.apply:
        for record in records:
            if record.get("id") not in verified_ids:
                continue
            evidence = record["source_evidence"]
            record["preview_url"] = evidence["official_media_url"]
            evidence["media_range_verified_at"] = args.checked_at
            evidence["runtime_range_verified_at"] = args.checked_at
        payload = "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in records)
        args.examples.write_text(payload, encoding="utf-8")

    report = {
        "generated_cases": len(generated),
        "cases_with_asset_urls": len(assets_by_id),
        "verified_cases": len(verified_ids),
        "checked_assets": len(checks),
        "failed_assets": len(failures),
        "retry_failed_url_counts": retry_counts,
        "checked_at": args.checked_at,
        "applied": args.apply,
        "failure_sample": failures[:50],
        "note": "Range checks prove current official asset retrieval, not per-item visual or interaction review.",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
