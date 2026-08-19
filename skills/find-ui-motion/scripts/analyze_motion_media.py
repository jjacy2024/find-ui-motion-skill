#!/usr/bin/env python3
"""Extract compact frame-difference and optical-flow evidence from motion media."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".gif"}


def _imports():
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "visual trajectory analysis requires OpenCV and NumPy; "
            "fall back to real-keyframe visual review when they are unavailable"
        ) from exc
    return cv2, np


def _ssim(left: Any, right: Any, np: Any) -> float:
    left_values = left.astype(np.float64)
    right_values = right.astype(np.float64)
    left_mean = float(left_values.mean())
    right_mean = float(right_values.mean())
    left_variance = float(left_values.var())
    right_variance = float(right_values.var())
    covariance = float(((left_values - left_mean) * (right_values - right_mean)).mean())
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    numerator = (2 * left_mean * right_mean + c1) * (2 * covariance + c2)
    denominator = (left_mean**2 + right_mean**2 + c1) * (left_variance + right_variance + c2)
    return numerator / denominator if denominator else 1.0


def _resize(frame: Any, cv2: Any, *, max_side: int = 320) -> Any:
    height, width = frame.shape[:2]
    scale = min(1.0, max_side / max(height, width))
    if scale == 1.0:
        return frame
    return cv2.resize(frame, (max(1, round(width * scale)), max(1, round(height * scale))))


def _read_media(paths: list[Path], sample_fps: float, max_seconds: float, cv2: Any) -> tuple[list[Any], list[float], float]:
    if len(paths) == 1 and paths[0].suffix.lower() in VIDEO_SUFFIXES:
        capture = cv2.VideoCapture(str(paths[0]))
        if not capture.isOpened():
            raise ValueError(f"cannot open media: {paths[0]}")
        source_fps = capture.get(cv2.CAP_PROP_FPS) or sample_fps
        source_fps = source_fps if math.isfinite(source_fps) and source_fps > 0 else sample_fps
        stride = max(1, round(source_fps / sample_fps))
        max_source_frames = max(2, round(max_seconds * source_fps))
        frames: list[Any] = []
        times: list[float] = []
        index = 0
        while index < max_source_frames:
            ok, frame = capture.read()
            if not ok:
                break
            if index % stride == 0:
                frames.append(_resize(frame, cv2))
                times.append(index / source_fps)
            index += 1
        capture.release()
        effective_fps = source_fps / stride
        return frames, times, effective_fps

    frames = []
    for path in paths:
        frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError(f"cannot read image: {path}")
        frames.append(_resize(frame, cv2))
    times = [index / sample_fps for index in range(len(frames))]
    return frames, times, sample_fps


def _compress_curve(values: list[float], bins: int, np: Any) -> list[float]:
    if not values:
        return []
    chunks = np.array_split(np.asarray(values, dtype=float), min(bins, len(values)))
    return [round(float(chunk.mean()), 4) for chunk in chunks]


def _timing_character(values: list[float], np: Any) -> str:
    if not values or max(values) < 0.002:
        return "static"
    weights = np.asarray(values, dtype=float)
    positions = np.linspace(0.0, 1.0, len(values))
    center = float((weights * positions).sum() / max(float(weights.sum()), 1e-9))
    peak = int(np.argmax(weights)) / max(1, len(values) - 1)
    if 0.35 <= center <= 0.65 and 0.25 <= peak <= 0.75:
        return "peaked"
    if center < 0.4:
        return "front-loaded"
    if center > 0.6:
        return "rear-loaded"
    return "even"


def _region(x: float, y: float, changed_ratio: float) -> str:
    if changed_ratio > 0.72:
        return "full"
    if x < 0.34:
        return "left"
    if x > 0.66:
        return "right"
    if y < 0.34:
        return "top"
    if y > 0.66:
        return "bottom"
    return "center"


def _direction(dx: float, dy: float, magnitude: float) -> str:
    if magnitude < 0.0008:
        return "static"
    if abs(dx) < abs(dy) * 0.7:
        return "down" if dy > 0 else "up"
    if abs(dy) < abs(dx) * 0.7:
        return "right" if dx > 0 else "left"
    return "mixed"


def _flow_backend(cv2: Any, requested: str) -> tuple[str, Any | None]:
    if requested not in {"auto", "dis", "farneback"}:
        raise ValueError("flow backend must be auto, dis, or farneback")
    if requested in {"auto", "dis"} and hasattr(cv2, "DISOpticalFlow_create"):
        preset = getattr(cv2, "DISOPTICAL_FLOW_PRESET_FAST", 1)
        return "dis", cv2.DISOpticalFlow_create(preset)
    if requested == "dis":
        raise RuntimeError("this OpenCV build does not provide DIS optical flow")
    return "farneback", None


def _calculate_flow(previous: Any, current: Any, cv2: Any, backend: str, engine: Any | None) -> Any:
    if backend == "dis":
        return engine.calc(previous, current, None)
    return cv2.calcOpticalFlowFarneback(previous, current, None, 0.5, 3, 15, 3, 5, 1.2, 0)


def extract_dynamic_crops(frames: list[Any], *, threshold: int = 12, margin_ratio: float = 0.08) -> tuple[dict[str, float], list[Any]]:
    """Crop the union of changed pixels so appearance does not dominate motion retrieval."""
    cv2, np = _imports()
    if not frames:
        raise ValueError("at least one frame is required")
    target_height = min(frame.shape[0] for frame in frames)
    target_width = min(frame.shape[1] for frame in frames)
    normalized = [cv2.resize(frame, (target_width, target_height)) for frame in frames]
    if len(normalized) == 1:
        return {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0, "changed": False}, normalized

    union = np.zeros((target_height, target_width), dtype=np.uint8)
    grays = [cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) for frame in normalized]
    for previous, current in zip(grays, grays[1:]):
        union = cv2.bitwise_or(union, (cv2.absdiff(previous, current) > threshold).astype(np.uint8) * 255)
    kernel = np.ones((3, 3), dtype=np.uint8)
    union = cv2.morphologyEx(union, cv2.MORPH_CLOSE, kernel, iterations=2)
    points = cv2.findNonZero(union)
    if points is None:
        return {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0, "changed": False}, normalized

    x, y, width, height = cv2.boundingRect(points)
    margin = round(max(width, height) * margin_ratio)
    x0 = max(0, x - margin)
    y0 = max(0, y - margin)
    x1 = min(target_width, x + width + margin)
    y1 = min(target_height, y + height + margin)
    bbox = {
        "x": round(x0 / target_width, 4),
        "y": round(y0 / target_height, 4),
        "width": round((x1 - x0) / target_width, 4),
        "height": round((y1 - y0) / target_height, 4),
        "changed": True,
    }
    return bbox, [frame[y0:y1, x0:x1].copy() for frame in normalized]


def _event_keyframes(grays: list[Any], activities: list[float], max_keyframes: int, np: Any) -> tuple[list[int], dict[int, float]]:
    selected = {0, len(grays) - 1}
    event_order = sorted(range(len(activities)), key=lambda index: (-activities[index], index))
    for transition_index in event_order[: min(4, max_keyframes - len(selected))]:
        selected.add(transition_index + 1)

    while len(selected) < min(max_keyframes, len(grays)):
        remaining = [index for index in range(1, len(grays) - 1) if index not in selected]
        if not remaining:
            break
        best_index = max(
            remaining,
            key=lambda index: (
                min(1.0 - _ssim(grays[index], grays[chosen], np) for chosen in selected)
                + (activities[index - 1] if index > 0 else 0.0),
                -index,
            ),
        )
        if min(1.0 - _ssim(grays[best_index], grays[chosen], np) for chosen in selected) < 0.015:
            break
        selected.add(best_index)

    ordered = sorted(selected)
    similarities = {ordered[0]: 1.0}
    for previous, current in zip(ordered, ordered[1:]):
        similarities[current] = _ssim(grays[previous], grays[current], np)
    return ordered, similarities


def analyze(
    paths: list[Path],
    *,
    sample_fps: float = 10.0,
    max_seconds: float = 5.0,
    max_keyframes: int = 8,
    flow_backend: str = "auto",
) -> tuple[dict[str, Any], list[Any]]:
    cv2, np = _imports()
    frames, times, effective_fps = _read_media(paths, sample_fps, max_seconds, cv2)
    if len(frames) < 2:
        raise ValueError("at least two sampled frames are required")

    target_height = min(frame.shape[0] for frame in frames)
    target_width = min(frame.shape[1] for frame in frames)
    frames = [cv2.resize(frame, (target_width, target_height)) for frame in frames]
    grays = [cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) for frame in frames]

    activities: list[float] = []
    changed_ratios: list[float] = []
    centroids: list[tuple[float, float]] = []
    flow_vectors: list[tuple[float, float, float]] = []
    direction_weights = np.zeros(8, dtype=float)
    selected_backend, flow_engine = _flow_backend(cv2, flow_backend)

    for previous, current in zip(grays, grays[1:]):
        delta = cv2.absdiff(previous, current)
        activities.append(float(delta.mean() / 255.0))
        changed = delta > 12
        changed_ratio = float(changed.mean())
        changed_ratios.append(changed_ratio)
        points = np.argwhere(changed)
        if len(points):
            y, x = points.mean(axis=0)
            centroids.append((float(x / max(1, target_width - 1)), float(y / max(1, target_height - 1))))

        flow = _calculate_flow(previous, current, cv2, selected_backend, flow_engine)
        magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        active = changed & (magnitude > 0.1)
        if active.any():
            dx = float(np.median(flow[..., 0][active]) / max(1, target_width))
            dy = float(np.median(flow[..., 1][active]) / max(1, target_height))
            mag = float(np.median(magnitude[active]) / max(1, max(target_width, target_height)))
            flow_vectors.append((dx, dy, mag))
            bins = np.floor((angle[active] % (2 * np.pi)) / (2 * np.pi) * 8).astype(int) % 8
            direction_weights += np.bincount(bins, weights=magnitude[active], minlength=8)

    mean_dx = float(np.median([v[0] for v in flow_vectors])) if flow_vectors else 0.0
    mean_dy = float(np.median([v[1] for v in flow_vectors])) if flow_vectors else 0.0
    mean_magnitude = float(np.median([v[2] for v in flow_vectors])) if flow_vectors else 0.0
    centroid_x = float(np.mean([p[0] for p in centroids])) if centroids else 0.5
    centroid_y = float(np.mean([p[1] for p in centroids])) if centroids else 0.5
    changed_mean = float(np.mean(changed_ratios)) if changed_ratios else 0.0

    selected, similarities = _event_keyframes(grays, activities, max_keyframes, np)
    selected_frames = [frames[index] for index in selected]
    dynamic_bbox, _ = extract_dynamic_crops(selected_frames)
    direction_names = ["right", "down-right", "down", "down-left", "left", "up-left", "up", "up-right"]
    direction_total = float(direction_weights.sum())
    direction_histogram = {
        name: round(float(direction_weights[index] / direction_total), 4) if direction_total else 0.0
        for index, name in enumerate(direction_names)
    }
    centroid_curve = [
        {"x": round(x, 4), "y": round(y, 4)}
        for x, y in centroids
    ]
    if len(centroid_curve) > 8:
        positions = np.linspace(0, len(centroid_curve) - 1, 8).round().astype(int)
        centroid_curve = [centroid_curve[int(position)] for position in positions]

    duration = max(0.0, times[-1] - times[0])
    result = {
        "analysis_depth": "video-trajectory" if len(paths) == 1 and paths[0].suffix.lower() in VIDEO_SUFFIXES else "keyframes",
        "sampled_frame_count": len(frames),
        "motion_signature": {
            "duration_seconds": round(duration, 3),
            "effective_fps": round(effective_fps, 3),
            "optical_flow_backend": selected_backend,
            "activity_curve": _compress_curve(activities, 8, np),
            "activity_mean": round(float(np.mean(activities)), 4),
            "activity_peak": round(float(max(activities)), 4),
            "changed_area_mean": round(changed_mean, 4),
            "changed_area_peak": round(float(max(changed_ratios)), 4),
            "changed_region": _region(centroid_x, centroid_y, changed_mean),
            "dynamic_bbox": dynamic_bbox,
            "change_centroid": {"x": round(centroid_x, 4), "y": round(centroid_y, 4)},
            "centroid_curve": centroid_curve,
            "dominant_direction": _direction(mean_dx, mean_dy, mean_magnitude),
            "direction_histogram": direction_histogram,
            "median_flow": {"dx": round(mean_dx, 5), "dy": round(mean_dy, 5), "magnitude": round(mean_magnitude, 5)},
            "timing_character": _timing_character(activities, np),
            "keyframes": [
                {
                    "sample_index": index,
                    "time_seconds": round(times[index], 3),
                    "similarity_to_previous_selection": round(similarities.get(index, 1.0), 4),
                }
                for index in selected
            ],
        },
        "limitations": [
            "Trajectory metrics do not identify object semantics; inspect retained keyframes with a vision-capable model.",
            "Camera motion, page scroll, and object motion may be conflated unless the capture is controlled.",
        ],
    }
    return result, selected_frames


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("media", nargs="+", type=Path, help="one video/GIF or two or more ordered image frames")
    parser.add_argument("--sample-fps", type=float, default=10.0)
    parser.add_argument("--max-seconds", type=float, default=5.0)
    parser.add_argument("--max-keyframes", type=int, default=8)
    parser.add_argument("--flow-backend", choices=("auto", "dis", "farneback"), default="auto")
    parser.add_argument("--keyframes-dir", type=Path)
    parser.add_argument("--dynamic-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if not 1 <= args.sample_fps <= 30:
        parser.error("--sample-fps must be between 1 and 30")
    if not 0.5 <= args.max_seconds <= 15:
        parser.error("--max-seconds must be between 0.5 and 15")
    if not 2 <= args.max_keyframes <= 12:
        parser.error("--max-keyframes must be between 2 and 12")
    if any(not path.is_file() for path in args.media):
        parser.error("every media path must be an existing file")
    try:
        result, keyframes = analyze(
            args.media,
            sample_fps=args.sample_fps,
            max_seconds=args.max_seconds,
            max_keyframes=args.max_keyframes,
            flow_backend=args.flow_backend,
        )
    except (RuntimeError, ValueError) as exc:
        print(json.dumps({"status": "unavailable", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

    if args.keyframes_dir:
        cv2, _ = _imports()
        args.keyframes_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for index, frame in enumerate(keyframes, start=1):
            path = args.keyframes_dir / f"keyframe-{index:02d}.jpg"
            cv2.imwrite(str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            written.append(str(path.resolve()))
        result["keyframe_files"] = written

    if args.dynamic_dir:
        cv2, _ = _imports()
        _, dynamic_crops = extract_dynamic_crops(keyframes)
        args.dynamic_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for index, frame in enumerate(dynamic_crops, start=1):
            path = args.dynamic_dir / f"dynamic-{index:02d}.jpg"
            cv2.imwrite(str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            written.append(str(path.resolve()))
        result["dynamic_crop_files"] = written

    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
