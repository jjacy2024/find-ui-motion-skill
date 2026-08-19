#!/usr/bin/env python3
"""Build a compact OpenCLIP index from task-scoped real motion captures."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from analyze_motion_media import analyze, extract_dynamic_crops
from catalog_lib import EXAMPLES_FILE, cache_dir, is_https_url, load_examples, now_iso
from openclip_backend import DEFAULT_MODEL, DEFAULT_PRETRAINED, OpenClipEncoder, OpenClipUnavailable
from visual_index import INDEX_SCHEMA_VERSION, write_metadata, write_visual_index


def _media_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _manifest_cases(data: Any) -> list[dict[str, Any]]:
    cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(cases, list) or not cases:
        raise ValueError("capture manifest must contain a non-empty cases array")
    if not all(isinstance(item, dict) for item in cases):
        raise ValueError("every capture-manifest case must be an object")
    return cases


def build_index_data(
    data: Any,
    *,
    base_dir: Path,
    encoder: Any,
    allow_unlisted: bool = False,
    flow_backend: str = "auto",
) -> tuple[dict[str, Any], dict[str, Any]]:
    examples, example_errors = load_examples(EXAMPLES_FILE)
    if example_errors:
        raise ValueError("cannot load example catalog: " + "; ".join(example_errors))
    example_by_id = {example["id"]: example for example in examples}

    case_ids: list[str] = []
    frame_embeddings = []
    dynamic_embeddings = []
    frame_offsets = [0]
    dynamic_offsets = [0]
    metadata_cases = []

    for index, record in enumerate(_manifest_cases(data)):
        case_id = str(record.get("id", "")).strip()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", case_id):
            raise ValueError(f"cases[{index}].id must be lowercase hyphen-case")
        if case_id in case_ids:
            raise ValueError(f"duplicate capture case id: {case_id}")
        catalog_record = example_by_id.get(case_id)
        if catalog_record is None and not allow_unlisted:
            raise ValueError(f"capture case {case_id} is not in examples.jsonl")

        media_values = record.get("media")
        if isinstance(media_values, str):
            media_values = [media_values]
        if not isinstance(media_values, list) or not media_values or not all(isinstance(item, str) and item for item in media_values):
            raise ValueError(f"cases[{index}].media must contain local file paths")
        media_paths = [Path(value).expanduser() for value in media_values]
        media_paths = [path if path.is_absolute() else (base_dir / path) for path in media_paths]
        if any(not path.is_file() for path in media_paths):
            raise ValueError(f"cases[{index}] contains a missing media file")

        title = str(record.get("title") or (catalog_record or {}).get("title") or case_id).strip()
        url = str(record.get("url") or (catalog_record or {}).get("url") or "").strip()
        if not title or not is_https_url(url):
            raise ValueError(f"cases[{index}] requires a title and safe HTTPS item URL")

        motion_result, keyframes = analyze(media_paths, flow_backend=flow_backend)
        _, dynamic_crops = extract_dynamic_crops(keyframes)
        full_vectors = encoder.encode_images(keyframes)
        dynamic_vectors = encoder.encode_images(dynamic_crops)
        frame_embeddings.extend(full_vectors)
        dynamic_embeddings.extend(dynamic_vectors)
        frame_offsets.append(len(frame_embeddings))
        dynamic_offsets.append(len(dynamic_embeddings))
        case_ids.append(case_id)
        metadata_cases.append(
            {
                "id": case_id,
                "title": title,
                "url": url,
                "site_id": (catalog_record or {}).get("site_id"),
                "analysis_depth": motion_result["analysis_depth"],
                "keyframe_count": len(keyframes),
                "dynamic_crop_count": len(dynamic_crops),
                "motion_signature": motion_result["motion_signature"],
                "source_media_sha256": _media_hash(media_paths),
                "captured_at": record.get("captured_at"),
                "rights_note": str(record.get("rights_note") or (catalog_record or {}).get("rights", {}).get("note") or "").strip(),
            }
        )

    import numpy as np  # type: ignore

    arrays = {
        "case_ids": case_ids,
        "frame_embeddings": np.asarray(frame_embeddings, dtype=np.float32),
        "frame_offsets": frame_offsets,
        "dynamic_embeddings": np.asarray(dynamic_embeddings, dtype=np.float32),
        "dynamic_offsets": dynamic_offsets,
    }
    metadata = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "case_count": len(case_ids),
        "encoder": encoder.metadata,
        "storage": {
            "embedding_dtype": "float16",
            "source_media_included": False,
            "note": "Only derived embeddings, hashes, and compact motion signatures are stored.",
        },
        "cases": metadata_cases,
    }
    return arrays, metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="JSON file containing task-scoped capture cases")
    default_root = cache_dir() / "visual-index"
    parser.add_argument("--index", type=Path, default=default_root / "index.npz")
    parser.add_argument("--metadata", type=Path, default=default_root / "metadata.json")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--pretrained", default=DEFAULT_PRETRAINED)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda", "mps"), default="auto")
    parser.add_argument("--flow-backend", choices=("auto", "dis", "farneback"), default="auto")
    parser.add_argument("--allow-unlisted", action="store_true", help="Allow test cases not present in examples.jsonl")
    args = parser.parse_args()

    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        encoder = OpenClipEncoder(model_name=args.model, pretrained=args.pretrained, device=args.device)
        arrays, metadata = build_index_data(
            manifest,
            base_dir=args.manifest.resolve().parent,
            encoder=encoder,
            allow_unlisted=args.allow_unlisted,
            flow_backend=args.flow_backend,
        )
        write_visual_index(args.index, **arrays)
        write_metadata(args.metadata, metadata)
    except (OSError, json.JSONDecodeError, ValueError, RuntimeError, OpenClipUnavailable) as exc:
        print(json.dumps({"status": "unavailable", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "status": "built",
                "case_count": metadata["case_count"],
                "index": str(args.index.resolve()),
                "metadata": str(args.metadata.resolve()),
                "encoder": metadata["encoder"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
