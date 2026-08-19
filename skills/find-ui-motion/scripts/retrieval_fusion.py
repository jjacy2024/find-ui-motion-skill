#!/usr/bin/env python3
"""Fuse independent retrieval rankings and decide whether VLM review is useful."""

from __future__ import annotations

from itertools import combinations
from typing import Any, Iterable


DEFAULT_RRF_K = 60


def _unique_ids(values: Iterable[Any], allowed_ids: set[str] | None = None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item_id = str(value).strip()
        if not item_id or item_id in seen or (allowed_ids is not None and item_id not in allowed_ids):
            continue
        seen.add(item_id)
        result.append(item_id)
    return result


def reciprocal_rank_fusion(
    rankings: dict[str, Iterable[Any]],
    *,
    weights: dict[str, float] | None = None,
    k: int = DEFAULT_RRF_K,
    allowed_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Return deterministic RRF results without treating source scores as calibrated."""
    if k < 1:
        raise ValueError("RRF k must be positive")
    clean_rankings = {
        name: _unique_ids(values, allowed_ids)
        for name, values in rankings.items()
        if str(name).strip()
    }
    clean_rankings = {name: values for name, values in clean_rankings.items() if values}
    if not clean_rankings:
        return []

    clean_weights: dict[str, float] = {}
    for name in clean_rankings:
        value = 1.0 if weights is None else weights.get(name, 1.0)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or float(value) <= 0:
            raise ValueError(f"RRF weight for {name!r} must be positive")
        clean_weights[name] = float(value)

    scores: dict[str, float] = {}
    contributions: dict[str, list[dict[str, Any]]] = {}
    for name, values in clean_rankings.items():
        for rank, item_id in enumerate(values, 1):
            contribution = clean_weights[name] / (k + rank)
            scores[item_id] = scores.get(item_id, 0.0) + contribution
            contributions.setdefault(item_id, []).append(
                {"channel": name, "rank": rank, "contribution": round(contribution, 8)}
            )

    ordered = sorted(scores, key=lambda item_id: (-scores[item_id], item_id))
    results: list[dict[str, Any]] = []
    for rank, item_id in enumerate(ordered, 1):
        item_contributions = sorted(contributions[item_id], key=lambda item: (item["rank"], item["channel"]))
        results.append(
            {
                "id": item_id,
                "rank": rank,
                "rrf_score": round(scores[item_id], 8),
                "channel_count": len(item_contributions),
                "contributions": item_contributions,
            }
        )
    return results


def _mean_top_overlap(rankings: dict[str, list[str]], depth: int = 5) -> float:
    non_empty = [set(values[:depth]) for values in rankings.values() if values]
    if len(non_empty) < 2:
        return 0.0
    overlaps = []
    for left, right in combinations(non_empty, 2):
        union = left | right
        overlaps.append(len(left & right) / len(union) if union else 1.0)
    return sum(overlaps) / len(overlaps)


def selective_vlm_decision(
    fused: list[dict[str, Any]],
    rankings: dict[str, Iterable[Any]],
    *,
    policy: str = "auto",
    max_candidates: int = 5,
) -> dict[str, Any]:
    """Escalate only when independent rankers disagree or the fused lead is narrow."""
    if policy not in {"auto", "always", "never"}:
        raise ValueError("VLM policy must be auto, always, or never")
    if not 1 <= max_candidates <= 5:
        raise ValueError("VLM max_candidates must be between 1 and 5")

    clean = {name: _unique_ids(values) for name, values in rankings.items()}
    clean = {name: values for name, values in clean.items() if values}
    candidate_ids = [str(item["id"]) for item in fused[:max_candidates]]
    if not fused:
        return {
            "required": False,
            "status": "unavailable",
            "reasons": ["No fused candidates are available for visual-language review."],
            "candidate_ids": [],
            "signals": {"ranker_count": len(clean), "top1_consensus": 0.0, "top5_overlap": 0.0, "lead_margin": 0.0},
        }

    top_id = str(fused[0]["id"])
    top1_votes = sum(top_id in values[:3] for values in clean.values())
    consensus = top1_votes / len(clean) if clean else 0.0
    overlap = _mean_top_overlap(clean)
    first_score = float(fused[0].get("rrf_score", 0.0))
    second_score = float(fused[1].get("rrf_score", 0.0)) if len(fused) > 1 else 0.0
    lead_margin = (first_score - second_score) / first_score if first_score > 0 else 0.0
    signals = {
        "ranker_count": len(clean),
        "top1_consensus": round(consensus, 4),
        "top5_overlap": round(overlap, 4),
        "lead_margin": round(lead_margin, 4),
    }

    if policy == "never":
        required = False
        reasons = ["VLM review was disabled by policy."]
    elif policy == "always":
        required = True
        reasons = ["VLM review was forced by policy."]
    else:
        reasons = []
        if len(clean) < 2:
            reasons.append("Fewer than two independent ranking channels are available.")
        if len(clean) >= 2 and consensus < 0.6:
            reasons.append("Independent ranking channels disagree on the leading candidates.")
        if len(fused) > 1 and lead_margin < 0.04 and consensus < 0.8:
            reasons.append("The fused lead over the next candidate is narrow.")
        if len(clean) >= 2 and overlap < 0.2:
            reasons.append("Top-five overlap across ranking channels is low.")
        required = bool(reasons)
        if not required:
            reasons = ["Independent rankers agree sufficiently; stop before VLM review."]

    return {
        "required": required,
        "status": "review" if required else "early-stop",
        "reasons": reasons,
        "candidate_ids": candidate_ids if required else [],
        "max_candidates": max_candidates,
        "signals": signals,
        "calibration_note": "Routing thresholds are heuristics until calibrated on labeled UI-motion queries.",
    }
