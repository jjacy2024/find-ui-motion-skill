# Visual Deep Match

Use this workflow after quick metadata retrieval when the user permits deeper matching. Its purpose is to inspect what candidate motions actually do, not to replace text retrieval with a slow crawl of every site.

## Start and stop contract

Before opening candidates, send one concise progress update that states:

- the fixed recall, live-check, and capture-pool sizes and current stage;
- that live interaction, keyframes, and motion trajectories will be checked to improve ranking;
- that the user can reply `停止深度匹配` at any time;
- that Goal mode users can also pause from the goal progress row.

Continue in the same task after the quick links. Do not send a final answer and promise to return later.

When the user stops, do not start another page, capture, or analysis job. Let only an already-running safe tool call settle, then return the completed partial results and list the unchecked count. A paused Goal must not launch further work until resumed.

## Candidate pool and stopping conditions

Build and fix the cross-source catalog pool before opening any candidate page. Do not start from one site's category page, search page, or ad hoc shortlist and call that the deep-match pool. Recall 48 unique concrete item URLs by default and use at most 64 for a broad, ambiguous, or visually exacting request when the catalog contains enough relevant cases. Metadata recall, source diversity, compatible cached official media, and a compatible external visual index may operate across all 64 because they do not require live page capture. Reduce that pool to at most 24 items for current browser health checks, then capture and analyze at most the strongest 16 healthy items. Never increase the live-check or capture limit merely because the recall pool is larger.

At deep-match entry, request the deduplicated pool directly. Use `--candidate-limit 48` normally; change only that value to `64` for the maximum-recall cases above:

```bash
python3 scripts/search_catalog.py "<user request>" --strategy auto --target-count 8 --limit 10 --examples-per-motion 20 --candidate-limit 64 --candidate-pool-only --json
```

Use `candidate_pool`, not a concatenation of per-motion examples. It is already deduplicated and source-diversified for the first-pass shortlist. Keep `--candidate-pool-only` for deep retrieval so the 64-case pool is not duplicated inside the per-motion JSON payload. Preserve `coverage`, `retrieval_trace`, and external provenance from [retrieval-ladder.md](retrieval-ladder.md); never use adjacent or externally supplemented items as unlabeled exact matches.

Record the actual returned count before live checking. If fewer than the requested 48 or 64 candidates are returned, keep the smaller fixed pool and report that real denominator; do not silently replace it with a single-source scrape. A current source page may resolve or replace a concrete candidate only after this cross-source pool is fixed.

Read [source-health.md](source-health.md) and require current content health before capture. Never analyze category or search routes as if they were examples. Exclude `shell_reachable`, `broken`, and `open-source-only` records from visual ranking until the named case has been resolved and observed in its `preview_url`; otherwise keep them metadata-only. Stop when the first applicable condition is met:

- eight eligible matches have been visually ranked;
- 24 candidates have received current browser health checks;
- 16 healthy candidates have been captured and analyzed;
- the filtered concrete-item pool is exhausted;
- three consecutive candidates cannot be accessed or triggered;
- the user stops or changes the request.

Do not fill a quota with duplicates, category routes, or weak candidates.

Treat eight as the default result target, not a soft maximum. Reduce below eight only when the qualifying pool is exhausted, 24 candidates have been live-checked, 16 healthy candidates have been captured, three consecutive candidates fail access or triggering, or the user stops or changes the request. Return every eligible result gathered so far and state the exact shortfall reason.

## Analyze real motion

For each candidate:

1. Open the exact public item, wait for `settle_ms`, and confirm the named item produces a visible render target. Inspect current critical-response failures and console errors when the result is empty.
2. Classify the source with [source-health.md](source-health.md) or `scripts/classify_source_health.py`. Exclude `broken`; keep `shell_reachable` and `capture_restricted` out of visual ranking.
3. Resolve the visible trigger again and capture a 2-5 second interaction at roughly 8-12 sampled frames per second when recording is available. Otherwise capture 4-8 real keyframes covering rest, onset, peak, and settle.
4. Use `scripts/analyze_motion_media.py` on the transient clip or ordered frames when OpenCV is available. Prefer its DIS result and accept the reported Farneback fallback. Use frame difference, dynamic region, and optical flow as trajectory evidence; do not treat them as object-semantic recognition.
5. When two or more candidates have real captures, read `visual-retrieval.md`, build or reuse a compatible external OpenCLIP index, and fuse metadata, full-frame, dynamic-region, and motion ranks with RRF.
6. Inspect retained keyframes with a vision-capable model only when the fusion result says `vlm_review.required=true`. Record the visible target, state change, hierarchy, occlusion or reveal pattern, and likely interaction meaning.
7. Delete or leave the media in task-scoped transient output. Never add third-party captures to the Skill or catalog.

Record an analysis depth for every candidate:

- `video-trajectory`: sampled clip plus visual-semantic review;
- `keyframes`: two or more real states plus visual-semantic review;
- `metadata-only`: no successful visual inspection; exclude it from the deep ranking.

If OpenCV, recording, or a vision tool is unavailable, use the strongest remaining evidence and disclose the downgrade. Never label metadata-only matching as visual deep matching.

If capture fails, do not immediately count it as a GPU or capture limitation. First prove that the item rendered. Missing critical data, a content-fetch error, or an absent expected render target after settling makes the item `broken`; a capture failure is `capture_restricted` only after visible content is confirmed.

## Motion signature

Keep the signature compact:

```yaml
motion_signature:
  target: visible element or region
  trigger: mount | hover | click | scroll | gesture | loop | manual
  state_change: concise before -> after
  visual_semantics: [reveal, continuity, emphasis]
  channels: [opacity, transform, mask]
  dominant_direction: up | down | left | right | mixed | static
  changed_region: top | center | bottom | left | right | full
  timing_character: front-loaded | even | peaked | rear-loaded
  interruption: observed | not-observed
analysis_depth: video-trajectory | keyframes | metadata-only
```

## Fuse and rank

Rank only `video-trajectory` and `keyframes` candidates. Prefer these independent channels when available:

- metadata text recall;
- OpenCLIP full-frame similarity;
- OpenCLIP dynamic-region similarity;
- DIS or Farneback motion-signature similarity;
- platform, rights, source quality, and delivery rank.

Fuse available ranks with Reciprocal Rank Fusion through `scripts/search_visual_index.py` or `scripts/rank_visual_matches.py`. Do not average raw cosine, trajectory, and metadata scores as if they were calibrated. Treat every score as a relative ordering aid, not a probability. Do not show fake precision such as `92% match`. Derive `高`, `中`, or `低` confidence from rank agreement and disclose that routing thresholds remain heuristic until calibrated.

Honor the selective VLM decision. Stop before VLM review when independent rankers agree. When they disagree, review at most the five returned IDs and report the real counter. Never send all 48-64 recalled candidates or all 24 live-checked candidates to a VLM.

Return exactly eight eligible results by default and never more than ten when explicitly requested. Sort highest first. Reduce below eight only under the documented stopping conditions, never merely for brevity; state the shortfall reason. Each result contains only its rank, title with direct item link, one-sentence match reason, confidence, and analysis depth. State access, trigger, or rights failures after the ranked list.

## Report real progress

Report progress at stage changes or after roughly 3-5 completed candidates, not after every page. Use real counters only:

```text
视觉深度匹配：交互捕获｜召回 48/64｜实时检查 12/24｜捕获 8/16｜受限 2
```

Allowed stages are `候选解析`, `交互捕获`, `特征分析`, and `融合重排`. Do not estimate a completion percentage unless the pool is fixed and work per candidate is genuinely comparable. Repeat the final links in the final answer because interim progress may be collapsed.
