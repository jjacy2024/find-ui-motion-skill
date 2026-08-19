#!/usr/bin/env python3
"""Build a self-contained HTML board from verified source media and metadata."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from catalog_lib import SKILL_ROOT, atomic_write_bytes


TEMPLATE = SKILL_ROOT / "assets" / "evidence-board.html"
PLACEHOLDER = "__SOURCE_EVIDENCE_DATA__"
ALLOWED_EVIDENCE = {"official-media", "live-capture", "storyboard", "open-source-only"}
ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp", "image/gif", "video/mp4", "video/webm"}
MAX_ITEM_BYTES = 25 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024


def safe_https(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None and parsed.password is None


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def resolve_media(path_value: str, manifest_dir: Path) -> Path:
    candidate = Path(path_value).expanduser()
    return (candidate if candidate.is_absolute() else manifest_dir / candidate).resolve()


def encode_media(path: Path, mime_type: str) -> str:
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{payload}"


def prepare_manifest(data: Any, manifest_dir: Path) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return None, ["manifest root must be an object"]
    if not nonempty(data.get("query")):
        errors.append("query must be a non-empty string")
    items = data.get("items")
    if not isinstance(items, list) or not items:
        errors.append("items must be a non-empty array")
        return None, errors
    if len(items) > 6:
        errors.append("items must contain no more than 6 source examples")

    prepared: dict[str, Any] = {
        "query": data.get("query", ""),
        "summary": data.get("summary", "Live-verified source examples"),
        "items": [],
    }
    total_bytes = 0
    seen: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        item_id = item.get("id")
        if not nonempty(item_id):
            errors.append(f"{prefix}.id must be a non-empty string")
        elif item_id in seen:
            errors.append(f"duplicate item id: {item_id}")
        else:
            seen.add(item_id)
        for field in ("title", "direction", "tradeoff"):
            if not nonempty(item.get(field)):
                errors.append(f"{prefix}.{field} must be a non-empty string")

        source = item.get("source")
        if not isinstance(source, dict) or not nonempty(source.get("site")) or not safe_https(source.get("url")):
            errors.append(f"{prefix}.source must contain site and a safe HTTPS url")
            source = {"site": "", "url": ""}

        evidence = item.get("evidence")
        if not isinstance(evidence, dict):
            errors.append(f"{prefix}.evidence must be an object")
            continue
        evidence_kind = evidence.get("kind")
        if evidence_kind == "synthetic" or evidence_kind not in ALLOWED_EVIDENCE:
            errors.append(f"{prefix}.evidence.kind must be real source evidence, not synthetic")
        for field in ("captured_at", "trigger", "verification"):
            if not nonempty(evidence.get(field)):
                errors.append(f"{prefix}.evidence.{field} must be a non-empty string")

        media = evidence.get("media", [])
        if not isinstance(media, list):
            errors.append(f"{prefix}.evidence.media must be an array")
            media = []
        if evidence_kind != "open-source-only" and not media:
            errors.append(f"{prefix} requires captured or official media")
        if evidence_kind == "storyboard" and len(media) < 2:
            errors.append(f"{prefix} storyboard requires at least two real source frames")

        prepared_media: list[dict[str, str]] = []
        for media_index, media_item in enumerate(media):
            media_prefix = f"{prefix}.evidence.media[{media_index}]"
            if not isinstance(media_item, dict) or not nonempty(media_item.get("path")):
                errors.append(f"{media_prefix}.path must be a non-empty string")
                continue
            path = resolve_media(media_item["path"], manifest_dir)
            if not path.is_file():
                errors.append(f"{media_prefix} file does not exist: {path}")
                continue
            size = path.stat().st_size
            if size > MAX_ITEM_BYTES:
                errors.append(f"{media_prefix} exceeds 25 MiB")
                continue
            total_bytes += size
            mime_type = media_item.get("mime_type") or mimetypes.guess_type(path.name)[0]
            if mime_type not in ALLOWED_MIME:
                errors.append(f"{media_prefix} has unsupported media type: {mime_type}")
                continue
            prepared_media.append(
                {
                    "label": str(media_item.get("label") or path.stem),
                    "mime_type": mime_type,
                    "media_type": "video" if mime_type.startswith("video/") else "image",
                    "data_uri": encode_media(path, mime_type),
                }
            )

        prepared["items"].append(
            {
                "id": item_id or "",
                "title": item.get("title", ""),
                "direction": item.get("direction", ""),
                "tradeoff": item.get("tradeoff", ""),
                "source": source,
                "evidence": {
                    "kind": evidence_kind,
                    "captured_at": evidence.get("captured_at", ""),
                    "trigger": evidence.get("trigger", ""),
                    "verification": evidence.get("verification", ""),
                    "media": prepared_media,
                },
                "motion_dna": item.get("motion_dna", {}),
                "rights_note": item.get(
                    "rights_note",
                    "Source preview is identification evidence, not permission to copy code or assets.",
                ),
            }
        )

    if total_bytes > MAX_TOTAL_BYTES:
        errors.append("embedded media exceeds 50 MiB total")
    return (None if errors else prepared), errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.manifest.expanduser().resolve()
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        prepared, errors = prepare_manifest(raw, manifest_path.parent)
        if errors:
            print(json.dumps({"status": "fail", "errors": errors}, ensure_ascii=False, indent=2))
            return 2
        template = TEMPLATE.read_text(encoding="utf-8")
        if PLACEHOLDER not in template:
            raise ValueError("evidence board template placeholder is missing")
        payload = json.dumps(prepared, ensure_ascii=False).replace("</", "<\\/")
        output = args.output.expanduser().resolve()
        atomic_write_bytes(output, template.replace(PLACEHOLDER, payload).encode("utf-8"))
        print(
            json.dumps(
                {"status": "pass", "output": str(output), "item_count": len(prepared["items"])},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "fail", "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
