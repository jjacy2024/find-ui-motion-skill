#!/usr/bin/env python3
"""Fuse visually reviewed motion rankings without assuming calibrated scores."""

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


def canonical_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("candidate URL must be a safe HTTPS item URL")
    query = urlencode([(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True) if not key.lower().startswith("utm_")])
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", parts.netloc.lower(), path, query, ""))


def rank_manifest(data: dict[str, Any], limit: int = 8) -> dict[str, Any]:
    if not 1 <= limit <= 10:
        raise ValueError("limit must be between 1 and 10")
    candidates = data.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("manifest.candidates must be an array")

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
                "scores": {key: round(value, 4) for key, value in clean_scores.items()},
            }
        )

    rankings = {
        channel: [item["id"] for item in sorted(eligible, key=lambda value: (-value["scores"][channel], value["id"]))]
        for channel in RRF_WEIGHTS
    }
    fused = reciprocal_rank_fusion(rankings, weights=RRF_WEIGHTS, allowed_ids={item["id"] for item in eligible})
    eligible_by_id = {item["id"]: item for item in eligible}
    ranked = []
    for position, fused_item in enumerate(fused):
        item = {**eligible_by_id[fused_item["id"]], **fused_item}
        strong_channels = sum(contribution["rank"] <= 3 for contribution in fused_item["contributions"])
        item["confidence"] = "高" if strong_channels >= 3 else "中" if strong_channels >= 2 else "低"
        previous_score = fused[position - 1]["rrf_score"] if position else None
        item["tie"] = previous_score is not None and (previous_score - item["rrf_score"]) / max(previous_score, 1e-12) < 0.03
        ranked.append(item)

    vlm_review = selective_vlm_decision(fused, rankings, policy=str(data.get("vlm_policy", "auto")))

    returned_count = min(limit, len(ranked))
    return {
        "query": data.get("query"),
        "fusion": "reciprocal-rank-fusion",
        "rrf_weights": RRF_WEIGHTS,
        "score_note": "RRF is an internal relative ordering aid, not a probability or calibrated percentage.",
        "results": ranked[:limit],
        "target_result_count": limit,
        "returned_result_count": returned_count,
        "shortfall_reason": None if returned_count == limit else f"Only {returned_count} unique eligible visually reviewed cases were available.",
        "eligible_count": len(ranked),
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
