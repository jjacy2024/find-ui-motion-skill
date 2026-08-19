#!/usr/bin/env python3
"""Classify browser-observed source health without performing network access."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


BROKEN_STATUS_CODES = {404, 410}
RESTRICTED_STATUS_CODES = {401, 403, 429}
BROKEN_ERROR_PATTERNS = (
    re.compile(r"error fetching data", re.IGNORECASE),
    re.compile(r"project[^\n]*(?:not found|does not exist|unavailable)", re.IGNORECASE),
    re.compile(r"failed to load resource[^\n]*(?:404|410)", re.IGNORECASE),
)
DEEP_ANALYSIS_DEPTHS = {"keyframes", "video-trajectory"}


def _status(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 100 <= value <= 599:
        raise ValueError(f"{field} must be an HTTP status integer or null")
    return value


def _visible_render_target(target: Any, index: int) -> bool:
    if not isinstance(target, dict):
        raise ValueError(f"render_targets[{index}] must be an object")
    kind = target.get("kind")
    if not isinstance(kind, str) or not kind:
        raise ValueError(f"render_targets[{index}].kind must be a non-empty string")
    visible = target.get("visible", True)
    if not isinstance(visible, bool):
        raise ValueError(f"render_targets[{index}].visible must be boolean")
    width = target.get("width", 0)
    height = target.get("height", 0)
    if isinstance(width, bool) or not isinstance(width, (int, float)) or width < 0:
        raise ValueError(f"render_targets[{index}].width must be a non-negative number")
    if isinstance(height, bool) or not isinstance(height, (int, float)) or height < 0:
        raise ValueError(f"render_targets[{index}].height must be a non-negative number")
    return visible and width > 0 and height > 0


def classify_case(case: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(case, dict):
        raise ValueError("case must be an object")
    case_id = case.get("id")
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("case.id must be a non-empty string")

    outer_status = _status(case.get("outer_status"), "outer_status")
    settled = case.get("settled", False)
    redirected_away = case.get("redirected_away", False)
    access_restricted = case.get("access_restricted", False)
    visually_observed = case.get("visually_observed", False)
    capture_attempted = case.get("capture_attempted", False)
    capture_succeeded = case.get("capture_succeeded", False)
    for field, value in (
        ("settled", settled),
        ("redirected_away", redirected_away),
        ("access_restricted", access_restricted),
        ("visually_observed", visually_observed),
        ("capture_attempted", capture_attempted),
        ("capture_succeeded", capture_succeeded),
    ):
        if not isinstance(value, bool):
            raise ValueError(f"{field} must be boolean")
    if capture_succeeded and not capture_attempted:
        raise ValueError("capture_succeeded requires capture_attempted=true")

    critical_responses = case.get("critical_responses", [])
    if not isinstance(critical_responses, list):
        raise ValueError("critical_responses must be an array")
    critical_statuses: list[int] = []
    for index, response in enumerate(critical_responses):
        if not isinstance(response, dict):
            raise ValueError(f"critical_responses[{index}] must be an object")
        status = _status(response.get("status"), f"critical_responses[{index}].status")
        if status is not None:
            critical_statuses.append(status)

    console_errors = case.get("console_errors", [])
    if not isinstance(console_errors, list) or not all(isinstance(item, str) for item in console_errors):
        raise ValueError("console_errors must be a string array")
    render_targets = case.get("render_targets", [])
    if not isinstance(render_targets, list):
        raise ValueError("render_targets must be an array")
    has_render_target = any(_visible_render_target(target, index) for index, target in enumerate(render_targets))
    expects_render_target = case.get("expects_render_target", False)
    if not isinstance(expects_render_target, bool):
        raise ValueError("expects_render_target must be boolean")

    reasons: list[str] = []
    broken = False
    restricted = access_restricted or outer_status in RESTRICTED_STATUS_CODES or any(
        status in RESTRICTED_STATUS_CODES for status in critical_statuses
    )
    if outer_status in BROKEN_STATUS_CODES or (outer_status is not None and outer_status >= 400 and not restricted):
        broken = True
        reasons.append(f"outer-status-{outer_status}")
    for status in critical_statuses:
        if status in BROKEN_STATUS_CODES or status >= 500:
            broken = True
            reasons.append(f"critical-status-{status}")
    if any(pattern.search(message) for message in console_errors for pattern in BROKEN_ERROR_PATTERNS):
        broken = True
        reasons.append("content-fetch-error")
    if redirected_away:
        broken = True
        reasons.append("redirected-away")
    if settled and expects_render_target and not has_render_target and not restricted:
        broken = True
        reasons.append("missing-render-target-after-settle")

    shell_reachable = outer_status is not None and 200 <= outer_status < 400 and not redirected_away
    rendered = visually_observed or has_render_target
    if broken:
        state = "broken"
    elif rendered and capture_attempted and not capture_succeeded:
        state = "capture_restricted"
        reasons.append("render-confirmed-capture-failed")
    elif rendered:
        state = "render_verified"
        reasons.append("visible-render-confirmed")
    else:
        state = "shell_reachable"
        if restricted:
            reasons.append("access-restricted")
        elif shell_reachable:
            reasons.append("outer-shell-only")
        else:
            reasons.append("source-unreachable-or-unconfirmed")

    analysis_depth = case.get("analysis_depth")
    if analysis_depth is not None and analysis_depth not in DEEP_ANALYSIS_DEPTHS | {"metadata-only"}:
        raise ValueError("analysis_depth must be keyframes, video-trajectory, metadata-only, or null")
    quick_eligible = state in {"render_verified", "capture_restricted"}
    deep_eligible = state == "render_verified" and analysis_depth in DEEP_ANALYSIS_DEPTHS
    return {
        "id": case_id,
        "state": state,
        "quick_eligible": quick_eligible,
        "deep_eligible": deep_eligible,
        "reasons": list(dict.fromkeys(reasons)),
    }


def classify_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("cases"), list):
        raise ValueError("manifest must be an object with a cases array")
    results = [classify_case(case) for case in manifest["cases"]]
    counts: dict[str, int] = {}
    for result in results:
        counts[result["state"]] = counts.get(result["state"], 0) + 1
    return {
        "schema_version": 1,
        "checked": len(results),
        "states": counts,
        "quick_eligible_count": sum(result["quick_eligible"] for result in results),
        "deep_eligible_count": sum(result["deep_eligible"] for result in results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Browser-observation JSON manifest")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = classify_manifest(json.loads(args.manifest.read_text(encoding="utf-8")))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 1 if result["states"].get("broken", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
