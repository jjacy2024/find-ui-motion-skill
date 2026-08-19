#!/usr/bin/env python3
"""Search a compact UI-motion visual index and route only ambiguous cases to a VLM."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from analyze_motion_media import analyze, extract_dynamic_crops
from catalog_lib import cache_dir, search_catalog
from openclip_backend import OpenClipEncoder, OpenClipUnavailable
from retrieval_fusion import reciprocal_rank_fusion, selective_vlm_decision
from visual_index import (
    infer_text_motion_intent,
    late_interaction_scores,
    load_metadata,
    load_visual_index,
    motion_signature_similarity,
    rank_ids,
)


def _metadata_ranking(query: str, allowed_ids: set[str]) -> list[str]:
    result = search_catalog(query, limit=20, sites_per_motion=10, examples_per_motion=20)
    ranked = []
    seen: set[str] = set()
    for match in result["matches"]:
        for example in match.get("examples", []):
            case_id = example["id"]
            if case_id in allowed_ids and case_id not in seen:
                seen.add(case_id)
                ranked.append(case_id)
    return ranked


def _load_intent(value: str | None, query: str) -> dict[str, Any]:
    if not value:
        return infer_text_motion_intent(query)
    path = Path(value).expanduser()
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else json.loads(value)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load motion intent: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("motion intent must be a JSON object")
    return data


def _motion_ranking(intent: dict[str, Any], metadata_cases: list[dict[str, Any]]) -> tuple[list[str], dict[str, float]]:
    scored = []
    score_map = {}
    if not intent:
        return [], score_map
    for case in metadata_cases:
        similarity = motion_signature_similarity(intent, case.get("motion_signature", {}))
        if similarity is None:
            continue
        case_id = str(case["id"])
        score_map[case_id] = similarity
        scored.append((case_id, similarity))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return [case_id for case_id, _ in scored], score_map


def search_index(
    query: str,
    *,
    semantic_query: str,
    index: dict[str, Any],
    metadata: dict[str, Any],
    encoder: Any | None,
    intent: dict[str, Any],
    reference_media: list[Path] | None = None,
    vlm_policy: str = "auto",
    limit: int = 8,
) -> dict[str, Any]:
    if not 1 <= limit <= 10:
        raise ValueError("limit must be between 1 and 10")
    case_ids = index["case_ids"]
    allowed_ids = set(case_ids)
    metadata_cases = metadata["cases"]
    case_by_id = {str(case["id"]): case for case in metadata_cases}
    rankings: dict[str, list[str]] = {}
    raw_scores: dict[str, dict[str, float]] = {}

    metadata_rank = _metadata_ranking(query, allowed_ids)
    if metadata_rank:
        rankings["metadata_text"] = metadata_rank

    if encoder is not None:
        prompt_variants = [
            semantic_query,
            f"UI animation: {semantic_query}",
            f"Interface motion where {semantic_query}",
        ]
        text_vectors = encoder.encode_texts(prompt_variants)
        full_scores = late_interaction_scores(text_vectors, index["frame_embeddings"], index["frame_offsets"])
        dynamic_scores = late_interaction_scores(text_vectors, index["dynamic_embeddings"], index["dynamic_offsets"])
        rankings["openclip_full_frame"] = rank_ids(case_ids, full_scores)
        rankings["openclip_dynamic_region"] = rank_ids(case_ids, dynamic_scores)
        raw_scores["openclip_full_frame"] = dict(zip(case_ids, full_scores))
        raw_scores["openclip_dynamic_region"] = dict(zip(case_ids, dynamic_scores))

    reference_signature = None
    if reference_media:
        reference_result, reference_frames = analyze(reference_media)
        reference_signature = reference_result["motion_signature"]
        if encoder is not None:
            _, reference_dynamic = extract_dynamic_crops(reference_frames)
            reference_vectors = encoder.encode_images(reference_frames)
            reference_dynamic_vectors = encoder.encode_images(reference_dynamic)
            reference_scores = late_interaction_scores(reference_vectors, index["frame_embeddings"], index["frame_offsets"])
            reference_dynamic_scores = late_interaction_scores(
                reference_dynamic_vectors,
                index["dynamic_embeddings"],
                index["dynamic_offsets"],
            )
            rankings["reference_full_frame"] = rank_ids(case_ids, reference_scores)
            rankings["reference_dynamic_region"] = rank_ids(case_ids, reference_dynamic_scores)
            raw_scores["reference_full_frame"] = dict(zip(case_ids, reference_scores))
            raw_scores["reference_dynamic_region"] = dict(zip(case_ids, reference_dynamic_scores))

    effective_intent = reference_signature or intent
    motion_rank, motion_scores = _motion_ranking(effective_intent, metadata_cases)
    if motion_rank:
        rankings["motion_signature"] = motion_rank
        raw_scores["motion_signature"] = motion_scores

    weights = {
        "metadata_text": 1.0,
        "openclip_full_frame": 1.0,
        "openclip_dynamic_region": 1.0,
        "motion_signature": 0.8,
        "reference_full_frame": 1.2,
        "reference_dynamic_region": 1.2,
    }
    fused = reciprocal_rank_fusion(rankings, weights=weights, allowed_ids=allowed_ids)
    vlm_review = selective_vlm_decision(fused, rankings, policy=vlm_policy, max_candidates=min(5, limit))

    results = []
    for item in fused[:limit]:
        case = case_by_id[item["id"]]
        channel_scores = {
            channel: round(float(scores[item["id"]]), 5)
            for channel, scores in raw_scores.items()
            if item["id"] in scores
        }
        results.append(
            {
                **item,
                "title": case["title"],
                "url": case["url"],
                "site_id": case.get("site_id"),
                "analysis_depth": case.get("analysis_depth"),
                "channel_scores": channel_scores,
            }
        )

    returned_count = len(results)
    return {
        "status": "ok" if encoder is not None else "degraded",
        "query": query,
        "semantic_query": semantic_query,
        "case_count": len(case_ids),
        "ranking_method": "reciprocal-rank-fusion",
        "ranking_channels": list(rankings),
        "motion_intent": effective_intent,
        "results": results,
        "target_result_count": limit,
        "returned_result_count": returned_count,
        "shortfall_reason": None if returned_count == limit else f"Only {returned_count} unique eligible indexed cases were available.",
        "vlm_review": {
            **vlm_review,
            "purpose": "Inspect real keyframes only when rankers disagree; do not analyze the full catalog with a VLM.",
            "stop_instruction": "The user may reply 停止深度匹配 before the review starts or between candidates.",
        },
        "score_note": "RRF and raw channel scores are relative ranking aids, not calibrated match probabilities.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    default_root = cache_dir() / "visual-index"
    parser.add_argument("--index", type=Path, default=default_root / "index.npz")
    parser.add_argument("--metadata", type=Path, default=default_root / "metadata.json")
    parser.add_argument("--semantic-query", help="Concise English visual description for the default English OpenCLIP checkpoint")
    parser.add_argument("--intent", help="JSON object or path containing a structured motion intent")
    parser.add_argument("--reference-media", nargs="+", type=Path)
    parser.add_argument("--vlm-policy", choices=("auto", "always", "never"), default="auto")
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()

    try:
        index = load_visual_index(args.index)
        metadata = load_metadata(args.metadata, index["case_ids"])
        intent = _load_intent(args.intent, args.query)
        encoder_data = metadata.get("encoder", {})
        try:
            encoder = OpenClipEncoder(
                model_name=str(encoder_data.get("model")),
                pretrained=str(encoder_data.get("pretrained")),
            )
            visual_error = None
        except OpenClipUnavailable as exc:
            encoder = None
            visual_error = str(exc)
        result = search_index(
            args.query,
            semantic_query=args.semantic_query or args.query,
            index=index,
            metadata=metadata,
            encoder=encoder,
            intent=intent,
            reference_media=args.reference_media,
            vlm_policy=args.vlm_policy,
            limit=args.limit,
        )
        if visual_error:
            result["visual_backend_error"] = visual_error
            result["degradation"] = "Metadata and motion-signature ranks remain available; OpenCLIP ranks were skipped."
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
