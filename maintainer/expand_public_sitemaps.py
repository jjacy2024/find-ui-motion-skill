#!/usr/bin/env python3
"""Expand examples.jsonl from allowlisted public source sitemaps."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse, urlunsplit
from xml.etree import ElementTree

from check_example_health import check


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXAMPLES = REPO_ROOT / "skills" / "find-ui-motion" / "references" / "examples.jsonl"

SOURCE_CONFIGS: dict[str, dict[str, Any]] = {
    "motion": {
        "sitemap": "https://motion.dev/sitemap.xml",
        "host": "motion.dev",
        "path": re.compile(r"^/ui/(?:components|sections)/[a-z0-9-]+/?$"),
        "stacks": ["javascript", "react"],
        "preview_strategy": "live-capture",
        "rights_note": "Exact public Motion UI example URL was discovered in the current official sitemap and shallow-checked. Verify the live preview, public implementation path, package version, and current MIT terms before reuse.",
    },
    "react-bits": {
        "sitemap": "https://reactbits.dev/sitemap.xml",
        "host": "reactbits.dev",
        "path": re.compile(r"^/(?:text-animations|animations|components|backgrounds)/[a-z0-9-]+/?$"),
        "stacks": ["react"],
        "preview_strategy": "live-capture",
        "rights_note": "Exact public React Bits item URL was discovered in the current official sitemap and shallow-checked. Verify the live preview, copy path, dependencies, and current MIT plus Commons Clause restrictions before reuse.",
    },
    "magic-ui": {
        "sitemap": "https://magicui.design/sitemap.xml",
        "host": "magicui.design",
        "path": re.compile(r"^/docs/components/[a-z0-9-]+/?$"),
        "exclude_slugs": {
            "android",
            "bento-grid",
            "code-comparison",
            "dot-pattern",
            "dotted-map",
            "file-tree",
            "grid-pattern",
            "hexagon-pattern",
            "iphone",
            "noise-texture",
            "safari",
            "striped-pattern",
            "tweet-card",
        },
        "stacks": ["react"],
        "preview_strategy": "live-capture",
        "rights_note": "Exact public Magic UI component URL was discovered in the current official sitemap and shallow-checked. Verify the live preview, public copy path, dependencies, and current MIT terms before reuse.",
    },
    "originkit": {
        "sitemap": "https://www.originkit.dev/sitemap.xml",
        "host": "www.originkit.dev",
        "path": re.compile(r"^/components/[a-z0-9-]+/?$"),
        "stacks": ["react", "framer"],
        "preview_strategy": "live-capture",
        "rights_note": "Exact public Originkit component URL was discovered in the current official sitemap and shallow-checked. Use as reference until the live preview, copy or export path, dependencies, and item terms are verified.",
    },
    "design-spells": {
        "sitemap": "https://designspells.com/sitemap.xml",
        "host": "designspells.com",
        "path": re.compile(r"^/spells/[^/]+/?$"),
        "stacks": ["agnostic"],
        "preview_strategy": "official-media",
        "rights_note": "Exact public Design Spells case URL was discovered in the current official sitemap and shallow-checked. Use only for inspiration and behavior-first recreation; do not copy product assets or implementation without separate permission.",
    },
}

MOTION_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("loading-skeleton-shimmer", ("skeleton", "shimmer")),
    ("loading-progress-morph", ("progress", "upload", "download", "completion")),
    ("loading-logo-loop", ("logo-loop", "launch-screen", "splash-screen")),
    ("loading-spinner", ("loader", "loading", "spinner", "preloader")),
    ("feedback-success-check", ("success", "complete", "achievement", "unlock", "confirmation")),
    ("feedback-error-shake", ("error", "invalid", "denied", "shake")),
    ("feedback-toggle-spring", ("toggle", "switch", "theme-toggler", "checkbox", "radio")),
    ("feedback-ripple", ("ripple", "click-spark", "clickeffect", "tap-feedback")),
    ("feedback-haptic-visual", ("haptic",)),
    ("scroll-progress", ("scroll-progress", "reading-progress")),
    ("scroll-text-scrub", ("scroll-text", "scroll-velocity", "scroll-float", "text-highlight", "sync-scroll")),
    ("scroll-sticky-story", ("sticky-story", "scrollytelling", "scroll-stack")),
    ("scroll-horizontal", ("horizontal-scroll", "marquee", "infinitegallery", "infinite-gallery")),
    ("scroll-parallax", ("parallax",)),
    ("scroll-reveal", ("scroll-reveal", "reveal-on-scroll")),
    ("text-typewriter", ("typewriter", "typing-animation", "text-type", "type-sequence")),
    ("text-rolling-counter", ("count-up", "counter", "number-ticker", "numbers-change", "odometer")),
    ("text-scramble", ("scramble", "decrypted", "glitch-text", "random-letter", "letter-glitch", "encrypt", "ascii-text")),
    ("text-gradient-flow", ("gradient-text", "aurora-text", "shiny-text", "colour-sweep", "line-shadow-text")),
    ("text-kinetic-wave", ("kinetic-text", "text-wave", "character-waves", "spinning-text", "circular-text", "curved-loop", "rolling-letters", "elastic-text", "spring-text")),
    ("text-split-reveal", ("text-reveal", "split-text", "masked-heading", "mask-text", "text-emerge", "appear-text", "dia-text-reveal", "focus-reveal", "dust-text-reveal")),
    ("hover-magnetic", ("magnetic", "magnet", "cursor-follow", "follow-the-cursor")),
    ("hover-tilt", ("tilt", "gyro", "perspective-hover", "reflective-card")),
    ("hover-sheen", ("glare", "shine", "shiny-button", "specular", "sheen", "border-beam")),
    ("hover-lift-shadow", ("card-hover", "hover-card", "lift-shadow")),
    ("hover-color-fill", ("directionhover", "direction-hover", "slide-fill", "colour-fill")),
    ("transition-tab-indicator", ("tab", "pill-nav", "segmented")),
    ("transition-shared-element", ("shared-element", "hero-transition")),
    ("transition-container-transform", ("accordion", "expand", "collapse", "drawer", "modal", "bubble-menu", "staggered-menu", "folder", "stepper")),
    ("transition-page-slide", ("page-transition", "screen-transition", "navigating", "swipe-stack", "sidebar")),
    ("transition-crossfade", ("crossfade", "fade-through", "pixel-transition")),
    ("entrance-blur-reveal", ("blur-fade", "blur-reveal", "gradual-blur", "progressive-blur")),
    ("entrance-mask-wipe", ("mask-reveal", "wipe", "image-reveal", "unfold", "pixelreveal", "pixel-reveal")),
    ("entrance-stagger-list", ("animated-list", "stagger", "domino-text")),
    ("entrance-spring-pop", ("spring-pop", "bounce", "popcorn-text")),
    ("entrance-slide-in", ("slide-in", "opens-from", "line-sidebar")),
    ("entrance-soft-fade-up", ("fade-content", "fade-in", "animated-content", "appear")),
    ("three-d-card-flip", ("card-flip", "flip-card", "image-flipper", "text-3d-flip", "mechanical-flip")),
    ("three-d-carousel-depth", ("carousel", "gallery", "slider", "coverflow", "flying-posters", "tunnel")),
    ("three-d-scroll-scene", ("3d-scene", "depth-text", "model-viewer", "isometric")),
    ("ambient-gradient", ("gradient", "aurora", "iridescence", "plasma", "prism", "light-rays", "lightfall", "glow", "chrome", "dark-veil", "silk", "grainient")),
    ("ambient-blob", ("blob", "liquid", "fluid", "metaball", "meta-ball", "ferrofluid", "vortex")),
    ("ambient-particles", ("particle", "confetti", "spark", "snow", "meteor", "firework", "stardust", "rain")),
    ("ambient-orbit", ("orbit", "galaxy", "globe", "solar", "radar", "rings")),
    ("ambient-floating", ("floating", "float", "antigravity", "lanyard", "avatar", "icon-cloud")),
    ("feedback-button-press", ("button", "keycap", "cta")),
)


def _fetch_sitemap(url: str, timeout: float) -> list[str]:
    curl = shutil.which("curl")
    if curl is None:
        raise RuntimeError("curl is required")
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
            "Mozilla/5.0 find-ui-motion-catalog/1.0",
            url,
        ],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace").strip() or f"curl failed: {url}")
    try:
        root = ElementTree.fromstring(completed.stdout)
    except ElementTree.ParseError as exc:
        raise RuntimeError(f"invalid sitemap XML from {url}: {exc}") from exc
    return [node.text.strip() for node in root.findall(".//{*}loc") if isinstance(node.text, str) and node.text.strip()]


def _title_from_slug(slug: str) -> str:
    acronyms = {"3d": "3D", "ui": "UI", "svg": "SVG", "ascii": "ASCII", "iphone": "iPhone"}
    return " ".join(acronyms.get(part, part.capitalize()) for part in slug.strip('"\'()').split("-"))[:160]


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:120]


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    path = quote(unquote(parsed.path), safe="/-._~@")
    return urlunsplit(("https", parsed.netloc, path.rstrip("/"), "", ""))


def _allowed_url(site_id: str, url: str) -> bool:
    config = SOURCE_CONFIGS[site_id]
    parsed = urlparse(url)
    slug = unquote(parsed.path.rstrip("/").rsplit("/", 1)[-1])
    return (
        parsed.scheme == "https"
        and parsed.hostname == config["host"]
        and bool(config["path"].fullmatch(unquote(parsed.path)))
        and slug not in config.get("exclude_slugs", set())
    )


def _fallback(site_id: str, path: str) -> tuple[list[str], str]:
    if site_id == "react-bits" and path.startswith("/backgrounds/"):
        return ["ambient-illustration-loop"], "loop"
    if site_id == "react-bits" and path.startswith("/text-animations/"):
        return ["text-split-reveal"], "mount"
    if site_id == "design-spells":
        return ["product-microinteraction"], "manual"
    return ["interactive-component-motion"], "click"


def _classify(site_id: str, path: str, slug: str) -> tuple[list[str], str]:
    haystack = f"{path.strip('/').replace('/', '-')} {slug}".lower()
    matches: list[str] = []
    for motion_id, keywords in MOTION_RULES:
        if any(keyword in haystack for keyword in keywords):
            matches.append(motion_id)
            if len(matches) == 3:
                break
    if not matches:
        return _fallback(site_id, path)
    first = matches[0]
    if first.startswith("hover-"):
        trigger = "hover"
    elif first.startswith("scroll-"):
        trigger = "scroll"
    elif first.startswith(("ambient-", "loading-")):
        trigger = "loop"
    elif first.startswith(("text-", "entrance-")):
        trigger = "mount"
    else:
        trigger = "click"
    return matches, trigger


def _record(site_id: str, url: str, checked_at: str) -> dict[str, Any]:
    config = SOURCE_CONFIGS[site_id]
    url = _normalize_url(url)
    parsed = urlparse(url)
    slug = unquote(parsed.path.rstrip("/").rsplit("/", 1)[-1])
    title = _title_from_slug(slug)
    motion_ids, trigger = _classify(site_id, parsed.path, slug)
    clip = trigger == "loop"
    if trigger == "hover":
        frame_labels = ["rest", "hover-peak", "reset"]
        settle_ms = 800
    elif trigger == "scroll":
        frame_labels = ["before-scroll", "mid-scroll", "settled"]
        settle_ms = 1200
    elif trigger == "mount":
        frame_labels = ["before-replay", "mid-motion", "settled"]
        settle_ms = 1200
    elif trigger == "manual":
        frame_labels = ["rest", "changed", "settled"]
        settle_ms = 1200
    else:
        frame_labels = ["before", "activated", "settled"]
        settle_ms = 1000
    search_terms = sorted({token for token in re.findall(r"[a-z0-9][a-z0-9-]+", f"{slug} {title.lower()}") if len(token) > 1})[:24]
    return {
        "id": f"{site_id}-{_slugify(slug)}",
        "site_id": site_id,
        "title": title,
        "url": url.rstrip("/"),
        "motion_ids": motion_ids,
        "stacks": config["stacks"],
        "preview_strategy": config["preview_strategy"],
        "trigger": {
            "kind": trigger,
            "target_hint": f"the visible {title} example preview",
            "settle_ms": 1600 if clip else settle_ms,
            "reset_hint": "use the public replay or reset control when available; otherwise restore the initial visible state",
        },
        "capture": {
            "recommended_evidence": "clip" if clip else "storyboard",
            "frame_labels": ["cycle-start", "cycle-peak", "cycle-return"] if clip else frame_labels,
            "clip_seconds": 5 if clip else 4,
        },
        "rights": {"status": "reference-only", "note": config["rights_note"]},
        "source_evidence": {
            "kind": "public-sitemap",
            "sitemap_url": config["sitemap"],
            "discovered_at": checked_at,
        },
        "search_terms": search_terms,
        "last_shallow_check": checked_at,
        "last_verified": None,
    }


def _discover(site_id: str, timeout: float, checked_at: str, limit: int) -> list[dict[str, Any]]:
    config = SOURCE_CONFIGS[site_id]
    records: list[dict[str, Any]] = []
    for url in sorted(set(_fetch_sitemap(config["sitemap"], timeout))):
        if not _allowed_url(site_id, url):
            continue
        records.append(_record(site_id, url, checked_at))
        if len(records) == limit:
            break
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    parser.add_argument("--source", action="append", choices=sorted(SOURCE_CONFIGS), help="Repeat to select sources; defaults to all")
    parser.add_argument("--per-source-limit", type=int, default=400)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--checked-at", default=date.today().isoformat())
    parser.add_argument("--apply", action="store_true", help="Verify new wrappers and append only shell-reachable records")
    parser.add_argument("--prune-ineligible", action="store_true", help="With --apply, remove prior public-sitemap records that no longer pass the allowlist")
    parser.add_argument("--exclude-jsonl", action="append", type=Path, default=[], help="Recoverable quarantine JSONL whose records must not be reintroduced")
    args = parser.parse_args()
    if not 1 <= args.per_source_limit <= 1000:
        parser.error("--per-source-limit must be between 1 and 1000")
    if not 1 <= args.workers <= 16:
        parser.error("--workers must be between 1 and 16")
    if not 5 <= args.timeout <= 30:
        parser.error("--timeout must be between 5 and 30 seconds")
    try:
        date.fromisoformat(args.checked_at)
    except ValueError:
        parser.error("--checked-at must be YYYY-MM-DD")

    selected_sources = args.source or list(SOURCE_CONFIGS)
    original_existing = [json.loads(line) for line in args.examples.read_text(encoding="utf-8").splitlines() if line.strip()]
    existing = []
    pruned: list[dict[str, Any]] = []
    for record in original_existing:
        evidence = record.get("source_evidence") if isinstance(record.get("source_evidence"), dict) else {}
        should_review = (
            args.prune_ineligible
            and evidence.get("kind") == "public-sitemap"
            and record.get("site_id") in selected_sources
        )
        if should_review and not _allowed_url(record["site_id"], record["url"]):
            pruned.append(record)
        else:
            existing.append(record)
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
    seen_ids = {record["id"] for record in existing} | excluded_ids
    seen_urls = {record["url"].rstrip("/") for record in existing} | excluded_urls
    discovered_by_source: dict[str, int] = {}
    candidates: list[dict[str, Any]] = []
    for site_id in selected_sources:
        discovered = _discover(site_id, args.timeout, args.checked_at, args.per_source_limit)
        discovered_by_source[site_id] = len(discovered)
        for record in discovered:
            if record["id"] in seen_ids or record["url"].rstrip("/") in seen_urls:
                continue
            seen_ids.add(record["id"])
            seen_urls.add(record["url"].rstrip("/"))
            candidates.append(record)

    states: dict[str, int] = {}
    accepted: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    if args.apply:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_record = {executor.submit(check, record, args.timeout): record for record in candidates}
            for future in as_completed(future_to_record):
                result = future.result()
                states[result["state"]] = states.get(result["state"], 0) + 1
                if result["state"] == "shell-reachable":
                    accepted.append(future_to_record[future])
                else:
                    failures.append(result)
        accepted.sort(key=lambda record: (record["site_id"], record["id"]))
        output = existing + accepted
        payload = "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in output)
        args.examples.write_text(payload, encoding="utf-8")

    print(
        json.dumps(
            {
                "selected_sources": selected_sources,
                "discovered_by_source": discovered_by_source,
                "existing_count": len(original_existing),
                "pruned_count": len(pruned),
                "new_candidates": len(candidates),
                "health_states": states,
                "added_count": len(accepted),
                "final_count": len(existing) + len(accepted),
                "checked_at": args.checked_at,
                "applied": args.apply,
                "excluded_known_cases": len(excluded_ids),
                "failure_sample": failures[:30],
                "note": "Sitemap discovery plus outer-wrapper health only. last_verified remains null until current visible motion is observed.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not args.apply or not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
