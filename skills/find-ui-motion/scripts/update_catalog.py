#!/usr/bin/env python3
"""Download, validate, and explicitly apply a newer website catalog."""

from __future__ import annotations

import argparse
import gzip
import json
import socket
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from catalog_lib import (
    UPDATE_CONFIG,
    atomic_write_bytes,
    cache_catalog_path,
    cache_examples_path,
    cache_state_path,
    compare_versions,
    dump_json_bytes,
    load_effective_catalog,
    load_examples,
    load_json,
    load_motions,
    now_iso,
    sha256_bytes,
    validate_catalog_data,
)
from check_catalog_update import fetch_manifest, load_config, load_state, validate_manifest, write_state


def host_allowed(url: str, hosts: list[str]) -> bool:
    return (urlparse(url).hostname or "").lower() in {host.lower() for host in hosts}


def read_resource_bytes(
    *,
    manifest: dict,
    config: dict,
    file_path: Path | None,
    url_field: str,
    max_bytes: int,
) -> bytes:
    if file_path:
        return file_path.read_bytes()
    url = manifest[url_field]
    if not host_allowed(url, config.get("allowed_catalog_hosts", [])):
        raise ValueError(f"{url_field} host is not allowed by update-config.json")
    accept = "application/octet-stream" if url_field == "examples_url" else "application/json"
    request = Request(url, headers={"Accept": accept, "User-Agent": "find-ui-motion/0.9.5"})
    with urlopen(request, timeout=float(config.get("timeout_seconds", 2.0)) * 3) as response:
        payload = response.read(max_bytes)
    if len(payload) >= max_bytes:
        raise ValueError(f"{url_field} resource exceeds size limit")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=UPDATE_CONFIG)
    parser.add_argument("--manifest-file", type=Path, help="Offline test fixture")
    parser.add_argument("--catalog-file", type=Path, help="Offline test fixture")
    parser.add_argument("--examples-file", type=Path, help="Offline examples fixture")
    parser.add_argument("--apply", action="store_true", help="Apply only after all checks pass")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        state = load_state()
        if args.manifest_file is None and (not config.get("enabled") or not config.get("manifest_url")):
            print(json.dumps({"status": "disabled"}, ensure_ascii=False, indent=2))
            return 0
        manifest, _, _ = fetch_manifest(config=config, state=state, manifest_file=args.manifest_file)
        manifest_errors = validate_manifest(manifest)
        if manifest_errors:
            raise ValueError("; ".join(manifest_errors))
        assert manifest is not None

        local_catalog, source, _ = load_effective_catalog()
        current_version = str(local_catalog["catalog_version"])
        latest_version = str(manifest["catalog_version"])
        skill_version = str(config.get("skill_version", "0"))
        if compare_versions(skill_version, str(manifest["min_skill_version"])) < 0:
            result = {
                "status": "skill_update_required",
                "skill_version": skill_version,
                "min_skill_version": manifest["min_skill_version"],
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 2
        if compare_versions(latest_version, current_version) <= 0:
            result = {"status": "current", "current_version": current_version, "catalog_source": source}
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        payload = read_resource_bytes(
            manifest=manifest,
            config=config,
            file_path=args.catalog_file,
            url_field="catalog_url",
            max_bytes=2 * 1024 * 1024,
        )
        actual_sha = sha256_bytes(payload)
        if actual_sha.lower() != str(manifest["sha256"]).lower():
            raise ValueError(f"SHA-256 mismatch: expected {manifest['sha256']}, got {actual_sha}")
        candidate = json.loads(payload.decode("utf-8"))
        errors, warnings = validate_catalog_data(candidate)
        if errors:
            raise ValueError("catalog validation failed: " + "; ".join(errors))
        if str(candidate["catalog_version"]) != latest_version:
            raise ValueError("catalog_version does not match manifest")
        if int(candidate["schema_version"]) != int(manifest["schema_version"]):
            raise ValueError("catalog schema_version does not match manifest")

        example_payload = None
        example_count = None
        if "examples_url" in manifest:
            example_asset_payload = read_resource_bytes(
                manifest=manifest,
                config=config,
                file_path=args.examples_file,
                url_field="examples_url",
                max_bytes=8 * 1024 * 1024,
            )
            actual_examples_sha = sha256_bytes(example_asset_payload)
            if actual_examples_sha.lower() != str(manifest["examples_sha256"]).lower():
                raise ValueError(
                    f"examples SHA-256 mismatch: expected {manifest['examples_sha256']}, got {actual_examples_sha}"
                )
            if manifest.get("examples_compression") == "gzip":
                try:
                    example_payload = gzip.decompress(example_asset_payload)
                except (OSError, EOFError) as exc:
                    raise ValueError("examples gzip asset is invalid") from exc
                if len(example_payload) >= 8 * 1024 * 1024:
                    raise ValueError("decompressed examples resource exceeds size limit")
                actual_content_sha = sha256_bytes(example_payload)
                if actual_content_sha.lower() != str(manifest["examples_content_sha256"]).lower():
                    raise ValueError(
                        "examples content SHA-256 mismatch: "
                        f"expected {manifest['examples_content_sha256']}, got {actual_content_sha}"
                    )
            else:
                example_payload = example_asset_payload
            motions, motion_errors = load_motions()
            if motion_errors:
                raise ValueError("motion validation failed: " + "; ".join(motion_errors))
            with tempfile.NamedTemporaryFile(suffix=".jsonl") as fixture:
                fixture.write(example_payload)
                fixture.flush()
                examples, example_errors = load_examples(
                    Path(fixture.name),
                    site_ids={site["id"] for site in candidate["sites"]},
                    motion_ids={motion["id"] for motion in motions},
                )
            if example_errors:
                raise ValueError("example validation failed: " + "; ".join(example_errors))
            example_count = len(examples)
        elif args.examples_file is not None:
            raise ValueError("--examples-file requires examples_url and examples_sha256 in the manifest")

        result = {
            "status": "ready" if not args.apply else "applied",
            "current_version": current_version,
            "latest_version": latest_version,
            "sha256": actual_sha,
            "site_count": len(candidate["sites"]),
            "example_count": example_count,
            "warnings": warnings,
        }
        if args.apply:
            destination = cache_catalog_path()
            if destination.exists():
                atomic_write_bytes(destination.with_suffix(".json.backup"), destination.read_bytes())
            atomic_write_bytes(destination, payload)
            if example_payload is not None:
                examples_destination = cache_examples_path()
                if examples_destination.exists():
                    atomic_write_bytes(
                        examples_destination.with_suffix(".jsonl.backup"),
                        examples_destination.read_bytes(),
                    )
                atomic_write_bytes(examples_destination, example_payload)
            state.update(
                {
                    "installed_catalog_version": latest_version,
                    "installed_at": now_iso(),
                    "last_notified_version": latest_version,
                    "last_notified_at": now_iso(),
                }
            )
            write_state(state)
            result["installed_path"] = str(destination)
            if example_payload is not None:
                result["installed_examples_path"] = str(cache_examples_path())
            result["state_path"] = str(cache_state_path())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (HTTPError, URLError, socket.timeout, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
