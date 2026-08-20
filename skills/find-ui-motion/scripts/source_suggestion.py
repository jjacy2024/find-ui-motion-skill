#!/usr/bin/env python3
"""Evaluate and prepare a privacy-minimal new-source suggestion.

This helper never sends data or creates an Issue. It only checks the local
catalog and returns a prefilled URL after every eligibility gate passes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode, urlsplit


SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = SKILL_ROOT / "references" / "sites.json"
DEFAULT_REPOSITORY = "jjacy2024/find-ui-motion-catalog"
FIELD_LABEL = "网站名称与域名"
PROMPT_TEMPLATE = (
    "发现一个尚未收录的高质量动效来源 {domain}。"
    "是否生成来源推荐，交给 find-ui-motion Catalog 维护者审核？"
    "审核通过后会加入下一个版本的内置清单中"
)


def normalize_domain(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    parsed = urlsplit(raw if "://" in raw else f"//{raw}")
    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if hostname.startswith("www."):
        hostname = hostname[4:]
    try:
        return hostname.encode("idna").decode("ascii")
    except UnicodeError:
        return ""


def _catalog_domains(catalog_path: Path) -> set[str]:
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    domains: set[str] = set()
    for site in payload.get("sites", []):
        candidates = [site.get("homepage")]
        routes = site.get("routes") or {}
        candidates.append(routes.get("examples"))
        candidates.extend((routes.get("categories") or {}).values())
        for candidate in candidates:
            if isinstance(candidate, str):
                domain = normalize_domain(candidate)
                if domain:
                    domains.add(domain)
    return domains


def _is_catalogued(domain: str, catalog_domains: set[str]) -> bool:
    return any(domain == known or domain.endswith(f".{known}") for known in catalog_domains)


def _submission_value(site_name: str, domain: str) -> str:
    clean_name = " ".join(site_name.split()).strip()
    return f"{clean_name} — {domain}" if clean_name else domain


def _github_issue_url(repository: str, field_value: str) -> str:
    title = f"[Source suggestion] {field_value}"
    body = f"{FIELD_LABEL}：{field_value}"
    query = urlencode(
        {
            "template": "source-suggestion.md",
            "title": title,
            "body": body,
        }
    )
    return f"https://github.com/{repository}/issues/new?{query}"


def _email_url(email: str | None, field_value: str) -> str | None:
    if not email:
        return None
    recipient = email.strip()
    if not recipient:
        return None
    subject = f"[find-ui-motion] 新来源推荐: {field_value}"
    body = f"{FIELD_LABEL}：{field_value}"
    return f"mailto:{quote(recipient, safe='@,+')}?{urlencode({'subject': subject, 'body': body})}"


def evaluate_source_suggestion(
    *,
    site_name: str,
    item_url: str,
    match_quality: str,
    confidence: str,
    source_health: str,
    support_kind: str,
    concrete_item: bool,
    already_suggested: bool = False,
    catalog_path: Path = DEFAULT_CATALOG,
    repository: str = DEFAULT_REPOSITORY,
    email: str | None = None,
) -> dict[str, Any]:
    """Return eligibility and safe handoff links without external mutation."""

    domain = normalize_domain(item_url)
    reasons: list[str] = []
    if not domain:
        reasons.append("invalid-domain")
    elif _is_catalogued(domain, _catalog_domains(catalog_path)):
        reasons.append("already-in-catalog")
    if match_quality != "exact":
        reasons.append("not-exact")
    if confidence != "high":
        reasons.append("not-high-confidence")
    if source_health != "render_verified":
        reasons.append("not-live-render-verified")
    if support_kind not in {"code-backed", "runtime-backed"}:
        reasons.append("not-code-or-runtime-backed")
    if not concrete_item:
        reasons.append("not-concrete-item")
    if already_suggested:
        reasons.append("already-suggested-in-task")

    if reasons:
        return {
            "eligible": False,
            "reasons": reasons,
            "prompt": None,
            "submission": None,
        }

    field_value = _submission_value(site_name, domain)
    return {
        "eligible": True,
        "reasons": [],
        "prompt": PROMPT_TEMPLATE.format(domain=domain),
        "submission": {
            "fields": [{"label": FIELD_LABEL, "value": field_value}],
            "channels": {
                "github_issue_url": _github_issue_url(repository, field_value),
                "email_url": _email_url(email, field_value),
            },
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate a new motion-source candidate and prepare an opt-in suggestion."
    )
    parser.add_argument("--site-name", required=True)
    parser.add_argument("--item-url", required=True, help="Used locally for domain and quality checks; never submitted.")
    parser.add_argument("--match-quality", choices=("exact", "adjacent", "unresolved"), required=True)
    parser.add_argument("--confidence", choices=("high", "medium", "low"), required=True)
    parser.add_argument(
        "--source-health",
        choices=("render_verified", "capture_restricted", "shell_reachable", "broken"),
        required=True,
    )
    parser.add_argument(
        "--support-kind",
        choices=("code-backed", "runtime-backed", "video-only"),
        required=True,
    )
    parser.add_argument("--concrete-item", action="store_true")
    parser.add_argument("--already-suggested", action="store_true")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--email", help="Optional maintainer address for a mailto fallback.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = evaluate_source_suggestion(
        site_name=args.site_name,
        item_url=args.item_url,
        match_quality=args.match_quality,
        confidence=args.confidence,
        source_health=args.source_health,
        support_kind=args.support_kind,
        concrete_item=args.concrete_item,
        already_suggested=args.already_suggested,
        catalog_path=args.catalog,
        repository=args.repository,
        email=args.email,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
