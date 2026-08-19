#!/usr/bin/env python3
"""Check a small remote manifest and emit a non-blocking catalog update status."""

from __future__ import annotations

import argparse
import json
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from catalog_lib import (
    UPDATE_CONFIG,
    atomic_write_bytes,
    cache_state_path,
    compare_versions,
    dump_json_bytes,
    load_effective_catalog,
    load_json,
    now_iso,
)


REQUIRED_MANIFEST_FIELDS = {
    "catalog_version",
    "schema_version",
    "min_skill_version",
    "published_at",
    "catalog_url",
    "sha256",
    "summary",
}


def load_config(path: Path) -> dict[str, Any]:
    config = load_json(path)
    if not isinstance(config, dict) or config.get("schema_version") != 1:
        raise ValueError("update config must be a schema_version 1 object")
    return config


def load_state() -> dict[str, Any]:
    path = cache_state_path()
    if not path.exists():
        return {}
    try:
        value = load_json(path)
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def write_state(state: dict[str, Any]) -> None:
    atomic_write_bytes(cache_state_path(), dump_json_bytes(state))


def validate_manifest(manifest: Any) -> list[str]:
    if not isinstance(manifest, dict):
        return ["manifest root must be an object"]
    errors = [f"missing manifest field: {field}" for field in sorted(REQUIRED_MANIFEST_FIELDS - set(manifest))]
    if errors:
        return errors
    if manifest["schema_version"] != 1:
        errors.append("manifest schema_version must be 1")
    for field in ("catalog_version", "min_skill_version"):
        try:
            compare_versions(str(manifest[field]), str(manifest[field]))
        except ValueError as exc:
            errors.append(str(exc))
    for url_field, digest_field in (("catalog_url", "sha256"), ("examples_url", "examples_sha256")):
        present = url_field in manifest or digest_field in manifest
        if not present:
            continue
        if url_field not in manifest or digest_field not in manifest:
            errors.append(f"manifest must contain both {url_field} and {digest_field}")
            continue
        if not isinstance(manifest[url_field], str) or urlparse(manifest[url_field]).scheme != "https":
            errors.append(f"manifest {url_field} must use HTTPS")
        digest = manifest[digest_field]
        if not isinstance(digest, str) or len(digest) != 64:
            errors.append(f"manifest {digest_field} must contain 64 hexadecimal characters")
        elif any(char not in "0123456789abcdefABCDEF" for char in digest):
            errors.append(f"manifest {digest_field} is not hexadecimal")
    if not isinstance(manifest["summary"], dict):
        errors.append("manifest summary must be an object")
    return errors


def _host_allowed(url: str, allowed_hosts: list[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {item.lower() for item in allowed_hosts}


def fetch_manifest(
    *,
    config: dict[str, Any],
    state: dict[str, Any],
    manifest_file: Path | None = None,
) -> tuple[dict[str, Any] | None, str | None, bool]:
    if manifest_file:
        return load_json(manifest_file), None, False

    url = config.get("manifest_url", "")
    if not config.get("enabled") or not url:
        return None, None, False
    if not _host_allowed(url, config.get("allowed_manifest_hosts", [])):
        raise ValueError("manifest host is not allowed by update-config.json")

    headers = {"Accept": "application/json", "User-Agent": "find-ui-motion/0.8.1"}
    if state.get("etag"):
        headers["If-None-Match"] = state["etag"]
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=float(config.get("timeout_seconds", 2.0))) as response:
            payload = response.read(128 * 1024)
            if len(payload) >= 128 * 1024:
                raise ValueError("manifest exceeds 128 KiB limit")
            manifest = json.loads(payload.decode("utf-8"))
            return manifest, response.headers.get("ETag"), False
    except HTTPError as exc:
        if exc.code == 304:
            cached = state.get("latest_manifest")
            return cached if isinstance(cached, dict) else None, state.get("etag"), True
        raise


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def should_skip_interval(state: dict[str, Any], config: dict[str, Any], force: bool) -> bool:
    if force:
        return False
    interval = float(config.get("check_interval_hours", 0))
    if interval <= 0:
        return False
    last = parse_timestamp(state.get("last_checked_at"))
    return bool(last and datetime.now(timezone.utc) - last < timedelta(hours=interval))


def check_update(
    *,
    config_path: Path = UPDATE_CONFIG,
    manifest_file: Path | None = None,
    force: bool = False,
    mark_notified: bool = True,
) -> dict[str, Any]:
    config = load_config(config_path)
    local_catalog, source, _ = load_effective_catalog()
    current_version = str(local_catalog["catalog_version"])
    state = load_state()

    if manifest_file is None and (not config.get("enabled") or not config.get("manifest_url")):
        return {"status": "disabled", "current_version": current_version, "catalog_source": source}
    if should_skip_interval(state, config, force):
        return {"status": "interval_skipped", "current_version": current_version, "catalog_source": source}

    try:
        manifest, etag, not_modified = fetch_manifest(config=config, state=state, manifest_file=manifest_file)
    except (HTTPError, URLError, socket.timeout, TimeoutError, OSError) as exc:
        return {
            "status": "offline_or_unreachable",
            "current_version": current_version,
            "catalog_source": source,
            "detail": exc.__class__.__name__,
        }
    except (ValueError, json.JSONDecodeError) as exc:
        return {"status": "invalid_manifest", "current_version": current_version, "error": str(exc)}

    if manifest is None:
        return {"status": "not_modified", "current_version": current_version, "catalog_source": source}
    errors = validate_manifest(manifest)
    if errors:
        return {"status": "invalid_manifest", "current_version": current_version, "errors": errors}

    latest_version = str(manifest["catalog_version"])
    state.update(
        {
            "last_checked_at": now_iso(),
            "etag": etag,
            "latest_manifest": manifest,
        }
    )

    skill_version = str(config.get("skill_version", "0"))
    if compare_versions(skill_version, str(manifest["min_skill_version"])) < 0:
        write_state(state)
        return {
            "status": "skill_update_required",
            "current_version": current_version,
            "latest_version": latest_version,
            "skill_version": skill_version,
            "min_skill_version": manifest["min_skill_version"],
            "summary": manifest["summary"],
        }

    if compare_versions(latest_version, current_version) <= 0:
        write_state(state)
        return {
            "status": "not_modified" if not_modified else "current",
            "current_version": current_version,
            "latest_version": latest_version,
            "catalog_source": source,
        }

    last_notified = state.get("last_notified_version")
    notified_at = parse_timestamp(state.get("last_notified_at"))
    remind_after = timedelta(hours=float(config.get("remind_after_hours", 168)))
    notify = last_notified != latest_version or not notified_at or datetime.now(timezone.utc) - notified_at >= remind_after
    if notify and mark_notified:
        state["last_notified_version"] = latest_version
        state["last_notified_at"] = now_iso()
    write_state(state)
    return {
        "status": "update_available",
        "notify": notify,
        "current_version": current_version,
        "latest_version": latest_version,
        "catalog_source": source,
        "summary": manifest["summary"],
        "published_at": manifest["published_at"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=UPDATE_CONFIG)
    parser.add_argument("--manifest-file", type=Path, help="Offline test fixture; bypasses remote config")
    parser.add_argument("--force", action="store_true", help="Ignore configured check interval")
    parser.add_argument("--no-mark-notified", action="store_true")
    args = parser.parse_args()
    try:
        result = check_update(
            config_path=args.config,
            manifest_file=args.manifest_file,
            force=args.force,
            mark_notified=not args.no_mark_notified,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"status": "error", "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result["status"] in {"error", "invalid_manifest"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
