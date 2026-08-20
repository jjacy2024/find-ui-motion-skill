#!/usr/bin/env python3
"""Fuse visually reviewed motion rankings and gate formal deep-match results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from retrieval_fusion import reciprocal_rank_fusion, selective_vlm_decision

RRF_WEIGHTS = {
    "text_fit": 1.0,
    "visual_semantic_fit": 1.0,
    "motion_trajectory_fit": 0.8,
    "delivery_quality": 0.4,
}
ALLOWED_DEPTHS = {"video-trajectory", "keyframes"}
MATCH_QUALITIES = {"exact", "adjacent", "unresolved"}
VLM_VERDICTS = {"not-reviewed", "confirmed", "contradicted", "inconclusive"}
STRONG_RATIO = 0.85
SUPPORTING_RATIO = 0.65
LIVE_CHECK_BUDGET = 24
CAPTURE_BUDGET = 16
STOP_REASONS = {
    "none",
    "pool-exhausted",
    "three-consecutive-access-failures",
    "user-stopped",
    "request-changed",
}


def canonical_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("candidate URL must be a safe HTTPS item URL")
    query = urlencode([(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True) if not key.lower().startswith("utm_")])
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", parts.netloc.lower(), path, query, ""))


def _review_progress(data: dict[str, Any]) -> dict[str, Any]:
    raw = data.get("review_progress", {})
    if not isinstance(raw, dict):
        raise ValueError("manifest.review_progress must be an object")
    live_checked = raw.get("live_checked", 0)
    captured = raw.get("captured", 0)
    if not isinstance(live_checked, int) or isinstance(live_checked, bool) or not 0 <= live_checked <= LIVE_CHECK_BUDGET:
        raise ValueError(f"review_progress.live_checked must be between 0 and {LIVE_CHECK_BUDGET}")
    if not isinstance(captured, int) or isinstance(captured, bool) or not 0 <= captured <= CAPTURE_BUDGET:
        raise ValueError(f"review_progress.captured must be between 0 and {CAPTURE_BUDGET}")
    stop_reason = str(raw.get("stop_reason", "none")).strip() or "none"
    if stop_reason not in STOP_REASONS:
        raise ValueError(f"review_progress.stop_reason must be one of {sorted(STOP_REASONS)}")
    return {
        "live_checked": live_checked,
        "live_check_budget": LIVE_CHECK_BUDGET,
        "remaining_live_checks": LIVE_CHECK_BUDGET - live_checked,
        "captured": captured,
        "capture_budget": CAPTURE_BUDGET,
        "remaining_captures": CAPTURE_BUDGET - captured,
        "stop_reason": stop_reason,
    }


def _confidence(scores: dict[str, float], best_scores: dict[str, float]) -> tuple[str, dict[str, Any]]:
    ratios = {
        channel: (scores[channel] / best if best > 0 else 0.0)
        for channel, best in best_scores.items()
    }
    strong = [channel for channel, ratio in ratios.items() if ratio >= STRONG_RATIO]
    supporting = [channel for channel, ratio in ratios.items() if ratio >= SUPPORTING_RATIO]
    if len(strong) >= 3:
        confidence = "高"
    elif len(strong) >= 2 or len(supporting) >= 3:
        confidence = "中"
    else:
        confidence = "低"
    return confidence, {
        "channel_ratios": {channel: round(ratio, 4) for channel, ratio in ratios.items()},
        "strong_channels": strong,
        "supporting_channels": supporting,
    }


def _rerank(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for rank, item in enumerate(items, 1):
        result.append({**item, "fusion_rank": item["rank"], "rank": rank})
    return result


def rank_manifest(data: dict[str, Any], limit: int = 8) -> dict[str, Any]:
    if not 1 <= limit <= 10:
        raise ValueError("limit must be between 1 and 10")
    candidates = data.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("manifest.candidates must be an array")

    progress = _review_progress(data)
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            raise ValueError(f"candidates[{index}] must be an object")
        candidate_id = str(candidate.get("id", "")).strip()
        title = str(candidate.get("title", "")).strip()
        url = canonical_url(str(candidate.get("url", "")))
        depth = candidate.get("analysis_depth")
        if not candidate_id or not title:
            raise ValueError(f"candidates[{index}] requires id and title")
        if candidate_id in seen_ids or url in seen_urls:
            excluded.append({"id": candidate_id, "reason": "duplicate id or canonical item URL"})
            continue
        seen_ids.add(candidate_id)
        seen_urls.add(url)
        if depth not in ALLOWED_DEPTHS:
            excluded.append({"id": candidate_id, "reason": "metadata-only or missing visual inspection"})
            continue

        match_quality = str(candidate.get("match_quality", "unresolved")).strip() or "unresolved"
        if match_quality not in MATCH_QUALITIES:
            raise ValueError(f"candidates[{index}].match_quality must be one of {sorted(MATCH_QUALITIES)}")
        if match_quality == "unresolved":
            excluded.append({"id": candidate_id, "reason": "missing or unresolved semantic match quality"})
            continue
        vlm_verdict = str(candidate.get("vlm_verdict", "not-reviewed")).strip() or "not-reviewed"
        if vlm_verdict not in VLM_VERDICTS:
            raise ValueError(f"candidates[{index}].vlm_verdict must be one of {sorted(VLM_VERDICTS)}")
        if vlm_verdict == "contradicted":
            excluded.append({"id": candidate_id, "reason": "VLM review contradicted the claimed visual match"})
            continue

        scores = candidate.get("scores")
        if not isinstance(scores, dict):
            raise ValueError(f"candidates[{index}].scores must be an object")
        clean_scores: dict[str, float] = {}
        for key in RRF_WEIGHTS:
            value = scores.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= float(value) <= 1:
                raise ValueError(f"candidates[{index}].scores.{key} must be between 0 and 1")
            clean_scores[key] = float(value)
        eligible.append(
            {
                "id": candidate_id,
                "title": title,
                "url": url,
                "reason": str(candidate.get("reason", "")).strip(),
                "analysis_depth": depth,
                "match_quality": match_quality,
                "vlm_verdict": vlm_verdict,
                "scores": {key: round(value, 4) for key, value in clean_scores.items()},
            }
        )

    rankings = {
        channel: [item["id"] for item in sorted(eligible, key=lambda value: (-value["scores"][channel], value["id"]))]
        for channel in RRF_WEIGHTS
    }
    fused = reciprocal_rank_fusion(rankings, weights=RRF_WEIGHTS, allowed_ids={item["id"] for item in eligible})
    eligible_by_id = {item["id"]: item for item in eligible}
    best_scores = {
        channel: max((item["scores"][channel] for item in eligible), default=0.0)
        for channel in RRF_WEIGHTS
    }
    ranked = []
    for position, fused_item in enumerate(fused):
        item = {**eligible_by_id[fused_item["id"]], **fused_item}
        confidence, confidence_signals = _confidence(item["scores"], best_scores)
        item["confidence_basis"] = "relative-channel-agreement"
        if confidence == "低" and item["vlm_verdict"] == "confirmed":
            confidence = "中"
            item["confidence_basis"] = "vlm-confirmed-promotion"
        item["confidence"] = confidence
        item["confidence_signals"] = confidence_signals
        previous_score = fused[position - 1]["rrf_score"] if position else None
        item["tie"] = previous_score is not None and (previous_score - item["rrf_score"]) / max(previous_score, 1e-12) < 0.03
        ranked.append(item)

    vlm_review = selective_vlm_decision(fused, rankings, policy=str(data.get("vlm_policy", "auto")))
    formal = _rerank(
        [item for item in ranked if item["match_quality"] == "exact" and item["confidence"] in {"高", "中"}][
            :limit
        ]
    )
    adjacent = _rerank(
        [item for item in ranked if item["match_quality"] == "adjacent" and item["confidence"] in {"高", "中"}]
    )
    low_confidence = _rerank([item for item in ranked if item["confidence"] == "低"])
    returned_count = len(formal)
    terminal_reason = progress["stop_reason"]
    if terminal_reason == "none" and progress["live_checked"] >= LIVE_CHECK_BUDGET:
        terminal_reason = "live-check-budget-exhausted"
    if terminal_reason == "none" and progress["captured"] >= CAPTURE_BUDGET:
        terminal_reason = "capture-budget-exhausted"
    progress["effective_stop_reason"] = terminal_reason
    needs_replacements = returned_count < limit and terminal_reason == "none"
    status = "complete" if returned_count == limit else "needs-more-review" if needs_replacements else "confidence-shortfall"
    shortfall_reason = None
    continuation_reason = None
    if needs_replacements:
        continuation_reason = (
            f"Only {returned_count} exact high/medium-confidence cases qualify; continue reviewing later candidates "
            f"within the remaining {progress['remaining_live_checks']} live checks and {progress['remaining_captures']} captures."
        )
    elif returned_count < limit:
        shortfall_reason = (
            f"Only {returned_count} exact high/medium-confidence cases qualified before {terminal_reason}; "
            "low-confidence and adjacent cases were not used as padding."
        )
    return {
        "status": status,
        "query": data.get("query"),
        "fusion": "reciprocal-rank-fusion",
        "rrf_weights": RRF_WEIGHTS,
        "confidence_thresholds": {
            "strong_channel_ratio": STRONG_RATIO,
            "supporting_channel_ratio": SUPPORTING_RATIO,
            "high": "at least 3 strong channels",
            "medium": "at least 2 strong channels or at least 3 supporting channels",
        },
        "score_note": "RRF and relative channel ratios are heuristic ordering and agreement signals, not probabilities or calibrated percentages.",
        "results": formal,
        "adjacent_references": adjacent,
        "low_confidence_alternates": low_confidence,
        "target_result_count": limit,
        "returned_result_count": returned_count,
        "continuation_reason": continuation_reason,
        "shortfall_reason": shortfall_reason,
        "replacement_search": {
            "required": needs_replacements,
            "missing_count": max(0, limit - returned_count),
            "action": (
                "continue-reviewing-candidates"
                if needs_replacements
                else "report-confidence-shortfall"
                if returned_count < limit
                else "none"
            ),
            "review_progress": progress,
        },
        "eligible_count": len(ranked),
        "qualifying_result_count": len(formal),
        "adjacent_reference_count": len(adjacent),
        "low_confidence_alternate_count": len(low_confidence),
        "excluded": excluded,
        "vlm_review": vlm_review,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = rank_manifest(data, limit=args.limit)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))

    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
