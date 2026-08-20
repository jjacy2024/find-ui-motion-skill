from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO_ROOT / "skills" / "find-ui-motion"
SCRIPTS = SKILL_ROOT / "scripts"
MAINTAINER = REPO_ROOT / "maintainer"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(MAINTAINER))

from build_evidence_board import prepare_manifest  # noqa: E402
from build_visual_index import build_index_data  # noqa: E402
from catalog_overview import build_catalog_overview, render_markdown  # noqa: E402
from catalog_lib import _diversify_examples, load_examples, load_json, load_motions, load_query_expansions, search_catalog, validate_catalog_data  # noqa: E402
from check_catalog_update import check_update, validate_manifest  # noqa: E402
from analyze_motion_media import analyze, extract_dynamic_crops  # noqa: E402
from classify_source_health import classify_case, classify_manifest  # noqa: E402
from rank_visual_matches import rank_manifest  # noqa: E402
from retrieval_fusion import reciprocal_rank_fusion, selective_vlm_decision  # noqa: E402
from search_visual_index import search_index  # noqa: E402
from source_suggestion import FIELD_LABEL, PROMPT_TEMPLATE, evaluate_source_suggestion  # noqa: E402
from visual_index import late_interaction_scores, load_metadata, load_visual_index, write_metadata, write_visual_index  # noqa: E402
from curate_examples import curate  # noqa: E402
from expand_public_sitemaps import _normalize_url  # noqa: E402


class CatalogToolsTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_cache = os.environ.get("FIND_UI_MOTION_CACHE_DIR")
        os.environ["FIND_UI_MOTION_CACHE_DIR"] = self.temp_dir.name

    def tearDown(self):
        if self.previous_cache is None:
            os.environ.pop("FIND_UI_MOTION_CACHE_DIR", None)
        else:
            os.environ["FIND_UI_MOTION_CACHE_DIR"] = self.previous_cache
        self.temp_dir.cleanup()

    def test_bundled_catalog_and_motions_validate(self):
        catalog = load_json(SKILL_ROOT / "references" / "sites.json")
        errors, _ = validate_catalog_data(catalog)
        motions, motion_errors = load_motions()
        examples, example_errors = load_examples(
            SKILL_ROOT / "references" / "examples.jsonl",
            site_ids={site["id"] for site in catalog["sites"]},
            motion_ids={motion["id"] for motion in motions},
        )
        self.assertEqual(errors, [])
        self.assertEqual(motion_errors, [])
        self.assertEqual(example_errors, [])
        self.assertEqual(len(catalog["sites"]), 23)
        site_ids = {site["id"] for site in catalog["sites"]}
        self.assertTrue({"uiverse", "unicorn-studio", "lottielab", "design-spells", "transitions-dev", "originkit", "pixel-perfect"} <= site_ids)
        self.assertTrue({"aceternity-ui", "animate-ui", "21st-dev", "motion-primitives"} <= site_ids)
        self.assertTrue({"hover-css", "codepen", "lottiefiles"}.isdisjoint(site_ids))
        self.assertGreaterEqual(len(motions), 65)
        self.assertGreaterEqual(len(examples), 3000)
        self.assertGreaterEqual(len({example["site_id"] for example in examples}), 17)
        self.assertGreaterEqual(len({motion_id for example in examples for motion_id in example["motion_ids"]}), 60)
        self.assertEqual(len({example["id"] for example in examples}), len(examples))
        self.assertEqual(len({example["url"].rstrip("/") for example in examples}), len(examples))
        self.assertTrue(all(example["last_shallow_check"] for example in examples))
        self.assertTrue(
            all(
                example["last_verified"] is not None
                or (
                    example.get("link_scope") == "source-with-category-preview"
                    and example["last_verified"] is None
                )
                for example in examples
            )
        )
        self.assertTrue(all(example.get("verification", {}).get("verified_at") == example["last_verified"] for example in examples))

    def test_conservative_curation_keeps_only_current_dynamic_evidence(self):
        checked_at = "2026-08-19"

        def record(case_id, url, site_id="react-bits", evidence=None):
            value = {"id": case_id, "url": url, "site_id": site_id, "last_verified": None}
            if evidence is not None:
                value["source_evidence"] = evidence
            return value

        rive_evidence = {
            "kind": "public-list-api",
            "official_media_url": "https://public.rive.app/community/videos/1.mp4",
            "runtime_file_url": "https://public.rive.app/community/runtime-files/1.riv",
            "media_range_verified_at": checked_at,
            "runtime_range_verified_at": checked_at,
        }
        records = [
            record("rive-dynamic", "https://rive.app/marketplace/1/", "rive-community", rive_evidence),
            record("duplicate-url", "https://rive.app/marketplace/1", "rive-community", rive_evidence),
            record("page-dynamic", "https://reactbits.dev/animations/example"),
            record("static", "https://reactbits.dev/animations/static"),
            record("broken", "https://reactbits.dev/animations/broken"),
            record("unknown", "https://reactbits.dev/animations/unknown"),
        ]
        audits = {
            "rive-dynamic": [{
                "id": "rive-dynamic", "state": "dynamic", "evidence_kind": "official-media-frame-difference",
                "evidence": {"changed_pixel_ratio": 0.5, "mean_absolute_difference": 12.0},
            }],
            "page-dynamic": [{
                "id": "page-dynamic", "state": "dynamic", "evidence_kind": "browser-page-motion",
                "target": {"kind": "canvas", "confidence": "explicit"}, "unique_frame_hashes": 2,
                "running_animations": 0, "video_advanced": False,
            }],
            "static": [{"id": "static", "state": "static"}, {"id": "static", "state": "static"}],
            "broken": [{"id": "broken", "state": "broken"}, {"id": "broken", "state": "broken"}],
            "unknown": [{"id": "unknown", "state": "unverified"}],
        }
        kept, quarantine, report = curate(records, audits, checked_at)
        self.assertEqual({item["id"] for item in kept}, {"rive-dynamic", "page-dynamic"})
        self.assertTrue(all(item["last_verified"] == checked_at for item in kept))
        self.assertEqual(report["removed_exact_duplicates"], 1)
        reasons = {item["id"]: item["reason"] for item in quarantine}
        self.assertEqual(reasons["static"], "static-confirmed-twice")
        self.assertEqual(reasons["broken"], "broken-confirmed-twice")
        self.assertEqual(reasons["unknown"], "motion-unverified")

    def test_incremental_curation_preserves_prior_verified_cases(self):
        checked_at = "2026-08-19"
        existing = {
            "id": "existing-verified",
            "site_id": "react-bits",
            "url": "https://reactbits.dev/animations/existing",
            "last_verified": "2026-08-18",
            "verification": {"kind": "browser-page-motion", "verified_at": "2026-08-18"},
        }
        candidate = {
            "id": "new-dynamic",
            "site_id": "animate-ui",
            "url": "https://animate-ui.com/docs/components/buttons/ripple",
            "last_verified": None,
        }
        audits = {
            "new-dynamic": [{
                "id": "new-dynamic", "state": "dynamic", "evidence_kind": "browser-page-motion",
                "target": {"kind": "main", "confidence": "semantic"}, "unique_frame_hashes": 2,
                "running_animations": 1, "video_advanced": False,
            }],
        }
        kept, quarantine, _ = curate(
            [existing, candidate], audits, checked_at, preserve_current_verified=True
        )
        self.assertEqual({item["id"] for item in kept}, {"existing-verified", "new-dynamic"})
        self.assertEqual(next(item for item in kept if item["id"] == "existing-verified")["last_verified"], "2026-08-18")
        self.assertEqual(quarantine, [])

    def test_curated_catalog_covers_sources_evidence_and_motion_families(self):
        examples, errors = load_examples(SKILL_ROOT / "references" / "examples.jsonl")
        self.assertEqual(errors, [])
        example_sites = {example["site_id"] for example in examples}
        self.assertTrue({"animista", "lottielab", "rive-community", "unicorn-studio"} <= example_sites)
        rive_examples = [example for example in examples if example["site_id"] == "rive-community"]
        expanded_rive = [example for example in rive_examples if example["id"].startswith("rive-marketplace-")]
        self.assertGreaterEqual(len(rive_examples), 1950)
        self.assertGreaterEqual(len(expanded_rive), 1900)
        self.assertTrue(all(example.get("source_evidence", {}).get("kind") == "public-list-api" for example in expanded_rive))
        self.assertTrue(all(example["source_evidence"]["width"] > 0 for example in expanded_rive))
        self.assertTrue(all(example["source_evidence"]["height"] > 0 for example in expanded_rive))
        self.assertTrue(all(example["source_evidence"]["official_media_url"].endswith(".mp4") for example in expanded_rive))
        self.assertTrue(all(example["source_evidence"]["runtime_file_url"].endswith(".riv") for example in expanded_rive))
        self.assertTrue(all(example.get("preview_url") == example["source_evidence"]["official_media_url"] for example in expanded_rive))
        self.assertTrue(all(example["source_evidence"].get("media_range_verified_at") for example in expanded_rive))
        self.assertTrue(all(example["source_evidence"].get("runtime_range_verified_at") for example in expanded_rive))
        self.assertTrue(all(example["verification"]["kind"] == "official-media-frame-difference" for example in expanded_rive))
        self.assertTrue(all(
            example["verification"]["changed_pixel_ratio"] >= 0.001
            or example["verification"]["mean_absolute_difference"] >= 0.25
            for example in expanded_rive
        ))
        sites_by_motion: dict[str, set[str]] = {}
        for example in examples:
            for motion_id in example["motion_ids"]:
                sites_by_motion.setdefault(motion_id, set()).add(example["site_id"])
        expected = {
            "feedback-error-shake": "animista",
            "exit-scale-out": "animista",
            "loading-progress-morph": "lottielab",
            "loading-dots": "lottielab",
            "transition-shared-axis": "react-bits",
        }
        for motion_id, site_id in expected.items():
            self.assertIn(site_id, sites_by_motion[motion_id])

        pixel_examples = [example for example in examples if example["site_id"] == "pixel-perfect"]
        self.assertGreaterEqual(len(pixel_examples), 8)
        self.assertTrue(all(example["link_scope"] == "source-with-category-preview" for example in pixel_examples))
        self.assertTrue(all(example["preview_strategy"] == "open-source-only" for example in pixel_examples))
        self.assertTrue(all(example["preview_url"].startswith("https://www.pixel-perfect.space/") for example in pixel_examples))

    def test_public_sitemap_expansion_survives_current_dynamic_audit(self):
        examples, errors = load_examples(SKILL_ROOT / "references" / "examples.jsonl")
        self.assertEqual(errors, [])
        sitemap_examples = [
            example
            for example in examples
            if example.get("source_evidence", {}).get("kind") == "public-sitemap"
        ]
        self.assertGreaterEqual(len(sitemap_examples), 590)
        source_counts = {
            site_id: sum(example["site_id"] == site_id for example in examples)
            for site_id in {example["site_id"] for example in examples}
        }
        self.assertGreaterEqual(source_counts["react-bits"], 160)
        self.assertGreaterEqual(source_counts["magic-ui"], 60)
        self.assertGreaterEqual(source_counts["originkit"], 160)
        self.assertGreaterEqual(source_counts["design-spells"], 300)
        self.assertLessEqual(max(source_counts.values()) / len(examples), 0.80)
        self.assertTrue(all(example["last_verified"] is not None for example in sitemap_examples))
        self.assertTrue(all(example["verification"]["kind"] == "browser-page-motion" for example in sitemap_examples))
        self.assertTrue(all(example["source_evidence"]["sitemap_url"].startswith("https://") for example in sitemap_examples))
        self.assertTrue(all(example["source_evidence"]["discovered_at"] <= example["last_shallow_check"] for example in sitemap_examples))
        self.assertIn("interactive-component-motion", {motion for example in sitemap_examples for motion in example["motion_ids"]})
        self.assertIn("product-microinteraction", {motion for example in sitemap_examples for motion in example["motion_ids"]})
        self.assertNotIn("https://magicui.design/docs/components/android", {example["url"] for example in examples})
        self.assertTrue(any("%27" in example["url"] for example in sitemap_examples if example["site_id"] == "design-spells"))

    def test_public_index_expansion_survives_current_dynamic_audit(self):
        examples, errors = load_examples(SKILL_ROOT / "references" / "examples.jsonl")
        self.assertEqual(errors, [])
        index_examples = [
            example for example in examples
            if example.get("source_evidence", {}).get("kind") == "public-index-page"
            and example.get("link_scope", "item") == "item"
        ]
        self.assertGreaterEqual(len(index_examples), 217)
        source_counts = {
            site_id: sum(example["site_id"] == site_id for example in index_examples)
            for site_id in {example["site_id"] for example in index_examples}
        }
        self.assertGreaterEqual(source_counts["aceternity-ui"], 110)
        self.assertGreaterEqual(source_counts["animate-ui"], 75)
        self.assertGreaterEqual(source_counts["21st-dev"], 20)
        self.assertGreaterEqual(source_counts["motion-primitives"], 10)
        self.assertNotIn("fancy-components", source_counts)
        self.assertTrue(all(example["last_verified"] is not None for example in index_examples))
        self.assertTrue(all(example["verification"]["kind"] == "browser-page-motion" for example in index_examples))
        self.assertTrue(all(example["source_evidence"]["index_url"].startswith("https://") for example in index_examples))
        self.assertTrue(all(example["source_evidence"]["discovered_at"] <= example["last_shallow_check"] for example in index_examples))
        self.assertTrue(all("/@" in example["url"] and "%40" not in example["url"] for example in index_examples if example["site_id"] == "21st-dev"))

    def test_public_item_url_normalization_preserves_at_sign(self):
        self.assertEqual(
            _normalize_url("https://21st.dev/@author/components/animated-hero/"),
            "https://21st.dev/@author/components/animated-hero",
        )

    def test_trigger_metadata(self):
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = skill_text.split("---", 2)[1]
        for phrase in (
            "UI motion",
            "Web and mobile",
            "网页动效",
            "App 动效",
            "交互动效",
            "微动效",
            "动画灵感",
            "hover",
            "transition",
            "Lottie",
            "Rive",
            "SwiftUI",
            "Jetpack Compose",
            "Flutter",
            "React Native",
            "动效网站",
            "static UI design",
            "video editing",
            "real source examples",
        ):
            self.assertIn(phrase, frontmatter)

        agent_config = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("allow_implicit_invocation: true", agent_config)
        self.assertIn("$find-ui-motion", agent_config)

    def test_mobile_targets_use_platform_compatibility_gates(self):
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        rebuild_rules = (SKILL_ROOT / "references" / "reference-rebuild.md").read_text(encoding="utf-8")

        for rule in (
            "source environment and target platform",
            "Do not deliver Web code as a mobile implementation",
            "web | ios | android | cross-platform | unspecified",
        ):
            self.assertIn(rule, skill_text)
        for rule in (
            "A React package is not a React Native package",
            "platform-native primitives",
            "target_platform: web | ios | android | cross-platform",
        ):
            self.assertIn(rule, rebuild_rules)

    def test_code_first_discovery_requires_explicit_video_case_authorization(self):
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        exact_rules = (SKILL_ROOT / "references" / "exact-search.md").read_text(encoding="utf-8")
        ladder_rules = (SKILL_ROOT / "references" / "retrieval-ladder.md").read_text(encoding="utf-8")
        inspiration_rules = (SKILL_ROOT / "references" / "inspiration-exploration.md").read_text(encoding="utf-8")
        preview_rules = (SKILL_ROOT / "references" / "source-preview.md").read_text(encoding="utf-8")

        for rule in (
            "video_case_search_authorized=false",
            "explicitly asks for video cases",
            "Exclude video-only sources",
            "code-backed | runtime-backed | video-only",
            "视频补充（已授权）",
            "transient clip recorded from a code-backed interactive demo",
        ):
            self.assertIn(rule, skill_text)
        self.assertIn("prioritize cases with an attached public snippet", exact_rules)
        self.assertIn("Exclude video-only cases from retrieval", exact_rules)
        self.assertIn("Rank `code-backed` and `runtime-backed` cases first", ladder_rules)
        self.assertIn("A generic request to see examples does not authorize video-case search", inspiration_rules)
        self.assertIn("A video preview is allowed without video-search authorization only when it previews the same code-backed", preview_rules)

    def test_catalog_overview_reports_current_bundled_counts(self):
        overview = build_catalog_overview()

        self.assertEqual(overview["catalog_version"], "2026.08.9")
        self.assertEqual(overview["source_count"], 23)
        self.assertEqual(overview["case_count"], 3656)
        self.assertNotIn("sites", overview)
        self.assertEqual(
            overview["announcement"],
            "当前版本 2026.08.9 的内置清单共收录 23 个来源网站，"
            "案例库中共有 3656 个案例。"
            "如果你有兴趣，可以查看网站清单，并手动点击链接访问任意来源网站。",
        )

    def test_catalog_overview_lists_every_public_source_as_a_clickable_link(self):
        overview = build_catalog_overview(include_sites=True)
        sites = overview["sites"]

        self.assertEqual(len(sites), overview["source_count"])
        self.assertEqual(len({site["name"] for site in sites}), overview["source_count"])
        self.assertTrue(all(site["homepage"].startswith("https://") for site in sites))
        markdown = render_markdown(overview)
        self.assertIn("### 网站清单", markdown)
        for site in sites:
            self.assertIn(f"]({site['homepage']})", markdown)

        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "catalog_overview.py"),
                "--list-sites",
                "--format",
                "markdown",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(completed.stdout.count("\n- ["), overview["source_count"])

    def test_catalog_overview_is_once_per_task_and_never_auto_opens_sites(self):
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        rules = (SKILL_ROOT / "references" / "catalog-overview.md").read_text(encoding="utf-8")

        for rule in (
            "first Skill use in each task",
            "source-site and case counts once",
            "Do not open any source automatically",
        ):
            self.assertIn(rule, skill_text)
        for rule in (
            "never hardcode or estimate",
            "Do not repeat the announcement later in the same task",
            "Return every listed website as a clickable Markdown link",
            "does not count toward the default eight concrete-case links",
            "Let the user manually click a link",
        ):
            self.assertIn(rule, rules)

    def test_new_external_source_suggestion_uses_approved_copy_and_one_field(self):
        result = evaluate_source_suggestion(
            site_name="Particle Lab",
            item_url="https://particles.example.com/demos/app-launch",
            match_quality="exact",
            confidence="high",
            source_health="render_verified",
            support_kind="code-backed",
            concrete_item=True,
        )

        self.assertTrue(result["eligible"])
        self.assertEqual(
            result["prompt"],
            "发现一个尚未收录的高质量动效来源 particles.example.com。"
            "是否生成来源推荐，交给 find-ui-motion Catalog 维护者审核？"
            "审核通过后会加入下一个版本的内置清单中",
        )
        self.assertEqual(PROMPT_TEMPLATE.count("{domain}"), 1)
        self.assertEqual(
            result["submission"]["fields"],
            [{"label": FIELD_LABEL, "value": "Particle Lab — particles.example.com"}],
        )
        channels = result["submission"]["channels"]
        self.assertIn("github.com/jjacy2024/find-ui-motion-catalog/issues/new", channels["github_issue_url"])
        self.assertIn("source-suggestion.md", channels["github_issue_url"])
        self.assertNotIn("app-launch", channels["github_issue_url"])
        self.assertIsNone(channels["email_url"])

        with_email = evaluate_source_suggestion(
            site_name="Particle Lab",
            item_url="https://particles.example.com/demos/app-launch",
            match_quality="exact",
            confidence="high",
            source_health="render_verified",
            support_kind="runtime-backed",
            concrete_item=True,
            email="maintainer@example.com",
        )
        email_url = with_email["submission"]["channels"]["email_url"]
        self.assertTrue(email_url.startswith("mailto:maintainer@example.com?"))
        self.assertNotIn("app-launch", email_url)

    def test_source_suggestion_rejects_catalogued_or_weak_candidates(self):
        base = {
            "site_name": "Motion",
            "item_url": "https://motion.dev/examples/react-particle-launch",
            "match_quality": "exact",
            "confidence": "high",
            "source_health": "render_verified",
            "support_kind": "code-backed",
            "concrete_item": True,
        }
        catalogued = evaluate_source_suggestion(**base)
        self.assertFalse(catalogued["eligible"])
        self.assertIn("already-in-catalog", catalogued["reasons"])
        self.assertIsNone(catalogued["submission"])

        weak = evaluate_source_suggestion(
            **{
                **base,
                "site_name": "Particle Lab",
                "item_url": "https://particles.example.com/demos/app-launch",
                "match_quality": "adjacent",
                "confidence": "medium",
                "source_health": "capture_restricted",
                "support_kind": "video-only",
                "concrete_item": False,
                "already_suggested": True,
            }
        )
        self.assertFalse(weak["eligible"])
        self.assertEqual(
            set(weak["reasons"]),
            {
                "not-exact",
                "not-high-confidence",
                "not-live-render-verified",
                "not-code-or-runtime-backed",
                "not-concrete-item",
                "already-suggested-in-task",
            },
        )

    def test_source_suggestion_reference_forbids_extra_or_automatic_submission(self):
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        rules = (SKILL_ROOT / "references" / "source-suggestion.md").read_text(encoding="utf-8")

        self.assertIn("网站名称与域名", skill_text)
        self.assertIn("审核通过后会加入下一个版本的内置清单中", rules)
        self.assertIn("contains exactly one field", rules)
        self.assertIn("Never create an Issue, send email", rules)
        self.assertIn("The item URL is local evaluation input only", rules)

    def test_exact_example_is_attached_to_matching_motion(self):
        result = search_catalog("SaaS 首页首屏高级安静的进入动效", stack="react", limit=4)
        blur = next(match for match in result["matches"] if match["motion"]["id"] == "entrance-blur-reveal")
        magic_blur = next(example for example in blur["examples"] if example["id"] == "magic-ui-blur-fade")
        self.assertEqual(magic_blur["url"], "https://magicui.design/docs/components/blur-fade")

    def test_expanded_examples_are_retrievable_beyond_top_three_sites(self):
        checks = {
            "滚动文字逐字揭示": ("scroll-text-scrub", "originkit"),
            "左右横向画廊": ("scroll-horizontal", "aceternity-ui"),
            "按钮跟随鼠标": ("hover-magnetic", "motion"),
            "卡片展开成详情": ("transition-container-transform", "motion"),
        }
        for query, (motion_id, expected_site) in checks.items():
            result = search_catalog(query, limit=4, examples_per_motion=10)
            match = next(item for item in result["matches"] if item["motion"]["id"] == motion_id)
            self.assertIn(expected_site, {example["site_id"] for example in match["examples"]})
            self.assertTrue(all(example["last_shallow_check"] for example in match["examples"]))

    def test_large_source_is_diversified_before_overflow_fill(self):
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Never infer quality from source volume", skill_text)
        candidates = [
            {"id": f"rive-{index}", "site_id": "rive-community"}
            for index in range(10)
        ] + [
            {"id": "magic-1", "site_id": "magic-ui"},
            {"id": "react-1", "site_id": "react-bits"},
        ]
        selected = _diversify_examples(candidates, 6)
        self.assertEqual(len(selected), 6)
        self.assertIn("magic-ui", {item["site_id"] for item in selected[:4]})
        self.assertIn("react-bits", {item["site_id"] for item in selected[:4]})

    def test_large_catalog_returns_bounded_deduplicated_candidate_pool(self):
        result = search_catalog(
            "交互状态机 按钮 页面转场 加载动效",
            limit=10,
            examples_per_motion=20,
            candidate_limit=64,
        )
        candidates = result["candidate_pool"]
        self.assertGreaterEqual(len(candidates), 48)
        self.assertLessEqual(len(candidates), 64)
        self.assertEqual(len({item["id"] for item in candidates}), len(candidates))
        self.assertEqual(len({item["url"].rstrip("/") for item in candidates}), len(candidates))
        self.assertTrue(all(item["matched_motion_ids"] for item in candidates))
        self.assertTrue(all(isinstance(item["recall_score"], float) for item in candidates))

        default_result = search_catalog("interactions loading transition", limit=10, examples_per_motion=20)
        self.assertLessEqual(len(default_result["candidate_pool"]), 48)

    def test_auto_retrieval_keeps_style_gap_optional_after_local_quick_results(self):
        groups = load_query_expansions()
        group_ids = {group["id"] for group in groups}
        self.assertTrue(
            {"mechanism-pixel", "style-cyberpunk", "mechanism-crt", "mechanism-scanline"} <= group_ids
        )

        result = search_catalog(
            "web端，像素风格动效，赛博朋克感，页面转场",
            strategy="auto",
            candidate_limit=64,
        )
        completed = {item["stage"]: item for item in result["retrieval_trace"] if item["status"] == "completed"}
        self.assertEqual(result["examples_total"], 3656)
        self.assertEqual(completed["global"]["examples_scanned"], result["examples_total"])
        self.assertEqual(completed["global-expanded"]["examples_scanned"], result["examples_total"])
        self.assertEqual(result["retrieval_level"], "global-expanded")
        self.assertEqual(result["candidate_pool"][0]["id"], "react-bits-pixel-transition")
        self.assertEqual(result["candidate_pool"][0]["coverage"], "adjacent")
        self.assertEqual(result["candidate_pool"][0]["quick_fit"], "strong")
        self.assertIn("style-cyberpunk", result["candidate_pool"][0]["missing_query_groups"])
        self.assertTrue(result["quick_coverage"]["complete"])
        self.assertEqual(result["external_search"]["decision"], "offer")
        self.assertFalse(result["external_search"]["recommended"])
        self.assertEqual(result["external_search"]["max_initial_queries"], 1)
        self.assertEqual(result["external_search"]["provenance_label"], "外网补充")

    def test_quick_gradient_background_pool_does_not_require_all_style_keywords(self):
        result = search_catalog(
            "web 动态渐变流光背景 绚丽有机 多色液态融合",
            strategy="auto",
            candidate_limit=48,
        )
        self.assertEqual(result["coverage"]["exact_count"], 0)
        self.assertTrue(result["quick_coverage"]["complete"])
        self.assertGreaterEqual(result["quick_coverage"]["strong_count"], 3)
        self.assertGreaterEqual(result["quick_coverage"]["source_count"], 3)
        self.assertEqual(result["external_search"]["decision"], "skip")
        self.assertFalse(result["external_search"]["recommended"])
        self.assertIn("react-bits-liquid-chrome", {item["id"] for item in result["candidate_pool"][:8]})
        self.assertTrue(
            all("scene-background" in item["quick_core_matches"] for item in result["candidate_pool"][:8])
        )

    def test_crt_gap_emits_focused_external_query_only_after_local_ladder(self):
        result = search_catalog("CRT 电视关机扫描线页面转场", strategy="auto", candidate_limit=64)
        self.assertFalse(result["coverage"]["complete"])
        self.assertEqual(result["quick_coverage"]["eligible_count"], 0)
        self.assertEqual(result["external_search"]["decision"], "required")
        self.assertTrue(result["external_search"]["recommended"])
        self.assertIn("crt", result["external_search"]["query"].lower())
        self.assertIn("scanline", result["external_search"]["query"].lower())
        self.assertIn("shutdown", result["external_search"]["query"].lower())
        self.assertEqual(
            [item["stage"] for item in result["retrieval_trace"] if item["status"] == "completed"],
            ["taxonomy", "global", "global-expanded"],
        )

    def test_candidate_pool_only_cli_avoids_duplicate_match_payload(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "search_catalog.py"),
                "gradient glow background motion",
                "--limit",
                "10",
                "--examples-per-motion",
                "20",
                "--candidate-limit",
                "64",
                "--candidate-pool-only",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(completed.stdout)
        self.assertNotIn("matches", payload)
        self.assertEqual(payload["strategy"], "auto")
        self.assertIn("retrieval_trace", payload)
        self.assertIn("quick_coverage", payload)
        self.assertIn("external_search", payload)
        self.assertGreaterEqual(len(payload["candidate_pool"]), 48)
        self.assertLessEqual(len(payload["candidate_pool"]), 64)

    def test_real_example_followups_require_pagination_and_deduplication(self):
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        preview_rules = (SKILL_ROOT / "references" / "source-preview.md").read_text(encoding="utf-8")

        self.assertIn("next page of three by default", skill_text)
        for rule in (
            "next page of exactly three examples",
            "shown example IDs",
            "shown canonical item URLs",
            "Never refill a short page with a duplicate",
            "Preserve query parameters that identify the example or state",
            "cumulative unique count",
        ):
            self.assertIn(rule, preview_rules)

    def test_quick_links_and_visual_deep_match_contract(self):
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        deep_rules = (SKILL_ROOT / "references" / "visual-deep-match.md").read_text(encoding="utf-8")
        preview_rules = (SKILL_ROOT / "references" / "source-preview.md").read_text(encoding="utf-8")
        health_rules = (SKILL_ROOT / "references" / "source-health.md").read_text(encoding="utf-8")
        ladder_rules = (SKILL_ROOT / "references" / "retrieval-ladder.md").read_text(encoding="utf-8")

        for rule in (
            "exactly eight eligible concrete case links by default",
            "Reduce the count below eight only when fewer than eight",
            "快速初筛，尚未完成视觉复核",
            "继续探索入口",
            "Do not create an aggregation page",
            "Formal results must be `exact` and `高` or `中`",
            "continue checking later candidates within the existing 24 live-check and 16 capture budgets",
        ):
            self.assertIn(rule, skill_text)
        for rule in (
            "停止深度匹配",
            "Build and fix the cross-source catalog pool before opening any candidate page",
            "Do not start from one site's category page",
            "Recall 48 unique concrete item URLs by default and use at most 64",
            "Use `--candidate-limit 48` normally",
            "24 candidates have received current browser health checks",
            "16 healthy candidates have been captured and analyzed",
            "three consecutive candidates",
            "OpenCLIP full-frame similarity",
            "Reciprocal Rank Fusion",
            "vlm_review.required=true",
            "eight `exact` matches with `高` or `中` evidence confidence",
            "Do not stop merely because the first eight captured candidates have been ranked",
            "match_quality: exact | adjacent | unresolved",
            "strong at a ratio of at least `0.85`",
            "supporting at a ratio of at least `0.65`",
            "status=needs-more-review",
            "status=confidence-shortfall",
            "low_confidence_alternates",
            "Do not show fake precision",
            "召回 48/64",
            "实时检查 12/24",
            "捕获 8/16",
        ):
            self.assertIn(rule, deep_rules)
        self.assertIn("Build a board only when the user explicitly requests", preview_rules)
        for rule in (
            "outer-page request proves only",
            "shell_reachable",
            "render_verified",
            "capture_restricted",
            "broken",
            "Never infer health from HTTP 200",
            "Never use `open-source-only` to rescue a `broken` item",
        ):
            self.assertIn(rule, health_rules)
        for rule in (
            "taxonomy",
            "global",
            "global-expanded",
            "external_search.decision",
            "external_search.recommended=true",
            "one focused initial query",
            "外网补充",
            "本地相邻参考",
            "Do not add newly discovered external items",
        ):
            self.assertIn(rule, ladder_rules)

        retrieval_rules = (SKILL_ROOT / "references" / "visual-retrieval.md").read_text(encoding="utf-8")
        for rule in (
            "open_clip_torch",
            "dynamic-region",
            "Farneback fallback",
            "RRF",
            "vlm_review",
            "status=degraded",
            "retrieval/fusion evidence, not a presentable final result",
            "within the fixed 24/16 budgets",
        ):
            self.assertIn(rule, retrieval_rules)

    def test_source_health_rejects_wrapper_200_with_missing_project_data(self):
        result = classify_case(
            {
                "id": "missing-project",
                "outer_status": 200,
                "settled": True,
                "expects_render_target": True,
                "critical_responses": [{"label": "project-data", "status": 404}],
                "console_errors": ["Error fetching data for project id 'missing-project'"],
                "render_targets": [],
                "capture_attempted": True,
                "capture_succeeded": False,
                "analysis_depth": "metadata-only",
            }
        )
        self.assertEqual(result["state"], "broken")
        self.assertFalse(result["quick_eligible"])
        self.assertFalse(result["deep_eligible"])
        self.assertIn("critical-status-404", result["reasons"])
        self.assertIn("missing-render-target-after-settle", result["reasons"])

    def test_source_health_distinguishes_render_capture_and_shell_states(self):
        manifest = {
            "cases": [
                {
                    "id": "working-canvas",
                    "outer_status": 200,
                    "settled": True,
                    "expects_render_target": True,
                    "critical_responses": [{"label": "project-data", "status": 200}],
                    "render_targets": [{"kind": "canvas", "visible": True, "width": 1280, "height": 720}],
                    "capture_attempted": True,
                    "capture_succeeded": True,
                    "analysis_depth": "keyframes",
                },
                {
                    "id": "capture-blocked",
                    "outer_status": 200,
                    "settled": True,
                    "visually_observed": True,
                    "capture_attempted": True,
                    "capture_succeeded": False,
                },
                {
                    "id": "wrapper-only",
                    "outer_status": 200,
                    "settled": False,
                },
            ]
        }
        result = classify_manifest(manifest)
        by_id = {item["id"]: item for item in result["results"]}
        self.assertEqual(by_id["working-canvas"]["state"], "render_verified")
        self.assertTrue(by_id["working-canvas"]["quick_eligible"])
        self.assertTrue(by_id["working-canvas"]["deep_eligible"])
        self.assertEqual(by_id["capture-blocked"]["state"], "capture_restricted")
        self.assertTrue(by_id["capture-blocked"]["quick_eligible"])
        self.assertFalse(by_id["capture-blocked"]["deep_eligible"])
        self.assertEqual(by_id["wrapper-only"]["state"], "shell_reachable")
        self.assertFalse(by_id["wrapper-only"]["quick_eligible"])
        self.assertEqual(result["quick_eligible_count"], 2)

    def test_source_health_requires_consistent_capture_signals(self):
        with self.assertRaisesRegex(ValueError, "capture_succeeded requires"):
            classify_case(
                {
                    "id": "invalid-capture",
                    "outer_status": 200,
                    "capture_attempted": False,
                    "capture_succeeded": True,
                }
            )

    def test_source_health_cli_regression_fixture(self):
        fixture = REPO_ROOT / "tests" / "fixtures" / "source-health-wrapper-200-inner-404.json"
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "classify_source_health.py"), str(fixture)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        result = json.loads(completed.stdout)
        by_id = {item["id"]: item for item in result["results"]}
        self.assertEqual(by_id["unicorn-studio-fluted-gradient"]["state"], "render_verified")
        self.assertTrue(by_id["unicorn-studio-fluted-gradient"]["quick_eligible"])
        self.assertEqual(by_id["unicorn-studio-blue-noise"]["state"], "broken")
        self.assertFalse(by_id["unicorn-studio-blue-noise"]["quick_eligible"])

    def test_visual_ranking_is_bounded_sorted_and_excludes_metadata_only(self):
        candidates = [
            {
                "id": "medium",
                "title": "Medium",
                "url": "https://example.com/medium?utm_source=test",
                "analysis_depth": "keyframes",
                "match_quality": "exact",
                "scores": {
                    "text_fit": 0.7,
                    "visual_semantic_fit": 0.7,
                    "motion_trajectory_fit": 0.6,
                    "delivery_quality": 0.7,
                },
            },
            {
                "id": "best",
                "title": "Best",
                "url": "https://example.com/best#demo",
                "analysis_depth": "video-trajectory",
                "match_quality": "exact",
                "scores": {
                    "text_fit": 0.95,
                    "visual_semantic_fit": 0.9,
                    "motion_trajectory_fit": 0.85,
                    "delivery_quality": 0.8,
                },
            },
            {
                "id": "metadata",
                "title": "Metadata only",
                "url": "https://example.com/metadata",
                "analysis_depth": "metadata-only",
                "match_quality": "exact",
                "scores": {
                    "text_fit": 1.0,
                    "visual_semantic_fit": 1.0,
                    "motion_trajectory_fit": 1.0,
                    "delivery_quality": 1.0,
                },
            },
            {
                "id": "medium-duplicate",
                "title": "Duplicate",
                "url": "https://example.com/medium",
                "analysis_depth": "keyframes",
                "match_quality": "exact",
                "scores": {
                    "text_fit": 0.8,
                    "visual_semantic_fit": 0.8,
                    "motion_trajectory_fit": 0.8,
                    "delivery_quality": 0.8,
                },
            },
        ]
        result = rank_manifest({"query": "test", "candidates": candidates}, limit=10)
        self.assertEqual([item["id"] for item in result["results"]], ["best", "medium"])
        self.assertEqual(result["results"][0]["rank"], 1)
        self.assertEqual(result["eligible_count"], 2)
        self.assertEqual(len(result["excluded"]), 2)
        self.assertEqual(result["target_result_count"], 10)
        self.assertEqual(result["returned_result_count"], 2)
        self.assertEqual(result["status"], "needs-more-review")
        self.assertTrue(result["replacement_search"]["required"])
        self.assertEqual(result["replacement_search"]["review_progress"]["remaining_live_checks"], 24)
        self.assertEqual(result["replacement_search"]["review_progress"]["remaining_captures"], 16)
        self.assertIsNotNone(result["continuation_reason"])
        self.assertIsNone(result["shortfall_reason"])
        self.assertIn("not probabilities", result["score_note"])
        default_result = rank_manifest({"query": "test", "candidates": candidates})
        self.assertEqual(default_result["target_result_count"], 8)
        with self.assertRaisesRegex(ValueError, "between 1 and 10"):
            rank_manifest({"candidates": []}, limit=11)

    def test_visual_ranking_separates_semantic_fit_and_confidence(self):
        def candidate(case_id, scores, *, match_quality="exact", vlm_verdict="not-reviewed"):
            return {
                "id": case_id,
                "title": case_id,
                "url": f"https://example.com/{case_id}",
                "analysis_depth": "keyframes",
                "match_quality": match_quality,
                "vlm_verdict": vlm_verdict,
                "scores": dict(zip(("text_fit", "visual_semantic_fit", "motion_trajectory_fit", "delivery_quality"), scores)),
            }

        result = rank_manifest(
            {
                "query": "exact motion",
                "candidates": [
                    candidate("exact-high", (1.0, 1.0, 1.0, 1.0)),
                    candidate("exact-medium", (0.9, 0.9, 0.5, 0.5)),
                    candidate("exact-low", (0.8, 0.4, 0.4, 0.4)),
                    candidate("adjacent-high", (0.95, 0.95, 0.95, 0.95), match_quality="adjacent"),
                    candidate("unresolved", (1.0, 1.0, 1.0, 1.0), match_quality="unresolved"),
                    candidate("contradicted", (1.0, 1.0, 1.0, 1.0), vlm_verdict="contradicted"),
                ],
            },
            limit=4,
        )
        self.assertEqual({item["id"] for item in result["results"]}, {"exact-high", "exact-medium"})
        self.assertTrue(all(item["match_quality"] == "exact" for item in result["results"]))
        self.assertTrue(all(item["confidence"] in {"高", "中"} for item in result["results"]))
        self.assertEqual([item["id"] for item in result["adjacent_references"]], ["adjacent-high"])
        self.assertEqual([item["id"] for item in result["low_confidence_alternates"]], ["exact-low"])
        excluded = {item["id"]: item["reason"] for item in result["excluded"]}
        self.assertIn("unresolved", excluded)
        self.assertIn("contradicted", excluded)

    def test_relative_channel_confidence_can_qualify_eight_supported_cases(self):
        candidates = []
        for index in range(8):
            score = 1.0 - index * 0.015
            candidates.append(
                {
                    "id": f"case-{index}",
                    "title": f"Case {index}",
                    "url": f"https://example.com/case-{index}",
                    "analysis_depth": "video-trajectory",
                    "match_quality": "exact",
                    "scores": {
                        "text_fit": score,
                        "visual_semantic_fit": score,
                        "motion_trajectory_fit": score,
                        "delivery_quality": score,
                    },
                }
            )
        result = rank_manifest({"query": "supported set", "candidates": candidates})
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["returned_result_count"], 8)
        self.assertTrue(all(item["confidence"] == "高" for item in result["results"]))
        self.assertFalse(result["replacement_search"]["required"])

    def test_visual_ranking_reports_terminal_confidence_shortfall_without_padding(self):
        candidates = [
            {
                "id": "strong",
                "title": "Strong",
                "url": "https://example.com/strong",
                "analysis_depth": "keyframes",
                "match_quality": "exact",
                "scores": {"text_fit": 1.0, "visual_semantic_fit": 1.0, "motion_trajectory_fit": 1.0, "delivery_quality": 1.0},
            },
            {
                "id": "weak",
                "title": "Weak",
                "url": "https://example.com/weak",
                "analysis_depth": "keyframes",
                "match_quality": "exact",
                "scores": {"text_fit": 0.8, "visual_semantic_fit": 0.3, "motion_trajectory_fit": 0.3, "delivery_quality": 0.3},
            },
        ]
        result = rank_manifest(
            {"query": "budget exhausted", "candidates": candidates, "review_progress": {"live_checked": 24, "captured": 10}},
        )
        self.assertEqual(result["status"], "confidence-shortfall")
        self.assertEqual([item["id"] for item in result["results"]], ["strong"])
        self.assertEqual([item["id"] for item in result["low_confidence_alternates"]], ["weak"])
        self.assertFalse(result["replacement_search"]["required"])
        self.assertEqual(result["replacement_search"]["action"], "report-confidence-shortfall")
        self.assertEqual(result["replacement_search"]["review_progress"]["effective_stop_reason"], "live-check-budget-exhausted")
        self.assertIn("live-check-budget-exhausted", result["shortfall_reason"])

    def test_vlm_confirmation_promotes_once_and_contradiction_excludes(self):
        candidates = [
            {
                "id": "best",
                "title": "Best",
                "url": "https://example.com/best",
                "analysis_depth": "keyframes",
                "match_quality": "exact",
                "scores": {"text_fit": 1.0, "visual_semantic_fit": 1.0, "motion_trajectory_fit": 1.0, "delivery_quality": 1.0},
            },
            {
                "id": "vlm-confirmed",
                "title": "VLM Confirmed",
                "url": "https://example.com/vlm-confirmed",
                "analysis_depth": "keyframes",
                "match_quality": "exact",
                "vlm_verdict": "confirmed",
                "scores": {"text_fit": 0.75, "visual_semantic_fit": 0.5, "motion_trajectory_fit": 0.5, "delivery_quality": 0.5},
            },
            {
                "id": "vlm-contradicted",
                "title": "VLM Contradicted",
                "url": "https://example.com/vlm-contradicted",
                "analysis_depth": "keyframes",
                "match_quality": "exact",
                "vlm_verdict": "contradicted",
                "scores": {"text_fit": 1.0, "visual_semantic_fit": 1.0, "motion_trajectory_fit": 1.0, "delivery_quality": 1.0},
            },
        ]
        result = rank_manifest({"query": "vlm", "candidates": candidates}, limit=3)
        promoted = next(item for item in result["results"] if item["id"] == "vlm-confirmed")
        self.assertEqual(promoted["confidence"], "中")
        self.assertEqual(promoted["confidence_basis"], "vlm-confirmed-promotion")
        self.assertIn("vlm-contradicted", {item["id"] for item in result["excluded"]})

    def test_missing_match_quality_is_unresolved_and_excluded(self):
        result = rank_manifest(
            {
                "candidates": [
                    {
                        "id": "missing-quality",
                        "title": "Missing Quality",
                        "url": "https://example.com/missing-quality",
                        "analysis_depth": "keyframes",
                        "scores": {"text_fit": 1.0, "visual_semantic_fit": 1.0, "motion_trajectory_fit": 1.0, "delivery_quality": 1.0},
                    }
                ]
            }
        )
        self.assertEqual(result["results"], [])
        self.assertIn("unresolved semantic match quality", result["excluded"][0]["reason"])

    def test_motion_media_analyzer_extracts_real_frame_change(self):
        try:
            import cv2
            import numpy as np
        except ImportError:
            self.skipTest("OpenCV and NumPy are optional")

        frame_paths = []
        for index, x in enumerate((4, 20, 36)):
            frame = np.zeros((64, 64, 3), dtype=np.uint8)
            frame[22:38, x : x + 14] = 255
            path = Path(self.temp_dir.name) / f"frame-{index}.png"
            cv2.imwrite(str(path), frame)
            frame_paths.append(path)
        output = Path(self.temp_dir.name) / "motion-signature.json"
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "analyze_motion_media.py"),
                *[str(path) for path in frame_paths],
                "--output",
                str(output),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["analysis_depth"], "keyframes")
        self.assertEqual(result["sampled_frame_count"], 3)
        self.assertGreater(result["motion_signature"]["changed_area_peak"], 0)
        self.assertGreaterEqual(len(result["motion_signature"]["keyframes"]), 2)

    def test_motion_media_analyzer_extracts_dynamic_region_and_flow_backend(self):
        try:
            import cv2
            import numpy as np
        except ImportError:
            self.skipTest("OpenCV and NumPy are optional")

        paths = []
        for index, x in enumerate((5, 13, 22, 32)):
            frame = np.zeros((80, 100, 3), dtype=np.uint8)
            frame[30:46, x : x + 18] = (20, 180, 255)
            path = Path(self.temp_dir.name) / f"motion-{index}.png"
            cv2.imwrite(str(path), frame)
            paths.append(path)
        result, keyframes = analyze(paths, flow_backend="auto")
        signature = result["motion_signature"]
        self.assertIn(signature["optical_flow_backend"], {"dis", "farneback"})
        self.assertTrue(signature["dynamic_bbox"]["changed"])
        self.assertLess(signature["dynamic_bbox"]["height"], 1.0)
        self.assertAlmostEqual(sum(signature["direction_histogram"].values()), 1.0, places=3)
        bbox, crops = extract_dynamic_crops(keyframes)
        self.assertTrue(bbox["changed"])
        self.assertEqual(len(crops), len(keyframes))

    def test_rrf_fusion_and_selective_vlm_routing(self):
        agreed = {
            "text": ["a", "b", "c", "d"],
            "visual": ["a", "c", "b", "d"],
            "motion": ["a", "b", "d", "c"],
        }
        fused = reciprocal_rank_fusion(agreed)
        self.assertEqual(fused[0]["id"], "a")
        self.assertEqual(fused[0]["channel_count"], 3)
        decision = selective_vlm_decision(fused, agreed)
        self.assertFalse(decision["required"])
        self.assertEqual(decision["status"], "early-stop")

        disagreed = {
            "text": ["a", "b", "c", "d", "x", "y"],
            "visual": ["x", "d", "c", "b", "a", "y"],
            "motion": ["y", "d", "c", "b", "a", "x"],
        }
        disputed = reciprocal_rank_fusion(disagreed)
        decision = selective_vlm_decision(disputed, disagreed)
        self.assertTrue(decision["required"])
        self.assertLessEqual(len(decision["candidate_ids"]), 5)

    def test_compact_visual_index_and_fake_encoder_build(self):
        try:
            import cv2
            import numpy as np
        except ImportError:
            self.skipTest("OpenCV and NumPy are optional")

        class FakeEncoder:
            metadata = {"backend": "fake-test", "model": "fixture", "pretrained": "fixture"}

            def encode_images(self, frames):
                vectors = []
                for frame in frames:
                    mean = frame.astype(np.float32).mean(axis=(0, 1)) / 255.0
                    vectors.append([float(mean[0]) + 0.01, float(mean[1]) + 0.01, float(mean[2]) + 0.01, 1.0])
                return np.asarray(vectors, dtype=np.float32)

            def encode_texts(self, texts):
                return np.asarray([[0.1, 0.2, 0.3, 1.0] for _ in texts], dtype=np.float32)

        frame_paths = []
        for index, x in enumerate((8, 24, 40)):
            frame = np.zeros((64, 64, 3), dtype=np.uint8)
            frame[20:36, x : x + 12] = (80, 160, 240)
            path = Path(self.temp_dir.name) / f"index-{index}.png"
            cv2.imwrite(str(path), frame)
            frame_paths.append(path)
        manifest = {
            "cases": [
                {
                    "id": "fixture-motion",
                    "title": "Fixture Motion",
                    "url": "https://example.com/fixture-motion",
                    "media": [str(path) for path in frame_paths],
                }
            ]
        }
        arrays, metadata = build_index_data(
            manifest,
            base_dir=Path(self.temp_dir.name),
            encoder=FakeEncoder(),
            allow_unlisted=True,
        )
        index_path = Path(self.temp_dir.name) / "index.npz"
        metadata_path = Path(self.temp_dir.name) / "metadata.json"
        write_visual_index(index_path, **arrays)
        write_metadata(metadata_path, metadata)
        loaded = load_visual_index(index_path)
        loaded_metadata = load_metadata(metadata_path, loaded["case_ids"])
        self.assertEqual(loaded["case_ids"], ["fixture-motion"])
        self.assertEqual(loaded_metadata["case_count"], 1)
        query = np.asarray([[0.1, 0.2, 0.3, 1.0]], dtype=np.float32)
        scores = late_interaction_scores(query, loaded["frame_embeddings"], loaded["frame_offsets"])
        self.assertEqual(len(scores), 1)
        self.assertGreater(scores[0], 0)
        search_result = search_index(
            "卡片向右滑动",
            semantic_query="card slides right",
            index=loaded,
            metadata=loaded_metadata,
            encoder=FakeEncoder(),
            intent={"dominant_direction": "right"},
            limit=5,
        )
        self.assertEqual(search_result["status"], "ok")
        self.assertEqual(search_result["results"][0]["id"], "fixture-motion")
        self.assertIn("openclip_dynamic_region", search_result["ranking_channels"])
        self.assertFalse(search_result["vlm_review"]["required"])
        self.assertEqual(search_result["result_role"], "candidate-ordering-only")
        self.assertTrue(search_result["final_confidence_gate_required"])

    def test_synthetic_preview_has_no_source_claim(self):
        output = Path(self.temp_dir.name) / "synthetic.html"
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "build_preview.py"),
                "卡片 hover",
                "--output",
                str(output),
                "--limit",
                "2",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        html = output.read_text(encoding="utf-8")
        self.assertIn("Local synthesis only", html)
        self.assertIn("Local synthesis · no source claim", html)
        self.assertNotIn("Open source", html)
        self.assertNotIn("Uiverse", html)

    def test_evidence_board_builds_from_real_storyboard_and_rejects_synthetic(self):
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        rest = Path(self.temp_dir.name) / "rest.png"
        peak = Path(self.temp_dir.name) / "peak.png"
        rest.write_bytes(png)
        peak.write_bytes(png)
        manifest = {
            "query": "quiet button hover",
            "items": [
                {
                    "id": "uiverse-wise-goat-75",
                    "title": "Quiet radial glow button",
                    "direction": "Restrained radial glow",
                    "tradeoff": "Dark surfaces only",
                    "source": {"site": "Uiverse", "url": "https://uiverse.io/iZOXVL/wise-goat-75"},
                    "evidence": {
                        "kind": "storyboard",
                        "captured_at": "2026-08-18T00:00:00Z",
                        "trigger": "Hover the Explore button for 700ms",
                        "verification": "Exact public item live-verified",
                        "media": [
                            {"path": str(rest), "label": "Rest"},
                            {"path": str(peak), "label": "Hover peak"},
                        ],
                    },
                    "motion_dna": {"channels": ["gradient", "opacity", "translateY"]},
                    "rights_note": "Reference evidence only.",
                }
            ],
        }
        manifest_path = Path(self.temp_dir.name) / "evidence.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        output = Path(self.temp_dir.name) / "evidence.html"
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "build_evidence_board.py"), "--manifest", str(manifest_path), "--output", str(output)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        html = output.read_text(encoding="utf-8")
        self.assertIn("https://uiverse.io/iZOXVL/wise-goat-75", html)
        self.assertIn("data:image/png;base64,", html)

        manifest["items"][0]["evidence"]["kind"] = "synthetic"
        _, errors = prepare_manifest(manifest, Path(self.temp_dir.name))
        self.assertTrue(any("not synthetic" in error for error in errors))

    def test_chinese_spring_search(self):
        result = search_catalog("卡片出现时轻轻弹一下", stack="react", limit=3)
        self.assertEqual(result["matches"][0]["motion"]["id"], "entrance-spring-pop")
        self.assertTrue(result["matches"][0]["sites"])

    def test_chinese_saas_hero_search(self):
        result = search_catalog("SaaS 首页首屏的进入动效，要高级安静", stack="react", limit=4)
        ids = [match["motion"]["id"] for match in result["matches"]]
        self.assertEqual(ids[0], "entrance-soft-fade-up")
        self.assertIn("entrance-blur-reveal", ids)

    def test_asset_filter(self):
        result = search_catalog("成功勾选动画", capability="asset", limit=3)
        for match in result["matches"]:
            for site in match["sites"]:
                self.assertIn("asset", site["capabilities"])

    def test_update_notification_and_apply(self):
        catalog = load_json(SKILL_ROOT / "references" / "sites.json")
        version_parts = str(catalog["catalog_version"]).split(".")
        version_parts[-1] = str(int(version_parts[-1]) + 1)
        next_version = ".".join(version_parts)
        catalog["catalog_version"] = next_version
        catalog_bytes = (json.dumps(catalog, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        catalog_path = Path(self.temp_dir.name) / "candidate.json"
        catalog_path.write_bytes(catalog_bytes)
        examples_bytes = (SKILL_ROOT / "references" / "examples.jsonl").read_bytes()
        compressed_examples = gzip.compress(examples_bytes, mtime=0)
        compressed_examples_path = Path(self.temp_dir.name) / "examples.jsonl.gz"
        compressed_examples_path.write_bytes(compressed_examples)
        manifest = {
            "catalog_version": next_version,
            "schema_version": 1,
            "min_skill_version": "0.1.0",
            "published_at": "2026-08-18T00:00:00Z",
            "catalog_url": "https://github.com/example/releases/download/catalog/sites.json",
            "sha256": hashlib.sha256(catalog_bytes).hexdigest(),
            "examples_url": "https://github.com/example/releases/download/catalog/examples.jsonl.gz",
            "examples_sha256": hashlib.sha256(compressed_examples).hexdigest(),
            "examples_compression": "gzip",
            "examples_content_sha256": hashlib.sha256(examples_bytes).hexdigest(),
            "summary": {"added": 1, "removed": 0, "updated": 1},
        }
        manifest_path = Path(self.temp_dir.name) / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        check = check_update(manifest_file=manifest_path)
        self.assertEqual(check["status"], "update_available")
        self.assertTrue(check["notify"])
        repeated = check_update(manifest_file=manifest_path)
        self.assertFalse(repeated["notify"])
        legacy_manifest = dict(manifest)
        legacy_manifest.pop("examples_url")
        legacy_manifest.pop("examples_sha256")
        legacy_manifest.pop("examples_compression")
        legacy_manifest.pop("examples_content_sha256")
        self.assertEqual(validate_manifest(legacy_manifest), [])

        env = os.environ.copy()
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "update_catalog.py"),
                "--manifest-file",
                str(manifest_path),
                "--catalog-file",
                str(catalog_path),
                "--examples-file",
                str(compressed_examples_path),
                "--apply",
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "applied")
        self.assertTrue((Path(self.temp_dir.name) / "sites.json").exists())
        self.assertTrue((Path(self.temp_dir.name) / "examples.jsonl").exists())
        self.assertEqual((Path(self.temp_dir.name) / "examples.jsonl").read_bytes(), examples_bytes)


if __name__ == "__main__":
    unittest.main()
