#!/usr/bin/env python3
"""Compact visual-index storage, late interaction, and motion-signature matching."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any


INDEX_SCHEMA_VERSION = 1


def normalize_rows(values: Any, np: Any) -> Any:
    array = np.asarray(values, dtype=np.float32)
    if array.ndim != 2:
        raise ValueError("embedding arrays must be two-dimensional")
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    return array / np.maximum(norms, 1e-12)


def _validate_offsets(offsets: Any, row_count: int, case_count: int, np: Any, name: str) -> Any:
    values = np.asarray(offsets, dtype=np.int64)
    if values.ndim != 1 or len(values) != case_count + 1:
        raise ValueError(f"{name} must contain case_count + 1 entries")
    if int(values[0]) != 0 or int(values[-1]) != row_count or np.any(values[1:] < values[:-1]):
        raise ValueError(f"{name} contains invalid boundaries")
    if np.any(values[1:] == values[:-1]):
        raise ValueError(f"{name} cannot contain empty cases")
    return values


def write_visual_index(
    path: Path,
    *,
    case_ids: list[str],
    frame_embeddings: Any,
    frame_offsets: list[int],
    dynamic_embeddings: Any,
    dynamic_offsets: list[int],
) -> None:
    import numpy as np  # type: ignore

    if not case_ids or len(set(case_ids)) != len(case_ids):
        raise ValueError("case_ids must be non-empty and unique")
    frames = normalize_rows(frame_embeddings, np)
    dynamics = normalize_rows(dynamic_embeddings, np)
    frame_bounds = _validate_offsets(frame_offsets, len(frames), len(case_ids), np, "frame_offsets")
    dynamic_bounds = _validate_offsets(dynamic_offsets, len(dynamics), len(case_ids), np, "dynamic_offsets")
    if frames.shape[1] != dynamics.shape[1]:
        raise ValueError("full-frame and dynamic embeddings must use the same dimension")

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".npz", dir=path.parent)
    os.close(fd)
    try:
        np.savez_compressed(
            temporary_name,
            schema_version=np.asarray([INDEX_SCHEMA_VERSION], dtype=np.int16),
            case_ids=np.asarray(case_ids, dtype=f"<U{max(len(item) for item in case_ids)}"),
            frame_embeddings=frames.astype(np.float16),
            frame_offsets=frame_bounds,
            dynamic_embeddings=dynamics.astype(np.float16),
            dynamic_offsets=dynamic_bounds,
        )
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def load_visual_index(path: Path) -> dict[str, Any]:
    import numpy as np  # type: ignore

    try:
        archive = np.load(path, allow_pickle=False)
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot load visual index: {exc}") from exc
    required = {
        "schema_version",
        "case_ids",
        "frame_embeddings",
        "frame_offsets",
        "dynamic_embeddings",
        "dynamic_offsets",
    }
    if missing := required - set(archive.files):
        raise ValueError(f"visual index is missing {sorted(missing)}")
    schema_version = int(archive["schema_version"][0])
    if schema_version != INDEX_SCHEMA_VERSION:
        raise ValueError(f"unsupported visual index schema {schema_version}")
    case_ids = [str(value) for value in archive["case_ids"].tolist()]
    if not case_ids or len(set(case_ids)) != len(case_ids):
        raise ValueError("visual index case IDs must be non-empty and unique")
    frames = normalize_rows(archive["frame_embeddings"], np)
    dynamics = normalize_rows(archive["dynamic_embeddings"], np)
    frame_offsets = _validate_offsets(archive["frame_offsets"], len(frames), len(case_ids), np, "frame_offsets")
    dynamic_offsets = _validate_offsets(archive["dynamic_offsets"], len(dynamics), len(case_ids), np, "dynamic_offsets")
    if frames.shape[1] != dynamics.shape[1]:
        raise ValueError("visual index embedding dimensions disagree")
    return {
        "schema_version": schema_version,
        "case_ids": case_ids,
        "frame_embeddings": frames,
        "frame_offsets": frame_offsets,
        "dynamic_embeddings": dynamics,
        "dynamic_offsets": dynamic_offsets,
    }


def write_metadata(path: Path, data: dict[str, Any]) -> None:
    payload = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def load_metadata(path: Path, expected_ids: list[str]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load visual metadata: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != INDEX_SCHEMA_VERSION:
        raise ValueError("visual metadata has an unsupported schema")
    cases = data.get("cases")
    if not isinstance(cases, list):
        raise ValueError("visual metadata cases must be an array")
    ids = [str(case.get("id", "")) for case in cases if isinstance(case, dict)]
    if ids != expected_ids:
        raise ValueError("visual metadata case ordering does not match the index")
    return data


def late_interaction_scores(query_embeddings: Any, candidate_embeddings: Any, offsets: Any) -> list[float]:
    """Average each query vector's best matching keyframe for every candidate."""
    import numpy as np  # type: ignore

    queries = normalize_rows(query_embeddings, np)
    candidates = normalize_rows(candidate_embeddings, np)
    bounds = np.asarray(offsets, dtype=np.int64)
    scores = []
    for start, end in zip(bounds[:-1], bounds[1:]):
        similarities = queries @ candidates[int(start) : int(end)].T
        scores.append(float(similarities.max(axis=1).mean()))
    return scores


def rank_ids(case_ids: list[str], scores: list[float]) -> list[str]:
    if len(case_ids) != len(scores):
        raise ValueError("case_ids and scores must have equal lengths")
    return [item_id for item_id, _ in sorted(zip(case_ids, scores), key=lambda item: (-item[1], item[0]))]


def _curve(values: Any) -> list[float]:
    if not isinstance(values, list):
        return []
    result = []
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
            result.append(float(value))
    return result


def dtw_similarity(left: Any, right: Any) -> float | None:
    """Compare normalized curve shapes while tolerating different durations."""
    a = _curve(left)
    b = _curve(right)
    if not a or not b:
        return None
    a_scale = max(max(map(abs, a)), 1e-9)
    b_scale = max(max(map(abs, b)), 1e-9)
    a = [value / a_scale for value in a]
    b = [value / b_scale for value in b]
    previous = [float("inf")] * (len(b) + 1)
    previous[0] = 0.0
    for left_value in a:
        current = [float("inf")] * (len(b) + 1)
        for column, right_value in enumerate(b, 1):
            cost = abs(left_value - right_value)
            current[column] = cost + min(current[column - 1], previous[column], previous[column - 1])
        previous = current
    distance = previous[-1] / max(len(a), len(b))
    return max(0.0, 1.0 - min(1.0, distance))


def _categorical_similarity(left: Any, right: Any) -> float | None:
    if not isinstance(left, str) or not left or not isinstance(right, str) or not right:
        return None
    if left == right:
        return 1.0
    if "mixed" in {left, right}:
        return 0.5
    if "static" in {left, right}:
        return 0.0
    return 0.15


def motion_signature_similarity(query: dict[str, Any], candidate: dict[str, Any]) -> float | None:
    components: list[tuple[float, float]] = []
    for field, weight in (("dominant_direction", 1.2), ("changed_region", 0.8), ("timing_character", 0.8)):
        value = _categorical_similarity(query.get(field), candidate.get(field))
        if value is not None:
            components.append((value, weight))
    activity = dtw_similarity(query.get("activity_curve"), candidate.get("activity_curve"))
    if activity is not None:
        components.append((activity, 1.2))

    query_hist = query.get("direction_histogram")
    candidate_hist = candidate.get("direction_histogram")
    if isinstance(query_hist, dict) and isinstance(candidate_hist, dict):
        keys = sorted(set(query_hist) | set(candidate_hist))
        left = [float(query_hist.get(key, 0.0)) for key in keys]
        right = [float(candidate_hist.get(key, 0.0)) for key in keys]
        numerator = sum(a * b for a, b in zip(left, right))
        denominator = math.sqrt(sum(a * a for a in left) * sum(b * b for b in right))
        if denominator:
            components.append((max(0.0, min(1.0, numerator / denominator)), 1.0))
    if not components:
        return None
    total_weight = sum(weight for _, weight in components)
    return sum(value * weight for value, weight in components) / total_weight


def infer_text_motion_intent(query: str) -> dict[str, str]:
    """Provide a conservative fallback; an agent may pass a richer explicit intent."""
    normalized = re.sub(r"\s+", " ", query.lower())
    result: dict[str, str] = {}
    direction_terms = {
        "up": ("向上", "上移", "上滑", "slide up", "move up", "rise"),
        "down": ("向下", "下移", "下滑", "slide down", "move down", "drop"),
        "left": ("向左", "左滑", "slide left", "move left"),
        "right": ("向右", "右滑", "slide right", "move right"),
        "mixed": ("扩散", "爆炸", "散开", "morph", "scatter", "expand"),
    }
    for value, terms in direction_terms.items():
        if any(term in normalized for term in terms):
            result["dominant_direction"] = value
            break
    region_terms = {
        "top": ("顶部", "顶栏", "header", "top"),
        "bottom": ("底部", "底栏", "bottom", "tab bar"),
        "left": ("左侧", "侧边栏", "sidebar", "left"),
        "right": ("右侧", "right"),
        "center": ("中央", "中心", "居中", "center", "modal"),
        "full": ("全屏", "整页", "full screen", "page transition"),
    }
    for value, terms in region_terms.items():
        if any(term in normalized for term in terms):
            result["changed_region"] = value
            break
    timing_terms = {
        "front-loaded": ("快速开始", "迅速出现", "先快后慢", "snappy", "fast start"),
        "rear-loaded": ("后段加速", "最后突然", "slow start"),
        "peaked": ("弹性", "回弹", "bounce", "spring", "overshoot"),
        "even": ("匀速", "均匀", "linear", "even"),
    }
    for value, terms in timing_terms.items():
        if any(term in normalized for term in terms):
            result["timing_character"] = value
            break
    return result
