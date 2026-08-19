#!/usr/bin/env python3
"""Build a conservative active catalog from repeated dynamic-evidence audits."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit


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


def _canonical_url(value: str) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    parsed = urlsplit(value)
    path = unquote(parsed.path).rstrip("/") or "/"
    return (parsed.hostname.lower() if parsed.hostname else "", path, tuple(sorted(parse_qsl(parsed.query, keep_blank_values=True))))


def _report_date(report: dict[str, Any]) -> str:
    value = str(report.get("checked_at") or "")[:10]
    date.fromisoformat(value)
    return value


def _load_audits(paths: list[Path]) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    dates: list[str] = []
    for path in paths:
        report = json.loads(path.read_text(encoding="utf-8"))
        dates.append(_report_date(report))
        results = report.get("results")
        if not isinstance(results, list):
            raise ValueError(f"{path}: results must be an array")
        seen: set[str] = set()
        for result in results:
            case_id = result.get("id")
            if not isinstance(case_id, str) or not case_id or case_id in seen:
                raise ValueError(f"{path}: invalid or duplicate result id {case_id!r}")
            if result.get("state") not in {"dynamic", "static", "broken", "unverified"}:
                raise ValueError(f"{path}: unsupported state for {case_id}")
            seen.add(case_id)
            copy = dict(result)
            copy["audit_report"] = str(path)
            copy["checked_at"] = dates[-1]
            by_id[case_id].append(copy)
    return by_id, dates


def _strongest(records: list[dict[str, Any]]) -> dict[str, Any]:
    def score(record: dict[str, Any]) -> tuple[int, int, int, str]:
        evidence = record.get("source_evidence") if isinstance(record.get("source_evidence"), dict) else {}
        return (
            int(record.get("last_verified") is not None),
            int(bool(evidence)),
            int(record.get("link_scope", "item") == "item"),
            record["id"],
        )

    return max(records, key=score)


def _deduplicate(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    duplicate_reason: dict[str, str] = {}
    active = list(records)
    for label, key_function in (
        ("duplicate-id", lambda record: record["id"]),
        ("duplicate-canonical-url", lambda record: _canonical_url(record["url"])),
        (
            "duplicate-official-media",
            lambda record: (record.get("source_evidence") or {}).get("official_media_url")
            if isinstance(record.get("source_evidence"), dict)
            else None,
        ),
        (
            "duplicate-runtime-file",
            lambda record: (record.get("source_evidence") or {}).get("runtime_file_url")
            if isinstance(record.get("source_evidence"), dict)
            else None,
        ),
    ):
        groups: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for record in active:
            key = key_function(record)
            if key is not None:
                groups[key].append(record)
        losers: set[str] = set()
        for group in groups.values():
            if len(group) < 2:
                continue
            winner = _strongest(group)
            for record in group:
                if record is not winner:
                    losers.add(record["id"])
                    duplicate_reason[record["id"]] = label
        active = [record for record in active if record["id"] not in losers]
    return active, duplicate_reason


def _decision(results: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None, str]:
    dynamic = [result for result in results if result["state"] == "dynamic"]
    if dynamic:
        return "keep", dynamic[-1], "dynamic-verified"
    states = Counter(result["state"] for result in results)
    if states["static"] >= 2:
        return "quarantine", None, "static-confirmed-twice"
    if states["broken"] >= 2:
        return "quarantine", None, "broken-confirmed-twice"
    if states["static"]:
        return "quarantine", None, "static-needs-second-confirmation"
    if states["broken"]:
        return "quarantine", None, "broken-needs-second-confirmation"
    return "quarantine", None, "motion-unverified"


def _verification_summary(result: dict[str, Any], checked_at: str) -> dict[str, Any]:
    if result.get("evidence_kind") == "official-media-frame-difference":
        evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
        return {
            "kind": "official-media-frame-difference",
            "verified_at": checked_at,
            "changed_pixel_ratio": round(float(evidence.get("changed_pixel_ratio", 0)), 6),
            "mean_absolute_difference": round(float(evidence.get("mean_absolute_difference", 0)), 6),
        }
    target = result.get("target") if isinstance(result.get("target"), dict) else {}
    return {
        "kind": "browser-page-motion",
        "verified_at": checked_at,
        "target_kind": target.get("kind"),
        "target_confidence": target.get("confidence"),
        "unique_frame_hashes": result.get("unique_frame_hashes", 0),
        "running_animations": result.get("running_animations", 0),
        "video_advanced": bool(result.get("video_advanced", False)),
    }


def curate(
    records: list[dict[str, Any]],
    audits: dict[str, list[dict[str, Any]]],
    checked_at: str,
    *,
    preserve_current_verified: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    deduplicated, duplicate_reasons = _deduplicate(records)
    by_id = {record["id"]: record for record in records}
    quarantine: list[dict[str, Any]] = []
    for case_id, reason in duplicate_reasons.items():
        quarantine.append({"id": case_id, "reason": reason, "record": by_id[case_id]})

    kept: list[dict[str, Any]] = []
    for record in deduplicated:
        results = audits.get(record["id"], [])
        verification = record.get("verification") if isinstance(record.get("verification"), dict) else {}
        is_preservable = (
            preserve_current_verified
            and not results
            and isinstance(record.get("last_verified"), str)
            and verification.get("verified_at") == record.get("last_verified")
            and verification.get("kind") in {"official-media-frame-difference", "browser-page-motion"}
        )
        if is_preservable:
            kept.append(record)
            continue
        action, winning_result, reason = _decision(results)
        evidence = record.get("source_evidence") if isinstance(record.get("source_evidence"), dict) else {}
        is_generated_rive = evidence.get("kind") == "public-list-api"
        if action == "keep" and is_generated_rive:
            if evidence.get("media_range_verified_at") != checked_at or evidence.get("runtime_range_verified_at") != checked_at:
                action = "quarantine"
                winning_result = None
                reason = "official-assets-not-currently-verified"
        if action == "keep" and winning_result is not None:
            copy = dict(record)
            copy["last_shallow_check"] = checked_at
            copy["last_verified"] = checked_at
            copy["verification"] = _verification_summary(winning_result, checked_at)
            kept.append(copy)
        else:
            quarantine.append(
                {
                    "id": record["id"],
                    "reason": reason,
                    "audit_states": [result["state"] for result in results],
                    "record": record,
                }
            )

    reason_counts = Counter(item["reason"] for item in quarantine)
    source_before = Counter(record["site_id"] for record in records)
    source_after = Counter(record["site_id"] for record in kept)
    report = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "checked_at": checked_at,
        "before_count": len(records),
        "after_count": len(kept),
        "quarantined_count": len(quarantine),
        "removed_exact_duplicates": len(duplicate_reasons),
        "quarantine_reasons": dict(reason_counts.most_common()),
        "sources_before": dict(source_before.most_common()),
        "sources_after": dict(source_after.most_common()),
        "source_retention": {
            site_id: round(source_after[site_id] / count, 4) if count else 0
            for site_id, count in source_before.items()
        },
        "policy": (
            "Preserve previously verified active cases without re-auditing; admit new or re-audited cases only with current decoded media frame change or current browser-observed target motion. Quarantine every broken, static, duplicate, or unverified candidate."
            if preserve_current_verified
            else "Retain only cases with current decoded media frame change or current browser-observed target motion. Quarantine every broken, static, duplicate, or unverified record."
        ),
    }
    return kept, quarantine, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    parser.add_argument("--candidate-jsonl", action="append", type=Path, default=[], help="Independent candidate JSONL to merge only after audit")
    parser.add_argument("--rive-report", action="append", type=Path, default=[])
    parser.add_argument("--page-report", action="append", type=Path, default=[])
    parser.add_argument("--quarantine-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    parser.add_argument("--checked-at", default=date.today().isoformat())
    parser.add_argument("--preserve-current-verified", action="store_true", help="Keep active records with internally consistent prior verification when absent from incremental reports")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    date.fromisoformat(args.checked_at)
    if not args.rive_report and not args.page_report:
        parser.error("at least one audit report is required")

    records = _read_jsonl(args.examples)
    for candidate_path in args.candidate_jsonl:
        records.extend(_read_jsonl(candidate_path))
    audits, audit_dates = _load_audits(args.rive_report + args.page_report)
    if any(value != args.checked_at for value in audit_dates):
        parser.error("every audit report date must match --checked-at")
    kept, quarantine, report = curate(
        records,
        audits,
        args.checked_at,
        preserve_current_verified=args.preserve_current_verified,
    )
    _atomic_write(args.report_output, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    _atomic_write(
        args.quarantine_output,
        "".join(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n" for item in quarantine),
    )
    if args.apply:
        _atomic_write(
            args.examples,
            "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in kept),
        )
    print(json.dumps({**report, "applied": args.apply, "report": str(args.report_output), "quarantine": str(args.quarantine_output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
