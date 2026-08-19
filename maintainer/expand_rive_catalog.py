#!/usr/bin/env python3
"""Expand examples.jsonl from Rive Marketplace's browser-observed public listing."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXAMPLES = REPO_ROOT / "skills" / "find-ui-motion" / "references" / "examples.jsonl"
API_ROOT = "https://api-cached.rive.app/api/community-posts"
RIVE_MARKETPLACE_ROOT = "https://rive.app/marketplace"
GENERIC_TITLES = {"", "final", "test", "untitled", "new", "animation", "rive", "11"}

MOTION_RULES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("loading-spinner", ("loader", "loading", "spinner", "preloader", "wait"), "loop"),
    ("loading-progress-morph", ("progress", "completion", "upload", "download"), "loop"),
    ("loading-skeleton-shimmer", ("skeleton", "shimmer"), "loop"),
    ("loading-dots", ("typing", "ellipsis", "three dots", "bouncing dots"), "loop"),
    ("loading-logo-loop", ("logo", "brand mark"), "loop"),
    ("feedback-success-check", ("success", "checkmark", "complete", "confirmation"), "click"),
    ("feedback-error-shake", ("error", "invalid", "wrong", "denied", "shake", "shaking"), "click"),
    ("feedback-toggle-spring", ("toggle", "switch", "checkbox", "radio"), "click"),
    ("feedback-ripple", ("ripple", "tap feedback", "touch feedback"), "click"),
    ("feedback-button-press", ("button", "click", "tap", "press", "cta"), "click"),
    ("transition-tab-indicator", ("tab", "pill menu", "segmented", "navigation"), "click"),
    ("transition-container-transform", ("expand", "collapse", "accordion", "drawer", "modal"), "click"),
    ("transition-shared-element", ("shared element", "detail transition", "hero transition"), "click"),
    ("transition-page-slide", ("page transition", "screen transition", "onboarding", "swipe page"), "click"),
    ("transition-crossfade", ("crossfade", "cross fade", "fade transition"), "click"),
    ("entrance-blur-reveal", ("blur reveal", "blurred reveal"), "loop"),
    ("entrance-mask-wipe", ("mask reveal", "wipe reveal", "image reveal"), "loop"),
    ("entrance-slide-in", ("slide in", "slide-in", "enter screen"), "loop"),
    ("entrance-spring-pop", ("spring pop", "bounce in", "pop in"), "loop"),
    ("entrance-soft-fade-up", ("fade in", "intro", "appear"), "loop"),
    ("exit-fade-down", ("fade out", "disappear"), "click"),
    ("scroll-parallax", ("parallax",), "scroll"),
    ("scroll-progress", ("scroll progress", "reading progress"), "scroll"),
    ("scroll-horizontal", ("horizontal scroll", "scroll gallery"), "scroll"),
    ("scroll-reveal", ("scroll reveal", "reveal on scroll"), "scroll"),
    ("scroll-sticky-story", ("scrollytelling", "sticky story", "scroll story"), "scroll"),
    ("hover-magnetic", ("cursor follow", "mouse follow", "follow cursor", "magnetic"), "hover"),
    ("hover-tilt", ("tilt", "gyroscope", "perspective hover"), "hover"),
    ("hover-icon-nudge", ("icon hover", "hover icon"), "hover"),
    ("hover-lift-shadow", ("card hover", "hover card", "lift"), "hover"),
    ("text-typewriter", ("typewriter", "typing text"), "loop"),
    ("text-rolling-counter", ("counter", "number", "odometer", "score"), "loop"),
    ("text-scramble", ("scramble", "decode text", "glitch text"), "loop"),
    ("text-split-reveal", ("text reveal", "split text", "kinetic type"), "loop"),
    ("text-gradient-flow", ("gradient text", "text gradient"), "loop"),
    ("ambient-gradient", ("gradient", "aurora", "mesh", "glow", "color flow"), "loop"),
    ("ambient-blob", ("blob", "liquid", "fluid", "metaball", "morphing shape"), "loop"),
    ("ambient-particles", ("particle", "confetti", "spark", "snow", "rain", "firework"), "loop"),
    ("ambient-orbit", ("orbit", "planet", "solar", "radar"), "loop"),
    ("three-d-card-flip", ("card flip", "flip card"), "click"),
    ("three-d-carousel-depth", ("carousel", "slider", "coverflow", "gallery"), "click"),
    ("three-d-scroll-scene", ("3d scene", "camera", "depth", "isometric"), "scroll"),
    ("ambient-floating", ("float", "floating", "character", "avatar", "mascot", "illustration", "icon"), "loop"),
)


def _safe_https(value: Any, *, host: str | None = None, suffix: str | None = None) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    if host is not None and parsed.hostname != host:
        return False
    return suffix is None or parsed.path.endswith(suffix)


def _fetch_json(url: str, timeout: float) -> Any:
    curl = shutil.which("curl")
    if curl is None:
        raise RuntimeError("curl is required because the current Python TLS runtime cannot reach Rive reliably")
    completed = subprocess.run(
        [
            curl,
            "-LsS",
            "--fail-with-body",
            "--retry",
            "2",
            "--retry-delay",
            "1",
            "--max-time",
            str(timeout),
            "--user-agent",
            "Mozilla/5.0 find-ui-motion-catalog/0.9",
            url,
        ],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace").strip() or f"curl failed: {url}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Rive returned invalid JSON for {url}: {exc}") from exc


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized[:96]


def _display_title(revision: dict[str, Any], post_id: int, revision_id: int) -> str:
    title = str(revision.get("title") or "").strip()
    slug = str(revision.get("slug") or "")
    slug_title = re.sub(r"^\d+-\d+-", "", slug).replace("-", " ").strip()
    animation = str(revision.get("animation") or "").strip()
    artboard = str(revision.get("artboard") or "").strip()
    if title.lower() not in GENERIC_TITLES:
        return title[:160]
    for candidate in (slug_title, animation, artboard):
        if candidate and candidate.lower() not in GENERIC_TITLES:
            return candidate[:160]
    return f"Rive Marketplace {post_id}-{revision_id}"


def _search_text(revision: dict[str, Any], title: str) -> str:
    tags = revision.get("tags") if isinstance(revision.get("tags"), list) else []
    values = [
        title,
        str(revision.get("description") or ""),
        str(revision.get("animation") or ""),
        str(revision.get("artboard") or ""),
        *(str(tag) for tag in tags),
    ]
    return " ".join(values).lower()


def _classify_motion(revision: dict[str, Any], title: str) -> tuple[list[str], str]:
    haystack = _search_text(revision, title)
    matched: list[str] = []
    trigger = "loop"
    for motion_id, keywords, rule_trigger in MOTION_RULES:
        if any(re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", haystack) for keyword in keywords):
            matched.append(motion_id)
            if len(matched) == 1:
                trigger = rule_trigger
            if len(matched) == 3:
                break
    if not matched:
        if revision.get("is_animation_state_machine"):
            return ["interactive-state-machine"], "click"
        return ["ambient-illustration-loop"], "loop"
    return matched, trigger


def _record_from_post(post: Any, checked_at: str) -> dict[str, Any] | None:
    if not isinstance(post, dict) or not isinstance(post.get("community_post_id"), int):
        return None
    revisions = post.get("community_revisions")
    if not isinstance(revisions, list) or not revisions or not isinstance(revisions[0], dict):
        return None
    revision = revisions[0]
    post_id = post["community_post_id"]
    revision_id = revision.get("community_revision_id")
    slug = revision.get("slug")
    if not isinstance(revision_id, int) or not isinstance(slug, str) or not slug.strip():
        return None
    video_url = revision.get("video_url")
    width = revision.get("video_width")
    height = revision.get("video_height")
    files = revision.get("community_files")
    if (
        not _safe_https(video_url, host="public.rive.app", suffix=".mp4")
        or isinstance(width, bool)
        or not isinstance(width, (int, float))
        or width <= 0
        or isinstance(height, bool)
        or not isinstance(height, (int, float))
        or height <= 0
        or not isinstance(files, list)
    ):
        return None
    runtime_file = next(
        (
            item.get("file_url")
            for item in files
            if isinstance(item, dict) and _safe_https(item.get("file_url"), host="public.rive.app", suffix=".riv")
        ),
        None,
    )
    if runtime_file is None:
        return None

    title = _display_title(revision, post_id, revision_id)
    motion_ids, trigger_kind = _classify_motion(revision, title)
    clip = trigger_kind == "loop"
    item_url = f"{RIVE_MARKETPLACE_ROOT}/{slug.strip('/')}/"
    search_terms = sorted({unit for unit in re.findall(r"[a-z0-9][a-z0-9-]+", _search_text(revision, title)) if len(unit) > 1})[:24]
    return {
        "id": f"rive-marketplace-{post_id}-{revision_id}",
        "site_id": "rive-community",
        "title": title,
        "url": item_url,
        "preview_url": video_url,
        "motion_ids": motion_ids,
        "stacks": ["rive", "javascript", "react"],
        "preview_strategy": "official-media",
        "trigger": {
            "kind": trigger_kind,
            "target_hint": f"the visible {title} Marketplace preview",
            "settle_ms": 1600 if clip else 1000,
            "reset_hint": "reload the current Marketplace item or reset its exposed state machine",
        },
        "capture": {
            "recommended_evidence": "clip" if clip else "storyboard",
            "frame_labels": ["cycle-start", "cycle-peak", "cycle-return"] if clip else ["before", "activated", "settled"],
            "clip_seconds": 5 if clip else 4,
        },
        "rights": {
            "status": "reference-only",
            "note": "Current public Rive Marketplace listing exposed this exact item, official MP4 preview, and runtime file. Verify current remix or download permission, runtime version, creator terms, and commercial-use rights per item.",
        },
        "source_evidence": {
            "kind": "public-list-api",
            "official_media_url": video_url,
            "width": width,
            "height": height,
            "runtime_file_url": runtime_file,
        },
        "search_terms": search_terms,
        "last_shallow_check": checked_at,
        "last_verified": None,
    }


def expand_catalog(
    existing: list[dict[str, Any]],
    *,
    target_count: int,
    page_limit: int,
    timeout: float,
    checked_at: str,
    excluded_ids: set[str] | None = None,
    excluded_urls: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output = list(existing)
    seen_ids = {record.get("id") for record in existing} | (excluded_ids or set())
    seen_urls = {str(record.get("url", "")).rstrip("/") for record in existing} | (excluded_urls or set())
    before: int | None = None
    pages = 0
    fetched = 0
    rejected = 0
    while len(output) < target_count:
        query: dict[str, Any] = {"limit": page_limit}
        if before is not None:
            query["before"] = before
        url = f"{API_ROOT}?{urlencode(query)}"
        posts = _fetch_json(url, timeout)
        pages += 1
        if not isinstance(posts, list) or not posts:
            break
        fetched += len(posts)
        last_revision_id: int | None = None
        for post in posts:
            revisions = post.get("community_revisions") if isinstance(post, dict) else None
            if isinstance(revisions, list) and revisions and isinstance(revisions[0], dict):
                candidate_cursor = revisions[0].get("community_revision_id")
                if isinstance(candidate_cursor, int):
                    last_revision_id = candidate_cursor
            record = _record_from_post(post, checked_at)
            if record is None:
                rejected += 1
                continue
            canonical_url = record["url"].rstrip("/")
            if record["id"] in seen_ids or canonical_url in seen_urls:
                continue
            seen_ids.add(record["id"])
            seen_urls.add(canonical_url)
            output.append(record)
            if len(output) == target_count:
                break
        if last_revision_id is None or last_revision_id == before:
            break
        before = last_revision_id
    report = {
        "target_count": target_count,
        "final_count": len(output),
        "added_count": len(output) - len(existing),
        "pages_fetched": pages,
        "posts_fetched": fetched,
        "posts_rejected": rejected,
        "last_cursor": before,
        "checked_at": checked_at,
        "excluded_known_cases": len(excluded_ids or set()),
    }
    return output, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--target-count", type=int, default=3000)
    parser.add_argument("--page-limit", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--checked-at", default=date.today().isoformat())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--refresh-generated", action="store_true", help="Replace prior rive-marketplace-* generated records")
    parser.add_argument("--exclude-jsonl", action="append", type=Path, default=[], help="Recoverable quarantine JSONL whose records must not be reintroduced")
    args = parser.parse_args()
    if not 1 <= args.target_count <= 10000:
        parser.error("--target-count must be between 1 and 10000")
    if not 20 <= args.page_limit <= 100:
        parser.error("--page-limit must be between 20 and 100")
    if not 5 <= args.timeout <= 60:
        parser.error("--timeout must be between 5 and 60 seconds")
    try:
        date.fromisoformat(args.checked_at)
    except ValueError:
        parser.error("--checked-at must be YYYY-MM-DD")

    records = [json.loads(line) for line in args.examples.read_text(encoding="utf-8").splitlines() if line.strip()]
    excluded_ids: set[str] = set()
    excluded_urls: set[str] = set()
    for exclusion_path in args.exclude_jsonl:
        for line in exclusion_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            record = item.get("record") if isinstance(item, dict) and isinstance(item.get("record"), dict) else item
            if not isinstance(record, dict):
                continue
            if isinstance(record.get("id"), str):
                excluded_ids.add(record["id"])
            if isinstance(record.get("url"), str):
                excluded_urls.add(record["url"].rstrip("/"))
    generated_before = sum(record.get("id", "").startswith("rive-marketplace-") for record in records)
    source_records = (
        [record for record in records if not record.get("id", "").startswith("rive-marketplace-")]
        if args.refresh_generated
        else records
    )
    expanded, report = expand_catalog(
        source_records,
        target_count=args.target_count,
        page_limit=args.page_limit,
        timeout=args.timeout,
        checked_at=args.checked_at,
        excluded_ids=excluded_ids,
        excluded_urls=excluded_urls,
    )
    report["replaced_generated_count"] = generated_before if args.refresh_generated else 0
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["final_count"] < args.target_count:
        print("target count was not reached; output was not written", file=sys.stderr)
        return 1
    if args.apply:
        destination = args.output or args.examples
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in expanded)
        destination.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
