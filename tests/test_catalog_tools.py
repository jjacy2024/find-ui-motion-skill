from __future__ import annotations

import base64
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
sys.path.insert(0, str(SCRIPTS))

from build_evidence_board import prepare_manifest  # noqa: E402
from build_visual_index import build_index_data  # noqa: E402
from catalog_lib import load_examples, load_json, load_motions, search_catalog, validate_catalog_data  # noqa: E402
from check_catalog_update import check_update, validate_manifest  # noqa: E402
from analyze_motion_media import analyze, extract_dynamic_crops  # noqa: E402
from rank_visual_matches import rank_manifest  # noqa: E402
from retrieval_fusion import reciprocal_rank_fusion, selective_vlm_decision  # noqa: E402
from search_visual_index import search_index  # noqa: E402
from visual_index import late_interaction_scores, load_metadata, load_visual_index, write_metadata, write_visual_index  # noqa: E402


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
        self.assertEqual(len(catalog["sites"]), 14)
        site_ids = {site["id"] for site in catalog["sites"]}
        self.assertTrue({"uiverse", "unicorn-studio", "lottielab", "design-spells", "transitions-dev", "originkit", "pixel-perfect"} <= site_ids)
        self.assertTrue({"hover-css", "codepen", "lottiefiles"}.isdisjoint(site_ids))
        self.assertGreaterEqual(len(motions), 60)
        self.assertGreaterEqual(len(examples), 280)
        self.assertLessEqual(len(examples), 300)
        self.assertGreaterEqual(len({example["site_id"] for example in examples}), 14)
        self.assertGreaterEqual(len({motion_id for example in examples for motion_id in example["motion_ids"]}), 60)
        self.assertEqual(len({example["id"] for example in examples}), len(examples))
        self.assertEqual(len({example["url"].rstrip("/") for example in examples}), len(examples))
        self.assertTrue(all(example["last_shallow_check"] for example in examples))
        self.assertGreaterEqual(sum(example["last_verified"] is not None for example in examples), 3)

    def test_near_290_expansion_covers_new_sources_and_missing_families(self):
        examples, errors = load_examples(SKILL_ROOT / "references" / "examples.jsonl")
        self.assertEqual(errors, [])
        example_sites = {example["site_id"] for example in examples}
        self.assertTrue({"animista", "lottielab", "rive-community", "unicorn-studio"} <= example_sites)
        sites_by_motion: dict[str, set[str]] = {}
        for example in examples:
            for motion_id in example["motion_ids"]:
                sites_by_motion.setdefault(motion_id, set()).add(example["site_id"])
        expected = {
            "feedback-error-shake": "animista",
            "exit-scale-out": "animista",
            "loading-spinner": "lottielab",
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

    def test_exact_example_is_attached_to_matching_motion(self):
        result = search_catalog("SaaS 首页首屏高级安静的进入动效", stack="react", limit=4)
        blur = next(match for match in result["matches"] if match["motion"]["id"] == "entrance-blur-reveal")
        self.assertEqual(blur["examples"][0]["id"], "magic-ui-blur-fade")
        self.assertEqual(blur["examples"][0]["url"], "https://magicui.design/docs/components/blur-fade")

    def test_expanded_examples_are_retrievable_beyond_top_three_sites(self):
        checks = {
            "滚动文字逐字揭示": ("scroll-text-scrub", "originkit"),
            "左右横向画廊": ("scroll-horizontal", "gsap-demos"),
            "按钮跟随鼠标": ("hover-magnetic", "motion"),
            "卡片展开成详情": ("transition-container-transform", "gsap-demos"),
        }
        for query, (motion_id, expected_site) in checks.items():
            result = search_catalog(query, limit=4, examples_per_motion=10)
            match = next(item for item in result["matches"] if item["motion"]["id"] == motion_id)
            self.assertIn(expected_site, {example["site_id"] for example in match["examples"]})
            self.assertTrue(all(example["last_shallow_check"] for example in match["examples"]))

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

        for rule in (
            "exactly eight eligible concrete case links by default",
            "Reduce the count below eight only when fewer than eight",
            "快速初筛，尚未完成视觉复核",
            "继续探索入口",
            "Do not create an aggregation page",
        ):
            self.assertIn(rule, skill_text)
        for rule in (
            "停止深度匹配",
            "12-20 unique concrete item URLs",
            "20 candidates",
            "three consecutive candidates",
            "OpenCLIP full-frame similarity",
            "Reciprocal Rank Fusion",
            "vlm_review.required=true",
            "Return exactly eight eligible results by default",
            "never merely for brevity",
            "Do not show fake precision",
            "已检查 4/12",
        ):
            self.assertIn(rule, deep_rules)
        self.assertIn("Build a board only when the user explicitly requests", preview_rules)

        retrieval_rules = (SKILL_ROOT / "references" / "visual-retrieval.md").read_text(encoding="utf-8")
        for rule in (
            "open_clip_torch",
            "dynamic-region",
            "Farneback fallback",
            "RRF",
            "vlm_review",
            "status=degraded",
        ):
            self.assertIn(rule, retrieval_rules)

    def test_visual_ranking_is_bounded_sorted_and_excludes_metadata_only(self):
        candidates = [
            {
                "id": "medium",
                "title": "Medium",
                "url": "https://example.com/medium?utm_source=test",
                "analysis_depth": "keyframes",
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
        self.assertIsNotNone(result["shortfall_reason"])
        self.assertIn("not a probability", result["score_note"])
        default_result = rank_manifest({"query": "test", "candidates": candidates})
        self.assertEqual(default_result["target_result_count"], 8)
        with self.assertRaisesRegex(ValueError, "between 1 and 10"):
            rank_manifest({"candidates": []}, limit=11)

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
        manifest = {
            "catalog_version": next_version,
            "schema_version": 1,
            "min_skill_version": "0.1.0",
            "published_at": "2026-08-18T00:00:00Z",
            "catalog_url": "https://github.com/example/releases/download/catalog/sites.json",
            "sha256": hashlib.sha256(catalog_bytes).hexdigest(),
            "examples_url": "https://github.com/example/releases/download/catalog/examples.jsonl",
            "examples_sha256": hashlib.sha256(
                (SKILL_ROOT / "references" / "examples.jsonl").read_bytes()
            ).hexdigest(),
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
                str(SKILL_ROOT / "references" / "examples.jsonl"),
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


if __name__ == "__main__":
    unittest.main()
