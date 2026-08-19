#!/usr/bin/env python3
"""Build a reviewable candidate JSONL from a small curated source selection."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXAMPLES = REPO_ROOT / "skills" / "find-ui-motion" / "references" / "examples.jsonl"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", unquote(value).lower()).strip("-")


def _record_id(site_id: str, url: str) -> str:
    parsed = urlsplit(url)
    if site_id == "transitions-dev":
        slug = parse_qs(parsed.query).get("t", [""])[0]
    else:
        slug = parsed.path.strip("/")
    if not slug:
        raise ValueError(f"cannot derive item id from {url}")
    return f"{site_id}-{_slugify(slug)}"


def _capture(trigger: str) -> tuple[int, list[str], str, int]:
    if trigger == "hover":
        return 800, ["rest", "hover-peak", "reset"], "storyboard", 4
    if trigger == "scroll":
        return 1200, ["before-scroll", "mid-scroll", "settled"], "storyboard", 4
    if trigger in {"loop", "mount"}:
        return 1400, ["cycle-start", "cycle-peak", "cycle-return"], "clip", 5
    return 1000, ["before", "activated", "settled"], "storyboard", 4


def _selection_record(item: dict[str, Any], checked_at: str) -> dict[str, Any]:
    required = {"site_id", "title", "url", "motion_ids", "stacks", "trigger", "index_url", "rights_note"}
    missing = sorted(required - item.keys())
    if missing:
        raise ValueError(f"selection item missing {missing}: {item}")
    settle_ms, frame_labels, evidence, clip_seconds = _capture(item["trigger"])
    title = str(item["title"])
    search_terms = sorted(
        {
            token
            for token in re.findall(r"[a-z0-9][a-z0-9-]+", f"{title.lower()} {item['url'].lower()}")
            if len(token) > 1
        }
    )[:24]
    return {
        "id": _record_id(item["site_id"], item["url"]),
        "site_id": item["site_id"],
        "title": title,
        "url": item["url"],
        "motion_ids": item["motion_ids"],
        "stacks": item["stacks"],
        "preview_strategy": "live-capture",
        "trigger": {
            "kind": item["trigger"],
            "target_hint": item.get("target_hint", f"the visible {title} example preview"),
            "settle_ms": settle_ms,
            "reset_hint": "use the public replay or reset control when available; otherwise restore the initial visible state",
        },
        "capture": {
            "recommended_evidence": evidence,
            "frame_labels": frame_labels,
            "clip_seconds": clip_seconds,
        },
        "rights": {"status": "reference-only", "note": item["rights_note"]},
        "source_evidence": {
            "kind": "public-index-page",
            "index_url": item["index_url"],
            "discovered_at": checked_at,
            **({"ranking": item["ranking"]} if item.get("ranking") else {}),
        },
        "search_terms": search_terms,
        "last_shallow_check": checked_at,
        "last_verified": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--restore-jsonl", action="append", type=Path, default=[])
    parser.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    parser.add_argument("--include-active", action="store_true", help="Keep selected records even when they already exist in the active catalog")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    checked_at = selection["checked_at"]
    restore_sources = set(selection.get("restore_sources", []))
    restore_overrides = selection.get("restore_overrides", {})
    records = [_selection_record(item, checked_at) for item in selection.get("items", [])]
    restored_by_source: dict[str, int] = {}
    for path in args.restore_jsonl:
        for item in _read_jsonl(path):
            record = item.get("record") if isinstance(item.get("record"), dict) else item
            if record.get("site_id") not in restore_sources:
                continue
            copy = dict(record)
            copy["last_shallow_check"] = checked_at
            copy["last_verified"] = None
            copy.pop("verification", None)
            override = restore_overrides.get(copy["id"])
            if isinstance(override, dict):
                copy.update(override)
            records.append(copy)
            restored_by_source[copy["site_id"]] = restored_by_source.get(copy["site_id"], 0) + 1

    active = [] if args.include_active else _read_jsonl(args.examples)
    active_ids = {record["id"] for record in active}
    active_urls = {record["url"].rstrip("/") for record in active}
    output: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for record in records:
        case_id = record["id"]
        url = record["url"].rstrip("/")
        if case_id in active_ids or url in active_urls or case_id in seen_ids or url in seen_urls:
            continue
        seen_ids.add(case_id)
        seen_urls.add(url)
        output.append(record)

    _atomic_write(
        args.output,
        "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in output),
    )
    source_counts: dict[str, int] = {}
    for record in output:
        source_counts[record["site_id"]] = source_counts.get(record["site_id"], 0) + 1
    print(json.dumps({
        "checked_at": checked_at,
        "candidates": len(output),
        "sources": source_counts,
        "restored_by_source": restored_by_source,
        "output": str(args.output.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
