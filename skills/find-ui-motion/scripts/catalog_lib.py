#!/usr/bin/env python3
"""Shared catalog loading, validation, versioning, and search helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote_plus, urlparse


SKILL_ROOT = Path(__file__).resolve().parent.parent
REFERENCES_DIR = SKILL_ROOT / "references"
BUNDLED_CATALOG = REFERENCES_DIR / "sites.json"
MOTIONS_FILE = REFERENCES_DIR / "motions.jsonl"
EXAMPLES_FILE = REFERENCES_DIR / "examples.jsonl"
UPDATE_CONFIG = REFERENCES_DIR / "update-config.json"

ALLOWED_SITE_STATUSES = {"active", "degraded"}
ALLOWED_KINDS = {
    "code-library",
    "component-library",
    "community",
    "editor",
    "asset-library",
    "experimental",
}
ALLOWED_CAPABILITIES = {"snippet", "package", "asset", "recreate", "inspiration"}
ALLOWED_LICENSE_STATUSES = {"explicit", "item-specific", "restricted", "unclear"}
ALLOWED_AUTH = {"none", "optional", "required-for-search", "required-for-download", "unknown"}
ALLOWED_PREVIEW_STRATEGIES = {"official-media", "live-capture", "storyboard", "open-source-only"}
ALLOWED_TRIGGER_KINDS = {"mount", "hover", "click", "scroll", "loop", "manual"}
ALLOWED_PREVIEW_RIGHTS = {"reference-only", "official-media", "open-source-only", "unclear"}
ALLOWED_LINK_SCOPES = {"item", "source-with-category-preview"}
REQUIRED_SITE_FIELDS = {
    "id",
    "name",
    "status",
    "auth",
    "kind",
    "homepage",
    "routes",
    "capabilities",
    "stacks",
    "tags",
    "license",
    "added_at",
    "last_shallow_check",
    "last_deep_review",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def cache_dir() -> Path:
    override = os.environ.get("FIND_UI_MOTION_CACHE_DIR")
    return Path(override).expanduser() if override else Path.home() / ".codex" / "cache" / "find-ui-motion"


def cache_catalog_path() -> Path:
    return cache_dir() / "sites.json"


def cache_examples_path() -> Path:
    return cache_dir() / "examples.jsonl"


def cache_state_path() -> Path:
    return cache_dir() / "update-state.json"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json_bytes(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode("utf-8")


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def version_key(value: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", str(value))
    if not numbers:
        raise ValueError(f"version contains no numeric parts: {value!r}")
    return tuple(int(part) for part in numbers)


def compare_versions(left: str, right: str) -> int:
    left_key = version_key(left)
    right_key = version_key(right)
    size = max(len(left_key), len(right_key))
    left_key += (0,) * (size - len(left_key))
    right_key += (0,) * (size - len(right_key))
    return (left_key > right_key) - (left_key < right_key)


def is_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None and parsed.password is None


def _valid_date(value: Any, *, allow_null: bool = False) -> bool:
    if allow_null and value is None:
        return True
    if not isinstance(value, str):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_catalog_data(data: Any) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return ["catalog root must be an object"], warnings

    for field in ("schema_version", "catalog_version", "generated_at", "sites"):
        if field not in data:
            errors.append(f"missing root field: {field}")
    if errors:
        return errors, warnings
    if data["schema_version"] != 1:
        errors.append("schema_version must be 1")
    try:
        version_key(str(data["catalog_version"]))
    except ValueError as exc:
        errors.append(str(exc))
    if not isinstance(data["sites"], list) or not data["sites"]:
        errors.append("sites must be a non-empty array")
        return errors, warnings

    seen: set[str] = set()
    for index, site in enumerate(data["sites"]):
        prefix = f"sites[{index}]"
        if not isinstance(site, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = REQUIRED_SITE_FIELDS - set(site)
        for field in sorted(missing):
            errors.append(f"{prefix} missing field: {field}")
        if missing:
            continue

        site_id = site["id"]
        if not isinstance(site_id, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", site_id):
            errors.append(f"{prefix}.id must be lowercase hyphen-case")
        elif site_id in seen:
            errors.append(f"duplicate site id: {site_id}")
        else:
            seen.add(site_id)

        if site["status"] not in ALLOWED_SITE_STATUSES:
            errors.append(f"{prefix}.status must be active or degraded")
        if site["auth"] not in ALLOWED_AUTH:
            errors.append(f"{prefix}.auth is unsupported: {site['auth']!r}")
        if site["kind"] not in ALLOWED_KINDS:
            errors.append(f"{prefix}.kind is unsupported: {site['kind']!r}")
        if not is_https_url(site["homepage"]):
            errors.append(f"{prefix}.homepage must be a safe HTTPS URL")

        routes = site["routes"]
        if not isinstance(routes, dict) or not routes:
            errors.append(f"{prefix}.routes must be a non-empty object")
        else:
            for route_name, route_value in routes.items():
                if route_name == "categories":
                    if not isinstance(route_value, dict):
                        errors.append(f"{prefix}.routes.categories must be an object")
                        continue
                    route_items = route_value.items()
                else:
                    route_items = [(route_name, route_value)]
                for item_name, item_url in route_items:
                    if not isinstance(item_url, str) or not is_https_url(item_url.replace("{query}", "query")):
                        errors.append(f"{prefix}.routes.{item_name} must be a safe HTTPS URL template")
                    if isinstance(item_url, str) and "{" in item_url.replace("{query}", ""):
                        errors.append(f"{prefix}.routes.{item_name} contains an unsupported placeholder")

        capabilities = site["capabilities"]
        if not isinstance(capabilities, list) or not capabilities:
            errors.append(f"{prefix}.capabilities must be a non-empty array")
        elif unknown := set(capabilities) - ALLOWED_CAPABILITIES:
            errors.append(f"{prefix}.capabilities contains unsupported values: {sorted(unknown)}")

        for array_field in ("stacks", "tags"):
            value = site[array_field]
            if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
                errors.append(f"{prefix}.{array_field} must be a string array")

        license_data = site["license"]
        if not isinstance(license_data, dict) or "status" not in license_data or "url" not in license_data:
            errors.append(f"{prefix}.license must contain status and url")
        else:
            if license_data["status"] not in ALLOWED_LICENSE_STATUSES:
                errors.append(f"{prefix}.license.status is unsupported")
            license_url = license_data["url"]
            if license_url is not None and not is_https_url(license_url):
                errors.append(f"{prefix}.license.url must be null or HTTPS")

        if not _valid_date(site["added_at"]):
            errors.append(f"{prefix}.added_at must be YYYY-MM-DD")
        if not _valid_date(site["last_shallow_check"], allow_null=True):
            errors.append(f"{prefix}.last_shallow_check must be null or YYYY-MM-DD")
        if not _valid_date(site["last_deep_review"], allow_null=True):
            errors.append(f"{prefix}.last_deep_review must be null or YYYY-MM-DD")
        if site["last_deep_review"] is None:
            warnings.append(f"{site_id}: no deep browser review recorded")
        if site["status"] == "degraded":
            warnings.append(f"{site_id}: degraded sites are ranked lower")

    return errors, warnings


def load_motions(path: Path = MOTIONS_FILE) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    required = {
        "id",
        "category",
        "labels",
        "aliases",
        "targets",
        "triggers",
        "feel",
        "channels",
        "search_terms",
        "site_kinds",
        "stacks",
    }
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"motions line {line_number}: {exc}")
                continue
            if not isinstance(record, dict):
                errors.append(f"motions line {line_number}: record must be an object")
                continue
            missing = required - set(record)
            if missing:
                errors.append(f"motions line {line_number}: missing {sorted(missing)}")
                continue
            motion_id = record["id"]
            if not isinstance(motion_id, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", motion_id):
                errors.append(f"motions line {line_number}: invalid id")
                continue
            if motion_id in seen:
                errors.append(f"motions line {line_number}: duplicate id {motion_id}")
                continue
            seen.add(motion_id)
            for field in required - {"id", "category"}:
                value = record[field]
                if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
                    errors.append(f"motions line {line_number}: {field} must be a string array")
            records.append(record)
    if not records:
        errors.append("motions catalog is empty")
    return records, errors


def load_examples(
    path: Path = EXAMPLES_FILE,
    *,
    site_ids: set[str] | None = None,
    motion_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    required = {
        "id",
        "site_id",
        "title",
        "url",
        "motion_ids",
        "stacks",
        "preview_strategy",
        "trigger",
        "capture",
        "rights",
        "last_shallow_check",
        "last_verified",
    }
    try:
        handle = path.open("r", encoding="utf-8")
    except OSError as exc:
        return records, [f"examples: {exc}"]
    with handle:
        for line_number, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line:
                continue
            prefix = f"examples line {line_number}"
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{prefix}: {exc}")
                continue
            if not isinstance(record, dict):
                errors.append(f"{prefix}: record must be an object")
                continue
            missing = required - set(record)
            if missing:
                errors.append(f"{prefix}: missing {sorted(missing)}")
                continue
            example_id = record["id"]
            if not isinstance(example_id, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", example_id):
                errors.append(f"{prefix}: invalid id")
            elif example_id in seen:
                errors.append(f"{prefix}: duplicate id {example_id}")
            else:
                seen.add(example_id)

            site_id = record["site_id"]
            if not isinstance(site_id, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", site_id):
                errors.append(f"{prefix}: invalid site_id")
            elif site_ids is not None and site_id not in site_ids:
                errors.append(f"{prefix}: unknown site_id {site_id}")
            if not isinstance(record["title"], str) or not record["title"].strip():
                errors.append(f"{prefix}: title must be a non-empty string")
            if not is_https_url(record["url"]):
                errors.append(f"{prefix}: url must be a safe HTTPS URL")
            preview_url = record.get("preview_url")
            if preview_url is not None and (not isinstance(preview_url, str) or not is_https_url(preview_url)):
                errors.append(f"{prefix}: preview_url must be a safe HTTPS URL when present")
            link_scope = record.get("link_scope", "item")
            if link_scope not in ALLOWED_LINK_SCOPES:
                errors.append(f"{prefix}: unsupported link_scope")
            if link_scope == "source-with-category-preview":
                if preview_url is None:
                    errors.append(f"{prefix}: source-with-category-preview requires preview_url")
                if record["preview_strategy"] != "open-source-only":
                    errors.append(f"{prefix}: source-with-category-preview must use open-source-only")

            for field in ("motion_ids", "stacks"):
                values = record[field]
                if not isinstance(values, list) or not values or not all(isinstance(item, str) and item for item in values):
                    errors.append(f"{prefix}: {field} must be a non-empty string array")
            if motion_ids is not None and isinstance(record["motion_ids"], list):
                unknown = set(record["motion_ids"]) - motion_ids
                if unknown:
                    errors.append(f"{prefix}: unknown motion_ids {sorted(unknown)}")

            if record["preview_strategy"] not in ALLOWED_PREVIEW_STRATEGIES:
                errors.append(f"{prefix}: unsupported preview_strategy")
            trigger = record["trigger"]
            if not isinstance(trigger, dict):
                errors.append(f"{prefix}: trigger must be an object")
            else:
                if trigger.get("kind") not in ALLOWED_TRIGGER_KINDS:
                    errors.append(f"{prefix}: unsupported trigger kind")
                if not isinstance(trigger.get("target_hint"), str) or not trigger["target_hint"].strip():
                    errors.append(f"{prefix}: trigger.target_hint must be a non-empty string")
                if not isinstance(trigger.get("settle_ms"), int) or not 0 <= trigger["settle_ms"] <= 10000:
                    errors.append(f"{prefix}: trigger.settle_ms must be an integer from 0 to 10000")

            capture = record["capture"]
            if not isinstance(capture, dict):
                errors.append(f"{prefix}: capture must be an object")
            else:
                if capture.get("recommended_evidence") not in {"storyboard", "clip"}:
                    errors.append(f"{prefix}: capture.recommended_evidence must be storyboard or clip")
                labels = capture.get("frame_labels")
                if not isinstance(labels, list) or not 2 <= len(labels) <= 5 or not all(isinstance(item, str) and item for item in labels):
                    errors.append(f"{prefix}: capture.frame_labels must contain 2-5 strings")
                if not isinstance(capture.get("clip_seconds"), int) or not 1 <= capture["clip_seconds"] <= 10:
                    errors.append(f"{prefix}: capture.clip_seconds must be an integer from 1 to 10")

            rights = record["rights"]
            if not isinstance(rights, dict):
                errors.append(f"{prefix}: rights must be an object")
            else:
                if rights.get("status") not in ALLOWED_PREVIEW_RIGHTS:
                    errors.append(f"{prefix}: unsupported rights.status")
                if not isinstance(rights.get("note"), str) or not rights["note"].strip():
                    errors.append(f"{prefix}: rights.note must be a non-empty string")
            if not _valid_date(record["last_shallow_check"]):
                errors.append(f"{prefix}: last_shallow_check must be YYYY-MM-DD")
            if not _valid_date(record["last_verified"], allow_null=True):
                errors.append(f"{prefix}: last_verified must be YYYY-MM-DD or null")
            records.append(record)
    if not records:
        errors.append("examples index is empty")
    return records, errors


def load_effective_catalog() -> tuple[dict[str, Any], str, list[str]]:
    bundled = load_json(BUNDLED_CATALOG)
    bundled_errors, bundled_warnings = validate_catalog_data(bundled)
    if bundled_errors:
        raise ValueError("invalid bundled catalog: " + "; ".join(bundled_errors))

    cached_path = cache_catalog_path()
    if cached_path.exists():
        try:
            cached = load_json(cached_path)
            cached_errors, cached_warnings = validate_catalog_data(cached)
            if not cached_errors and compare_versions(str(cached["catalog_version"]), str(bundled["catalog_version"])) >= 0:
                return cached, "cache", cached_warnings
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    return bundled, "bundled", bundled_warnings


def load_effective_examples() -> tuple[list[dict[str, Any]], str, list[str]]:
    cached_path = cache_examples_path()
    if cached_path.exists():
        cached, cached_errors = load_examples(cached_path)
        if not cached_errors:
            return cached, "cache", []
    bundled, bundled_errors = load_examples(EXAMPLES_FILE)
    return bundled, "bundled", bundled_errors


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower()
    return re.sub(r"\s+", " ", value).strip()


def text_units(value: str) -> set[str]:
    normalized = normalize_text(value)
    units = set(re.findall(r"[a-z0-9][a-z0-9.+#-]*", normalized))
    for group in re.findall(r"[\u3400-\u9fff]+", normalized):
        units.update(group)
        if len(group) > 1:
            units.update(group[index : index + 2] for index in range(len(group) - 1))
    return {unit for unit in units if unit}


def _motion_score(query: str, motion: dict[str, Any]) -> float:
    query_norm = normalize_text(query)
    query_units = text_units(query)
    fields: list[tuple[Iterable[str], float]] = [
        (motion["labels"], 4.0),
        (motion["aliases"], 3.5),
        (motion["targets"], 2.0),
        (motion["triggers"], 2.0),
        (motion["feel"], 2.0),
        (motion["channels"], 1.5),
        (motion["search_terms"], 1.0),
        ([motion["category"]], 2.0),
    ]
    score = 0.0
    for values, weight in fields:
        for value in values:
            normalized = normalize_text(value)
            if normalized and normalized in query_norm:
                score += weight * 4
            overlap = query_units & text_units(value)
            score += weight * len(overlap)
    return round(score, 3)


def _site_url(site: dict[str, Any], motion: dict[str, Any]) -> str:
    routes = site["routes"]
    query = motion["search_terms"][0]
    if isinstance(routes.get("search"), str):
        return routes["search"].replace("{query}", quote_plus(query))
    categories = routes.get("categories", {})
    if motion["category"] in categories:
        return categories[motion["category"]]
    return routes.get("examples") or site["homepage"]


def _site_score(
    site: dict[str, Any],
    motion: dict[str, Any],
    *,
    stack: str | None,
    capability: str | None,
    kind: str | None,
) -> float | None:
    if kind and site["kind"] != kind:
        return None
    if stack and stack not in site["stacks"] and "agnostic" not in site["stacks"]:
        return None
    if capability and capability not in site["capabilities"]:
        return None

    score = 1.0
    if site["kind"] in motion["site_kinds"]:
        score += 4.0
    score += len(set(site["stacks"]) & set(motion["stacks"])) * 0.5
    score += len(set(site["tags"]) & (set(motion["feel"]) | {motion["category"]})) * 0.75
    if capability and capability in site["capabilities"]:
        score += 2.0
    if site["license"]["status"] == "explicit":
        score += 0.75
    if site["status"] == "degraded":
        score *= 0.5
    return round(score, 3)


def search_catalog(
    query: str,
    *,
    stack: str | None = None,
    capability: str | None = None,
    kind: str | None = None,
    limit: int = 6,
    sites_per_motion: int = 3,
    examples_per_motion: int = 10,
) -> dict[str, Any]:
    if not 1 <= examples_per_motion <= 20:
        raise ValueError("examples_per_motion must be between 1 and 20")
    catalog, source, warnings = load_effective_catalog()
    motions, motion_errors = load_motions()
    if motion_errors:
        raise ValueError("invalid motion catalog: " + "; ".join(motion_errors))
    examples, example_source, example_errors = load_effective_examples()
    if example_errors:
        raise ValueError("invalid example index: " + "; ".join(example_errors))

    ranked = sorted(
        ((motion, _motion_score(query, motion)) for motion in motions),
        key=lambda item: (-item[1], item[0]["id"]),
    )
    positive = [item for item in ranked if item[1] > 0]
    chosen = (positive or ranked)[: max(1, limit)]

    matches: list[dict[str, Any]] = []
    for motion, score in chosen:
        site_matches: list[tuple[dict[str, Any], float]] = []
        for site in catalog["sites"]:
            site_score = _site_score(site, motion, stack=stack, capability=capability, kind=kind)
            if site_score is not None:
                site_matches.append((site, site_score))
        site_matches.sort(key=lambda item: (-item[1], item[0]["id"]))
        sites = [
            {
                "id": site["id"],
                "name": site["name"],
                "kind": site["kind"],
                "status": site["status"],
                "auth": site["auth"],
                "capabilities": site["capabilities"],
                "stacks": site["stacks"],
                "license": site["license"],
                "url": _site_url(site, motion),
                "score": site_score,
                "last_deep_review": site["last_deep_review"],
            }
            for site, site_score in site_matches[:sites_per_motion]
        ]
        site_score_by_id = {site["id"]: site_score for site, site_score in site_matches}
        motion_examples = [
            example
            for example in examples
            if motion["id"] in example["motion_ids"]
            and example["site_id"] in site_score_by_id
            and (not stack or stack in example["stacks"])
        ]
        motion_examples.sort(
            key=lambda example: (
                example["last_verified"] is None,
                -site_score_by_id[example["site_id"]],
                -int(example["last_shallow_check"].replace("-", "")),
                example["id"],
            )
        )
        motion_examples = motion_examples[:examples_per_motion]
        matches.append({"motion": motion, "score": score, "sites": sites, "examples": motion_examples})

    return {
        "query": query,
        "filters": {"stack": stack, "capability": capability, "kind": kind},
        "catalog_version": catalog["catalog_version"],
        "catalog_source": source,
        "example_source": example_source,
        "catalog_warnings": warnings,
        "matches": matches,
    }
