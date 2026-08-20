---
name: find-ui-motion
description: Find UI motion for Web and mobile, including 网页动效、App 动效、交互动效、微动效和动画灵感. Use when a user wants to 找、搜索、推荐、比较、预览、复制、复刻、还原或实现界面动画; mentions hover, gesture, transition, navigation, scroll, loading, text animation, page or screen entrance, CSS, JavaScript, React, Vue, SwiftUI, Jetpack Compose, Flutter, React Native, Lottie, or Rive; asks to see real source examples; has only a vague motion idea; asks for 动效网站或动画参考; or provides a webpage, app screenshot, link, image, or video as a motion reference. Guide vague requests through questions, exhaust deterministic local taxonomy, full-index, and synonym-expanded retrieval before bounded Web supplementation, show live-verified source evidence, then deliver a platform-compatible public snippet, package integration, licensed asset, or independent recreation. Prioritize code-backed, target-compatible cases; search video-only cases only after explicit user authorization. Do not use for static UI design, ordinary development without motion, or general video editing.
---

# Find UI Motion

Use the local catalog for fast recall. Exhaust its deterministic retrieval ladder before external discovery. Access selected websites to resolve concrete item links, inspect real motion, verify current source material, or perform one bounded supplement after a confirmed local coverage gap.

Keep the source environment and target platform separate. A Web example may be valid visual evidence for a mobile interaction, but its code is not automatically compatible with the mobile runtime.

## Announce the bundled Catalog once

On the first Skill use in each task, read [catalog-overview.md](references/catalog-overview.md), run its local summary command, and include the returned source-site and case counts once in the first substantive reply. This notice must not delay the user's motion task or repeat later in the task.

If the user expresses interest in the website list, use the same reference to return every Catalog source as a clickable public homepage link. Do not open any source automatically; the user manually chooses which link to visit unless they separately ask the agent to browse it.

## Route the request

Choose exactly one primary workflow, then transition when the user makes a selection:

1. **Exact search**: the user can describe the target, trigger, behavior, or stack. Read [exact-search.md](references/exact-search.md).
2. **Inspiration exploration**: the user has a vague goal, feeling, or problem. Read [inspiration-exploration.md](references/inspiration-exploration.md).
3. **Reference rebuild**: the user supplies or selects a reference and wants usable output. Read [reference-rebuild.md](references/reference-rebuild.md).

Do not force a vague request into exact search. Do not treat a visually similar result as permission to copy its source.

## Require authorization for video-case search

Start every task with `video_case_search_authorized=false`. Change it to `true` only when the user explicitly asks for video cases or explicitly confirms a proposed video supplement. A request such as “看案例”, “酷炫一点”, “想看效果”, or “给我参考” is not video-search authorization by itself. A user-supplied video may be analyzed as the supplied reference, but it does not authorize searching for additional video cases.

While authorization is false:

- Prioritize code-backed interactive demos, intentionally exposed snippets, documented packages or components, target-compatible Rive or Lottie runtime examples, and cases with a credible platform-native recreation path.
- Exclude video-only sources and video-platform searches from candidate pools, result quotas, external supplements, and follow-up pages. A video-only case is consumed only as recorded media and has no verified snippet, package, runtime asset, component API, or credible implementation path attached to the same item.
- Do not ask for video permission when enough code-implementable cases can satisfy the request. If the code-first pool is insufficient, report the verified shortfall and ask whether the user wants a separately labeled video supplement; do not start that search before confirmation.

A transient clip recorded from a code-backed interactive demo for motion analysis is evidence capture, not video-case search. A code-backed Rive, Lottie, package, or component case does not become video-only merely because its publisher uses a video preview.

## Use the local catalog

Read [retrieval-ladder.md](references/retrieval-ladder.md) before concrete-case discovery.

Run local search from the Skill directory:

```bash
python3 scripts/search_catalog.py "<user request>" --strategy auto --target-count 8 --candidate-limit 48 --trace
```

Add `--stack`, `--capability`, or `--kind` only when the user has supplied those constraints and the local catalog represents them. For a native target with no matching catalog stack, search by behavior without the stack filter, then apply platform compatibility during reference rebuild. Use `--json` when another script or structured comparison needs the result.

Treat search scores as retrieval hints, not final design judgment. Inspect the best matches and remove incompatible or repetitive candidates. Never infer quality from source volume; preserve cross-source diversity when several sources contain similarly relevant concrete items.

Before returning candidates, classify them internally as `code-backed | runtime-backed | video-only`. Unless video search is authorized, remove `video-only`, then rank the remaining semantically relevant cases by target-platform implementation readiness before source spectacle or visual polish.

Let `auto` decide whether to escalate from taxonomy recall to a text scan of every eligible local example and then bundled bilingual query expansion. Never open Google or another search engine before the script completes the local ladder and returns `external_search.recommended=true`. Announce the local coverage gap before one focused external query. Label every such item `外网补充`, keep it separate from `本地准确匹配` and `本地相邻参考`, and apply the same direct-item, deduplication, and source-health gates.

## Offer high-quality new sources for review

When a bounded external supplement produces an `exact`, high-confidence, live `render_verified` concrete item from a code-backed or runtime-backed domain absent from the current `sites.json`, read [source-suggestion.md](references/source-suggestion.md). Run its deterministic eligibility check and offer the source once per domain per task. Stay silent when any gate fails.

The offer must use the approved message from that reference. After the user agrees, the proposed submission contains exactly one field, `网站名称与域名`. Never submit automatically: prefer opening a prefilled GitHub Issue for the user to submit, and use email only as an explicitly configured fallback. Creating an Issue or sending email requires separate explicit authorization after the user sees the one-field payload.

Generate a synthetic local direction board only when comparing newly synthesized motion DNA:

```bash
python3 scripts/build_preview.py "<user request>" --output <absolute-output.html> --limit 6
```

The board demonstrates motion DNA with generic shapes. Label every card `local-synthesis`; never attach a source site, source item, or source URL to it.

## Return quick links first

For discovery after any necessary inspiration conversation, return a quick metadata-based pass before visual deep matching:

- Read [source-health.md](references/source-health.md) and apply its current content-health gate before calling any dynamic or interactive item eligible. An outer-page HTTP 200, `last_shallow_check`, or catalog record alone never proves that the named item still renders.
- Show exactly eight eligible concrete case links by default and never more than ten when the user explicitly requests more. Include only items classified `render_verified` or `capture_restricted`. Reduce the count below eight only when fewer than eight unique, relevant, content-healthy cases remain; return every eligible remainder and state the shortfall reason. Never pad the list with weak, duplicate, inaccessible, broken, shell-only, or non-item links.
- Never count a local `adjacent` case as an exact result merely to reach eight. When external supplementation is needed, present local exact, local adjacent, and external cases under visibly separate provenance labels.
- Count code-backed or runtime-backed cases first. Do not include or count a video-only item unless `video_case_search_authorized=true`; when authorized, place those items under `视频补充（已授权）` instead of mixing them into the default code-first list.
- Link directly to each public item or demo. For a live-observed `official-media` record, use its `preview_url` as `观看动效` and keep the item `url` separately as `来源页`; never send an empty wrapper as the watch link. Do not put a category, search, collection, or homepage in the case list; label those separately as `继续探索入口`.
- Use one short sentence per case. Omit long Motion Briefs, Motion DNA cards, YAML, and generic prose from the visible quick result.
- Label the pass `快速初筛，尚未完成视觉复核` and state whether visual deep matching will continue.
- Interpret `换一批` as the next page of three by default. Accept a requested size up to ten and exclude every case ID and canonical item URL already shown in the task.

If the user says `只要快速结果`, stop after the quick pass. Otherwise continue visual deep matching in the same task when concrete item links and visual tools are available. If the user says `直接深度匹配`, skip the visible quick pass but still create a bounded text-recalled candidate pool.

## Show and analyze real source evidence

Read [source-preview.md](references/source-preview.md) when the user asks to see examples, when visual comparison materially affects a choice, or before implementing a selected live reference.

Use the indexed concrete examples returned by `search_catalog.py` when they fit. Treat `last_shallow_check` as outer-shell availability only; only a non-null `last_verified` records prior live interaction. Apply [source-health.md](references/source-health.md) before eligibility and diagnose empty dynamic pages through current network errors, console errors, and expected render targets before blaming GPU or capture limitations. A `source-with-category-preview` record is an exact official source plus a category locator, not a direct or visually verified item page; show both links and label the limitation. Open and re-resolve the current visible interaction because stored trigger hints are not selectors. Prefer an official preview, then a transient live capture, then a real-state storyboard, and finally the exact live page.

Read [visual-deep-match.md](references/visual-deep-match.md) before visually ranking candidates. Announce its purpose, real stage and counters, and stop instructions before starting. Use a staged funnel: recall 48 cases by default and at most 64, live-check at most 24, and capture at most 16. Separate semantic match quality (`exact | adjacent | unresolved`) from evidence confidence (`高 | 中 | 低`). Formal results must be `exact` and `高` or `中`. If fewer than eight qualify, continue checking later candidates within the existing 24 live-check and 16 capture budgets; never pad with low-confidence or adjacent cases. Return fewer only after a documented stopping condition and state the confidence shortfall. Do not call metadata-only matching visual deep matching.

When real candidate captures or a compatible cached index are available, read [visual-retrieval.md](references/visual-retrieval.md). Use OpenCLIP full-frame and dynamic-region embeddings, DIS optical flow with Farneback fallback, and RRF before deciding whether a VLM is needed. Treat `search_visual_index.py` as candidate retrieval and fusion only; pass reviewed candidates through `rank_visual_matches.py` before presenting formal results. Keep models, captures, and indexes outside the Skill. If `vlm_review.required=false`, stop before VLM inspection; if true, inspect only the returned candidate IDs, never the whole pool.

Build a self-contained evidence board only when the user explicitly asks to compare cases side by side, organize them into a page, or save the result:

```bash
python3 scripts/build_evidence_board.py --manifest <absolute-manifest.json> --output <absolute-evidence.html>
```

Never substitute local synthesis for failed source evidence. If capture fails or is restricted, say so and open the exact source instead. Do not create an aggregation page as a search intermediate or default result.

## Target the delivery platform

Track the target as `web | ios | android | cross-platform | unspecified`. Infer it from the user's project or request when safe; ask only when it would change the deliverable.

- Use a public snippet only when its language and runtime match the target. Do not deliver Web code as a mobile implementation.
- Use a package only when it supports the target framework and version; generate the platform-specific install command, import, and smallest working usage.
- Treat Lottie and Rive as potentially cross-platform assets, not guaranteed ones. Verify format, runtime support, license, and feature parity on the target.
- When direct reuse is incompatible, recreate the motion with platform-native APIs such as SwiftUI, Jetpack Compose, Flutter, or React Native.
- Preserve the target platform's reduced-motion or animation accessibility behavior and verify the result in the actual runtime when available.

## Check for catalog updates

On the first Skill use in a task, run the lightweight manifest check after the local result is available, or in parallel when possible:

```bash
python3 scripts/check_catalog_update.py
```

Rules:

- Never delay the primary task beyond the script's short network timeout.
- Stay silent for `disabled`, `current`, `not_modified`, `offline_or_unreachable`, or a repeated notification.
- When `status=update_available` and `notify=true`, append one short reminder containing current version, latest version, and summary.
- Never apply an update merely because one exists.
- When the user explicitly asks to update the catalog, run `python3 scripts/update_catalog.py --apply`, report validation results, and retain the bundled fallback.
- When `status=skill_update_required`, do not apply the catalog; explain the required Skill version.

## Apply source and rights gates

Before copying, installing, downloading, or recreating:

- Open the current source page and verify the selected example still exists.
- Treat a reachable wrapper with missing critical item data or no expected render target as `broken`, even when the wrapper returns HTTP 200.
- Verify the example-level license or terms; a site-level catalog label is not enough when `license.status` is `item-specific`, `unclear`, or `restricted`.
- Do not bypass authentication, paywalls, anti-bot challenges, download controls, minification, or obfuscation.
- Do not call page-source extraction a public snippet. A snippet must be intentionally exposed by the publisher.
- State whether the result is copied, package-based, asset-based, or recreated.
- State both the source environment and target platform, and identify any translation from Web behavior to a mobile implementation.
- Preserve `prefers-reduced-motion` behavior and flag performance-heavy layout, canvas, WebGL, video, or large-runtime choices.

## Return a useful result

For quick discovery, return sparse direct case links as specified above. For visual deep matching, the formal list contains only exact high/medium-confidence cases and returns rank, linked title, one-sentence fit reason, confidence (`高 | 中`), and analysis depth (`video-trajectory | keyframes`). Put high/medium adjacent references in a separately labeled section only when useful. Keep low-confidence cases out of the formal list; mention their count or expose them as alternates only when the user asks. Keep technical signatures internal unless the user asks for them. Repeat the final links in the final answer even when they appeared in progress updates.

For an explicit comparison, add only the distinctions that help selection: trigger, visible behavior, platform fit, evidence depth, and one meaningful tradeoff. Do not make the user infer motion from prose when a real item link is available.

For implementation, include files or code changed, dependencies, provenance, selected fallback level, rejected levels with reasons, and verification performed.

## Keep confidence explicit

Separate:

- `confirmed`: stated or selected by the user;
- `inferred`: reasonable working assumptions;
- `unresolved`: details that materially affect the next step.

Ask only when an unresolved item would substantially change the direction, licensing, runtime dependency, or deliverable.
