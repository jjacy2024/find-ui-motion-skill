# Visual Deep Match

Use this workflow after quick metadata retrieval when the user permits deeper matching. Its purpose is to inspect what candidate motions actually do, not to replace text retrieval with a slow crawl of every site.

## Start and stop contract

Before opening candidates, send one concise progress update that states:

- the fixed candidate-pool size and current stage;
- that live interaction, keyframes, and motion trajectories will be checked to improve ranking;
- that the user can reply `停止深度匹配` at any time;
- that Goal mode users can also pause from the goal progress row.

Continue in the same task after the quick links. Do not send a final answer and promise to return later.

When the user stops, do not start another page, capture, or analysis job. Let only an already-running safe tool call settle, then return the completed partial results and list the unchecked count. A paused Goal must not launch further work until resumed.

## Candidate pool and stopping conditions

Start from 12-20 unique concrete item URLs recalled by text, tags, and platform filters. Never analyze category or search routes as if they were examples. Exclude `open-source-only` records from visual ranking until the named case has been resolved and observed in its `preview_url`; otherwise keep them metadata-only. Stop when the first applicable condition is met:

- eight eligible matches have been visually ranked;
- 20 candidates have been checked;
- the filtered concrete-item pool is exhausted;
- three consecutive candidates cannot be accessed or triggered;
- the user stops or changes the request.

Do not fill a quota with duplicates, category routes, or weak candidates.

Treat eight as the default result target, not a soft maximum. Reduce below eight only when the qualifying pool is exhausted, 20 candidates have been checked, three consecutive candidates fail access or triggering, or the user stops or changes the request. Return every eligible result gathered so far and state the exact shortfall reason.

## Analyze real motion

For each candidate:

1. Open the exact public item, confirm it is still the intended example, and resolve the visible trigger again.
2. Capture a 2-5 second interaction at roughly 8-12 sampled frames per second when recording is available. Otherwise capture 4-8 real keyframes covering rest, onset, peak, and settle.
3. Use `scripts/analyze_motion_media.py` on the transient clip or ordered frames when OpenCV is available. Prefer its DIS result and accept the reported Farneback fallback. Use frame difference, dynamic region, and optical flow as trajectory evidence; do not treat them as object-semantic recognition.
4. When two or more candidates have real captures, read `visual-retrieval.md`, build or reuse a compatible external OpenCLIP index, and fuse metadata, full-frame, dynamic-region, and motion ranks with RRF.
5. Inspect retained keyframes with a vision-capable model only when the fusion result says `vlm_review.required=true`. Record the visible target, state change, hierarchy, occlusion or reveal pattern, and likely interaction meaning.
5. Delete or leave the media in task-scoped transient output. Never add third-party captures to the Skill or catalog.

Record an analysis depth for every candidate:

- `video-trajectory`: sampled clip plus visual-semantic review;
- `keyframes`: two or more real states plus visual-semantic review;
- `metadata-only`: no successful visual inspection; exclude it from the deep ranking.

If OpenCV, recording, or a vision tool is unavailable, use the strongest remaining evidence and disclose the downgrade. Never label metadata-only matching as visual deep matching.

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

Honor the selective VLM decision. Stop before VLM review when independent rankers agree. When they disagree, review at most the five returned IDs and report the real counter. Never send all 12-20 candidates to a VLM.

Return exactly eight eligible results by default and never more than ten when explicitly requested. Sort highest first. Reduce below eight only under the documented stopping conditions, never merely for brevity; state the shortfall reason. Each result contains only its rank, title with direct item link, one-sentence match reason, confidence, and analysis depth. State access, trigger, or rights failures after the ranked list.

## Report real progress

Report progress at stage changes or after roughly 3-5 completed candidates, not after every page. Use real counters only:

```text
视觉深度匹配：捕获阶段｜已检查 4/12｜成功 3｜受限 1
```

Allowed stages are `候选解析`, `交互捕获`, `特征分析`, and `融合重排`. Do not estimate a completion percentage unless the pool is fixed and work per candidate is genuinely comparable. Repeat the final links in the final answer because interim progress may be collapsed.
