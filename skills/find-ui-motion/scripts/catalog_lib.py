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
QUERY_EXPANSIONS_FILE = REFERENCES_DIR / "query-expansions.json"
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
            search_terms = record.get("search_terms")
            if search_terms is not None and (
                not isinstance(search_terms, list)
                or not all(isinstance(item, str) and item for item in search_terms)
            ):
                errors.append(f"{prefix}: search_terms must be a string array when present")
            source_evidence = record.get("source_evidence")
            if source_evidence is not None:
                if not isinstance(source_evidence, dict):
                    errors.append(f"{prefix}: source_evidence must be an object when present")
                else:
                    evidence_kind = source_evidence.get("kind")
                    if evidence_kind == "public-list-api":
                        if not is_https_url(source_evidence.get("official_media_url", "")):
                            errors.append(f"{prefix}: source_evidence.official_media_url must be HTTPS")
                        if not is_https_url(source_evidence.get("runtime_file_url", "")):
                            errors.append(f"{prefix}: source_evidence.runtime_file_url must be HTTPS")
                        for dimension in ("width", "height"):
                            value = source_evidence.get(dimension)
                            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                                errors.append(f"{prefix}: source_evidence.{dimension} must be positive")
                        for checked_field in ("media_range_verified_at", "runtime_range_verified_at"):
                            checked_value = source_evidence.get(checked_field)
                            if checked_value is not None and not _valid_date(checked_value):
                                errors.append(f"{prefix}: source_evidence.{checked_field} must be YYYY-MM-DD when present")
                    elif evidence_kind == "public-sitemap":
                        if not is_https_url(source_evidence.get("sitemap_url", "")):
                            errors.append(f"{prefix}: source_evidence.sitemap_url must be HTTPS")
                        if not _valid_date(source_evidence.get("discovered_at")):
                            errors.append(f"{prefix}: source_evidence.discovered_at must be YYYY-MM-DD")
                    elif evidence_kind == "public-index-page":
                        if not is_https_url(source_evidence.get("index_url", "")):
                            errors.append(f"{prefix}: source_evidence.index_url must be HTTPS")
                        if not _valid_date(source_evidence.get("discovered_at")):
                            errors.append(f"{prefix}: source_evidence.discovered_at must be YYYY-MM-DD")
                    else:
                        errors.append(f"{prefix}: unsupported source_evidence.kind")
            verification = record.get("verification")
            if verification is not None:
                if not isinstance(verification, dict):
                    errors.append(f"{prefix}: verification must be an object when present")
                else:
                    verification_kind = verification.get("kind")
                    if verification_kind not in {"official-media-frame-difference", "browser-page-motion"}:
                        errors.append(f"{prefix}: unsupported verification.kind")
                    if not _valid_date(verification.get("verified_at")):
                        errors.append(f"{prefix}: verification.verified_at must be YYYY-MM-DD")
                    if verification_kind == "official-media-frame-difference":
                        ratio = verification.get("changed_pixel_ratio")
                        difference = verification.get("mean_absolute_difference")
                        if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not 0 <= ratio <= 1:
                            errors.append(f"{prefix}: verification.changed_pixel_ratio must be from 0 to 1")
                        if isinstance(difference, bool) or not isinstance(difference, (int, float)) or difference < 0:
                            errors.append(f"{prefix}: verification.mean_absolute_difference must be non-negative")
                    elif verification_kind == "browser-page-motion":
                        if verification.get("target_confidence") not in {"explicit", "semantic", "fallback"}:
                            errors.append(f"{prefix}: unsupported verification.target_confidence")
                        for count_field in ("unique_frame_hashes", "running_animations"):
                            value = verification.get(count_field)
                            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                                errors.append(f"{prefix}: verification.{count_field} must be a non-negative integer")
                        if not isinstance(verification.get("video_advanced"), bool):
                            errors.append(f"{prefix}: verification.video_advanced must be boolean")
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


def load_query_expansions(path: Path = QUERY_EXPANSIONS_FILE) -> list[dict[str, Any]]:
    data = load_json(path)
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("query expansions must be a schema_version 1 object")
    groups = data.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError("query expansions must contain a non-empty groups array")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, group in enumerate(groups):
        prefix = f"query expansion groups[{index}]"
        if not isinstance(group, dict):
            raise ValueError(f"{prefix} must be an object")
        group_id = group.get("id")
        facet = group.get("facet")
        terms = group.get("terms")
        if not isinstance(group_id, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", group_id):
            raise ValueError(f"{prefix}.id must be lowercase hyphen-case")
        if group_id in seen:
            raise ValueError(f"duplicate query expansion id: {group_id}")
        if facet not in {"mechanism", "scene", "style", "platform"}:
            raise ValueError(f"{prefix}.facet is unsupported: {facet!r}")
        if not isinstance(terms, list) or len(terms) < 2 or not all(isinstance(term, str) and term.strip() for term in terms):
            raise ValueError(f"{prefix}.terms must contain at least two non-empty strings")
        seen.add(group_id)
        normalized.append({"id": group_id, "facet": facet, "terms": terms})
    return normalized


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


def _example_score(query: str, example: dict[str, Any]) -> float:
    query_norm = normalize_text(query)
    query_units = text_units(query)
    values: list[tuple[str, float]] = [(str(example.get("title", "")), 4.0)]
    values.extend((str(value), 1.5) for value in example.get("search_terms", []) if isinstance(value, str))
    score = 0.0
    for value, weight in values:
        normalized = normalize_text(value)
        if normalized and normalized in query_norm:
            score += weight * 4
        score += weight * len(query_units & text_units(value))
    return round(score, 3)


GENERIC_SEARCH_UNITS = {
    "animation",
    "effect",
    "motion",
    "style",
    "ui",
    "动效",
    "动画",
    "效果",
    "风格",
}


def lexical_units(value: str) -> set[str]:
    normalized = normalize_text(value)
    units = {
        unit
        for unit in re.findall(r"[a-z0-9][a-z0-9.+#-]*", normalized)
        if len(unit) >= 2 and unit not in GENERIC_SEARCH_UNITS
    }
    for group in re.findall(r"[\u3400-\u9fff]+", normalized):
        if len(group) >= 2:
            units.add(group)
            units.update(group[index : index + 2] for index in range(len(group) - 1))
    return {unit for unit in units if unit not in GENERIC_SEARCH_UNITS}


def _contains_term(value: str, term: str) -> bool:
    normalized_term = normalize_text(term)
    return bool(normalized_term) and normalized_term in normalize_text(value)


def _requested_query_groups(query: str, groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [group for group in groups if any(_contains_term(query, term) for term in group["terms"])]


def _query_variants(query: str, groups: list[dict[str, Any]]) -> list[str]:
    translated_terms: list[str] = []
    query_norm = normalize_text(query)
    for group in groups:
        preferred = next(
            (term for term in group["terms"] if re.search(r"[a-z]", normalize_text(term)) and normalize_text(term) not in query_norm),
            None,
        )
        if preferred and preferred not in translated_terms:
            translated_terms.append(preferred)
    variants = [query]
    if translated_terms:
        variants.append(query + " | " + " ".join(translated_terms))
    return variants


def _example_document_values(
    example: dict[str, Any],
    motion_by_id: dict[str, dict[str, Any]],
) -> list[tuple[str, float]]:
    values: list[tuple[str, float]] = [(str(example.get("title", "")), 6.0)]
    values.extend((str(value), 4.0) for value in example.get("search_terms", []) if isinstance(value, str))
    values.extend((str(value), 1.5) for value in example.get("stacks", []) if isinstance(value, str))
    trigger = example.get("trigger", {})
    if isinstance(trigger, dict) and isinstance(trigger.get("kind"), str):
        values.append((trigger["kind"], 2.0))
    for motion_id in example.get("motion_ids", []):
        motion = motion_by_id.get(str(motion_id))
        if not motion:
            continue
        values.append((motion["id"], 2.0))
        values.append((motion["category"], 2.5))
        for field, weight in (
            ("labels", 4.0),
            ("aliases", 3.5),
            ("targets", 2.5),
            ("triggers", 2.5),
            ("feel", 2.0),
            ("channels", 2.0),
            ("search_terms", 3.0),
        ):
            values.extend((str(value), weight) for value in motion[field])
    return values


def _document_lexical_score(query: str, values: list[tuple[str, float]]) -> tuple[float, list[str]]:
    query_norm = normalize_text(query)
    query_units = lexical_units(query)
    matched_units: set[str] = set()
    score = 0.0
    for value, weight in values:
        value_norm = normalize_text(value)
        if query_norm and len(query_norm) >= 3 and query_norm in value_norm:
            score += weight * 4
        overlap = query_units & lexical_units(value)
        matched_units.update(overlap)
        score += weight * len(overlap)
    return round(score, 3), sorted(matched_units)


def _direct_coverage(query: str, score: float, matched_units: list[str]) -> str:
    query_units = lexical_units(query)
    if not query_units:
        return "gap"
    required = max(1, (len(query_units) * 7 + 9) // 10)
    if len(matched_units) >= required and score >= 4.0:
        return "exact"
    if matched_units or score > 0:
        return "adjacent"
    return "gap"


def _expanded_coverage(
    direct: str,
    facet_values: dict[str, list[str]],
    requested_groups: list[dict[str, Any]],
) -> tuple[str, list[str], list[str], list[str]]:
    matched = [
        group["id"]
        for group in requested_groups
        if any(
            _contains_term(value, term)
            for value in facet_values[group["facet"]]
            for term in group["terms"]
        )
    ]
    required = [group["id"] for group in requested_groups if group["facet"] != "platform"]
    missing = [group_id for group_id in required if group_id not in matched]
    matched_facets = sorted({group["facet"] for group in requested_groups if group["id"] in matched})
    if required and not missing:
        coverage = "exact"
    elif matched:
        coverage = "adjacent"
    else:
        coverage = direct
    return coverage, matched, missing, matched_facets


def _facet_document_values(
    example: dict[str, Any],
    motion_by_id: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    title = str(example.get("title", ""))
    example_terms = [str(value) for value in example.get("search_terms", []) if isinstance(value, str)]
    trigger = example.get("trigger", {})
    trigger_kind = str(trigger.get("kind", "")) if isinstance(trigger, dict) else ""
    values = {
        "mechanism": [title, *example_terms],
        "scene": [title, trigger_kind],
        "style": [title, *example_terms],
        "platform": [str(value) for value in example.get("stacks", []) if isinstance(value, str)],
    }
    for motion_id in example.get("motion_ids", []):
        motion = motion_by_id.get(str(motion_id))
        if not motion:
            continue
        values["mechanism"].extend(
            [motion["id"], motion["category"], *motion["labels"], *motion["aliases"], *motion["channels"], *motion["search_terms"]]
        )
        values["scene"].extend(
            [*motion["labels"], *motion["aliases"], *motion["targets"], *motion["triggers"], *motion["search_terms"]]
        )
        values["style"].extend([*motion["labels"], *motion["aliases"], *motion["feel"]])
        values["platform"].extend(motion["stacks"])
    return values


def _example_matches_filters(
    example: dict[str, Any],
    site_by_id: dict[str, dict[str, Any]],
    *,
    stack: str | None,
    capability: str | None,
    kind: str | None,
) -> bool:
    site = site_by_id.get(example["site_id"])
    if not site:
        return False
    if stack and stack not in example.get("stacks", []):
        return False
    if capability and capability not in site["capabilities"]:
        return False
    if kind and kind != site["kind"]:
        return False
    return True


COVERAGE_RANK = {"gap": 0, "adjacent": 1, "exact": 2}
FACET_SCORE = {"mechanism": 8.0, "scene": 6.0, "style": 5.0, "platform": 2.0}
STAGE_RANK = {"taxonomy": 0, "global": 1, "global-expanded": 2}


def _enrich_candidate(
    example: dict[str, Any],
    *,
    query: str,
    motion_by_id: dict[str, dict[str, Any]],
    requested_groups: list[dict[str, Any]],
    retrieval_stage: str,
    expanded: bool,
) -> dict[str, Any]:
    values = _example_document_values(example, motion_by_id)
    direct_score, matched_units = _document_lexical_score(query, values)
    direct = _direct_coverage(query, direct_score, matched_units)
    matched_groups: list[str] = []
    missing_groups: list[str] = []
    matched_facets: list[str] = []
    matched_mechanism_groups: list[str] = []
    coverage = direct
    expansion_score = 0.0
    if expanded:
        coverage, matched_groups, missing_groups, matched_facets = _expanded_coverage(
            direct,
            _facet_document_values(example, motion_by_id),
            requested_groups,
        )
        group_by_id = {group["id"]: group for group in requested_groups}
        matched_mechanism_groups = [
            group_id for group_id in matched_groups if group_by_id[group_id]["facet"] == "mechanism"
        ]
        expansion_score = sum(FACET_SCORE[group_by_id[group_id]["facet"]] for group_id in matched_groups)
    existing_score = float(example.get("recall_score", 0.0))
    return {
        **example,
        "matched_motion_ids": list(dict.fromkeys(example.get("matched_motion_ids", example.get("motion_ids", [])))),
        "recall_score": round(max(existing_score, direct_score + expansion_score), 3),
        "coverage": coverage,
        "matched_query_units": matched_units,
        "matched_query_groups": matched_groups,
        "matched_mechanism_groups": matched_mechanism_groups,
        "missing_query_groups": missing_groups,
        "matched_facets": matched_facets,
        "retrieval_stages": list(dict.fromkeys([*example.get("retrieval_stages", []), retrieval_stage])),
    }


def _sort_candidates(candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    ranked = sorted(
        candidates,
        key=lambda example: (
            -COVERAGE_RANK[example["coverage"]],
            -len(example.get("matched_mechanism_groups", [])),
            -len(example.get("matched_query_groups", [])),
            example["last_verified"] is None,
            -float(example["recall_score"]),
            -int(example["last_shallow_check"].replace("-", "")),
            example["id"],
        ),
    )
    return _diversify_examples(ranked, limit)


def _global_candidate_pool(
    query: str,
    examples: list[dict[str, Any]],
    *,
    motion_by_id: dict[str, dict[str, Any]],
    site_by_id: dict[str, dict[str, Any]],
    requested_groups: list[dict[str, Any]],
    stack: str | None,
    capability: str | None,
    kind: str | None,
    candidate_limit: int,
    expanded: bool,
) -> tuple[list[dict[str, Any]], int]:
    stage = "global-expanded" if expanded else "global"
    candidates: list[dict[str, Any]] = []
    scanned = 0
    for example in examples:
        if not _example_matches_filters(
            example,
            site_by_id,
            stack=stack,
            capability=capability,
            kind=kind,
        ):
            continue
        scanned += 1
        candidate = _enrich_candidate(
            example,
            query=query,
            motion_by_id=motion_by_id,
            requested_groups=requested_groups,
            retrieval_stage=stage,
            expanded=expanded,
        )
        if candidate["coverage"] != "gap":
            candidates.append(candidate)
    return _sort_candidates(candidates, candidate_limit), scanned


def _merge_candidate_pools(pools: list[list[dict[str, Any]]], limit: int) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for pool in pools:
        for candidate in pool:
            current = merged.get(candidate["id"])
            if current is None:
                merged[candidate["id"]] = candidate
                continue
            stages = list(dict.fromkeys([*current["retrieval_stages"], *candidate["retrieval_stages"]]))
            candidate_key = (
                COVERAGE_RANK[candidate["coverage"]],
                max(STAGE_RANK[stage] for stage in candidate["retrieval_stages"]),
                len(candidate.get("matched_mechanism_groups", [])),
                len(candidate.get("matched_query_groups", [])),
                float(candidate["recall_score"]),
            )
            current_key = (
                COVERAGE_RANK[current["coverage"]],
                max(STAGE_RANK[stage] for stage in current["retrieval_stages"]),
                len(current.get("matched_mechanism_groups", [])),
                len(current.get("matched_query_groups", [])),
                float(current["recall_score"]),
            )
            winner = candidate if candidate_key > current_key else current
            merged[candidate["id"]] = {
                **winner,
                "recall_score": max(float(current["recall_score"]), float(candidate["recall_score"])),
                "retrieval_stages": stages,
            }
    return _sort_candidates(list(merged.values()), limit)


def _coverage_summary(candidates: list[dict[str, Any]], target_count: int) -> dict[str, Any]:
    exact_count = sum(candidate["coverage"] == "exact" for candidate in candidates)
    adjacent_count = sum(candidate["coverage"] == "adjacent" for candidate in candidates)
    status = "exact" if exact_count else "adjacent" if adjacent_count else "gap"
    return {
        "status": status,
        "complete": exact_count >= target_count,
        "target_count": target_count,
        "exact_count": exact_count,
        "adjacent_count": adjacent_count,
    }


def _diversify_examples(examples: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if len(examples) <= limit:
        return examples
    first_pass_cap = max(2, (limit + 2) // 3)
    selected: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    site_counts: dict[str, int] = {}
    for example in examples:
        site_id = example["site_id"]
        if site_counts.get(site_id, 0) < first_pass_cap:
            selected.append(example)
            site_counts[site_id] = site_counts.get(site_id, 0) + 1
        else:
            deferred.append(example)
        if len(selected) == limit:
            return selected
    selected.extend(deferred[: limit - len(selected)])
    return selected


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
    candidate_limit: int = 48,
    strategy: str = "auto",
    target_count: int = 8,
) -> dict[str, Any]:
    if not 1 <= examples_per_motion <= 20:
        raise ValueError("examples_per_motion must be between 1 and 20")
    if not 1 <= candidate_limit <= 64:
        raise ValueError("candidate_limit must be between 1 and 64")
    if strategy not in {"auto", "taxonomy", "global", "expanded"}:
        raise ValueError("strategy must be auto, taxonomy, global, or expanded")
    if not 1 <= target_count <= 10:
        raise ValueError("target_count must be between 1 and 10")
    catalog, source, warnings = load_effective_catalog()
    motions, motion_errors = load_motions()
    if motion_errors:
        raise ValueError("invalid motion catalog: " + "; ".join(motion_errors))
    examples, example_source, example_errors = load_effective_examples()
    if example_errors:
        raise ValueError("invalid example index: " + "; ".join(example_errors))
    expansion_groups = load_query_expansions()
    requested_groups = _requested_query_groups(query, expansion_groups)
    query_variants = _query_variants(query, requested_groups)
    motion_by_id = {motion["id"]: motion for motion in motions}
    site_by_id = {site["id"]: site for site in catalog["sites"]}

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
                -_example_score(query, example),
                -site_score_by_id[example["site_id"]],
                -int(example["last_shallow_check"].replace("-", "")),
                example["id"],
            )
        )
        motion_examples = _diversify_examples(motion_examples, examples_per_motion)
        matches.append({"motion": motion, "score": score, "sites": sites, "examples": motion_examples})

    pooled: dict[str, dict[str, Any]] = {}
    for match in matches:
        for example in match["examples"]:
            candidate = pooled.setdefault(
                example["id"],
                {
                    **example,
                    "matched_motion_ids": [],
                    "recall_score": 0.0,
                },
            )
            if match["motion"]["id"] not in candidate["matched_motion_ids"]:
                candidate["matched_motion_ids"].append(match["motion"]["id"])
            candidate["recall_score"] = max(
                candidate["recall_score"],
                round(float(match["score"]) + _example_score(query, example), 3),
            )
    taxonomy_pool = [
        _enrich_candidate(
            example,
            query=query,
            motion_by_id=motion_by_id,
            requested_groups=requested_groups,
            retrieval_stage="taxonomy",
            expanded=False,
        )
        for example in pooled.values()
    ]
    taxonomy_pool = _sort_candidates(
        [candidate for candidate in taxonomy_pool if candidate["coverage"] != "gap"],
        candidate_limit,
    )

    trace: list[dict[str, Any]] = []
    candidate_pools: list[list[dict[str, Any]]] = []
    retrieval_level = strategy
    expanded_completed = False

    if strategy in {"auto", "taxonomy"}:
        candidate_pools.append(taxonomy_pool)
        taxonomy_coverage = _coverage_summary(taxonomy_pool, target_count)
        trace.append(
            {
                "stage": "taxonomy",
                "examples_scanned": len(pooled),
                **taxonomy_coverage,
                "coverage_status": taxonomy_coverage["status"],
                "status": "completed",
            }
        )
        retrieval_level = "taxonomy"

    candidate_pool = _merge_candidate_pools(candidate_pools, candidate_limit) if candidate_pools else []
    current_coverage = _coverage_summary(candidate_pool, target_count)

    should_run_global = strategy == "global" or (strategy == "auto" and not current_coverage["complete"])
    if should_run_global:
        global_pool, scanned = _global_candidate_pool(
            query,
            examples,
            motion_by_id=motion_by_id,
            site_by_id=site_by_id,
            requested_groups=requested_groups,
            stack=stack,
            capability=capability,
            kind=kind,
            candidate_limit=candidate_limit,
            expanded=False,
        )
        candidate_pools.append(global_pool)
        candidate_pool = _merge_candidate_pools(candidate_pools, candidate_limit)
        current_coverage = _coverage_summary(candidate_pool, target_count)
        global_coverage = _coverage_summary(global_pool, target_count)
        trace.append(
            {
                "stage": "global",
                "examples_scanned": scanned,
                **global_coverage,
                "coverage_status": global_coverage["status"],
                "status": "completed",
            }
        )
        retrieval_level = "global"
    elif strategy == "auto":
        trace.append(
            {
                "stage": "global",
                "status": "skipped",
                "examples_scanned": 0,
                "reason": "taxonomy returned the requested number of exact local candidates",
            }
        )

    should_run_expanded = strategy == "expanded" or (strategy == "auto" and not current_coverage["complete"])
    if should_run_expanded:
        expanded_pool, scanned = _global_candidate_pool(
            query,
            examples,
            motion_by_id=motion_by_id,
            site_by_id=site_by_id,
            requested_groups=requested_groups,
            stack=stack,
            capability=capability,
            kind=kind,
            candidate_limit=candidate_limit,
            expanded=True,
        )
        candidate_pools.append(expanded_pool)
        candidate_pool = _merge_candidate_pools(candidate_pools, candidate_limit)
        current_coverage = _coverage_summary(candidate_pool, target_count)
        expanded_coverage = _coverage_summary(expanded_pool, target_count)
        trace.append(
            {
                "stage": "global-expanded",
                "examples_scanned": scanned,
                **expanded_coverage,
                "coverage_status": expanded_coverage["status"],
                "status": "completed",
            }
        )
        retrieval_level = "global-expanded"
        expanded_completed = True
    elif strategy == "auto":
        trace.append(
            {
                "stage": "global-expanded",
                "status": "skipped",
                "examples_scanned": 0,
                "reason": "the preceding local stage returned the requested number of exact candidates",
            }
        )

    if strategy == "taxonomy":
        candidate_pool = taxonomy_pool
        current_coverage = _coverage_summary(candidate_pool, target_count)
    elif strategy in {"global", "expanded"}:
        candidate_pool = _merge_candidate_pools(candidate_pools, candidate_limit)
        current_coverage = _coverage_summary(candidate_pool, target_count)

    best_candidate = candidate_pool[0] if candidate_pool else None
    missing_group_ids = best_candidate.get("missing_query_groups", []) if best_candidate else [
        group["id"] for group in requested_groups if group["facet"] != "platform"
    ]
    group_by_id = {group["id"]: group for group in requested_groups}
    missing_terms = [
        next((term for term in group_by_id[group_id]["terms"] if re.search(r"[a-z]", normalize_text(term))), group_by_id[group_id]["terms"][0])
        for group_id in missing_group_ids
        if group_id in group_by_id
    ]
    external_query = query + (" | " + " ".join(missing_terms) if missing_terms else "")
    local_ladder_exhausted = expanded_completed
    external_recommended = local_ladder_exhausted and not current_coverage["complete"]
    if current_coverage["complete"]:
        external_reason = "the local catalog satisfied the requested exact-result target"
    elif not local_ladder_exhausted:
        external_reason = "local retrieval ladder not exhausted"
    elif current_coverage["exact_count"] == 0:
        external_reason = "no exact local candidate satisfies every requested mechanism, scene, and style facet"
    else:
        external_reason = (
            f"only {current_coverage['exact_count']} exact local candidates remain for a target of "
            f"{target_count}"
        )

    return {
        "query": query,
        "filters": {"stack": stack, "capability": capability, "kind": kind},
        "strategy": strategy,
        "retrieval_level": retrieval_level,
        "examples_total": len(examples),
        "query_variants": query_variants,
        "query_expansion_groups": [
            {"id": group["id"], "facet": group["facet"]} for group in requested_groups
        ],
        "catalog_version": catalog["catalog_version"],
        "catalog_source": source,
        "example_source": example_source,
        "catalog_warnings": warnings,
        "matches": matches,
        "candidate_pool": candidate_pool,
        "coverage": current_coverage,
        "retrieval_trace": trace,
        "external_search": {
            "recommended": external_recommended,
            "reason": external_reason,
            "query": external_query,
            "max_initial_queries": 1,
            "provenance_label": "外网补充",
        },
    }
