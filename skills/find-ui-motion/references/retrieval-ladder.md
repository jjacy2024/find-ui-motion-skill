# Retrieval Ladder

Use this deterministic ladder for every concrete-case discovery request. Exhaust local retrieval before considering the public Web.

## Apply the code-first source policy

Treat `video_case_search_authorized=false` as the default. The local script may recall mixed source types, so apply this policy after every retrieval stage and before computing the user-facing eligible count:

- `code-backed`: the exact item exposes an intentional snippet, documented package or component API, or a credible implementation source for the target stack.
- `runtime-backed`: the exact item provides a compatible Rive, Lottie, or similar runtime asset or documented integration path. A video used only to preview this same implementable item does not make it video-only.
- `video-only`: the item is useful only as recorded media or a video template and has no verified code, runtime asset, component API, or credible implementation path attached to it.

Rank `code-backed` and `runtime-backed` cases first. Exclude `video-only` cases from candidate pools, formal exact counts, the fifteen-item quick target, external supplements, and follow-up pages unless the user explicitly asks for video cases or confirms a proposed video supplement. An uploaded video can remain the user's reference without changing this authorization state.

Capturing a transient clip of a code-backed interactive demo for keyframe or trajectory analysis is allowed and is not video-case search.

## Run the local ladder

Run from the Skill directory:

```bash
python3 scripts/search_catalog.py "<user request>" --mode quick --quick-count 15 --formal-target 8 --strategy auto --candidate-limit 48 --trace --json
```

Use `--candidate-limit 64` only for broad, ambiguous, or visually exacting requests. Keep `--quick-count 15` for discovery and `--formal-target 8` for deep results. An explicit quick-pass request may raise the former to twenty; an explicit formal-result request may raise the latter to ten. Do not let one target silently change the other.

In quick mode, `auto` executes only the stages needed:

1. `taxonomy`: rank the compact motion taxonomy and recall its indexed examples.
2. `global`: always scan every eligible concrete example using its title, search terms, tags, motion metadata, trigger, target, and stack so the initial pool is broad rather than taxonomy-bound.
3. `global-expanded`: scan the same full local index with bundled bilingual mechanism, scene, style, and platform equivalences only when fewer than `min(10, quick_count)` meaningful candidates survive the global scan, no `strong` candidate exists, or no candidate covers at least half of the explicitly requested core groups.

Never infer that the global stage ran from the candidate count. Require a completed `global` trace record and report its real `examples_scanned` value when retrieval provenance matters.

## Interpret quick and strict coverage

Use two independent labels, then apply design judgment and source-health checks.

`quick_tier` controls quick discovery:

- `strong`: covers the explicitly represented core target, behavior, and trigger groups; preference keywords are not required.
- `related`: overlaps at least one requested core mechanism, scene, target, or trigger and remains useful for comparison even when other core groups differ.
- `exploratory`: has meaningful lexical, tag, preference, or adjacent-mechanism relevance and is worth showing for discovery, but should not be described as a close match.
- `off-target`: has no meaningful relationship to the request and cannot fill the quick-result target.

Style, feeling, intensity, and visual-tone groups are preferences. They improve `quick_score` and ordering but their absence never turns an otherwise useful quick candidate into an external-search requirement. Platform groups describe compatibility; a mismatch demotes a quick candidate to `reference-only` instead of silently treating Web code as native implementation.

Order the quick pool by `quick_tier` and `quick_score` before strict `coverage`. Aim for roughly five strong, six related, and four exploratory results at the default count when those tiers are available, then fill sparse tiers from the remaining meaningful pool. Keep approximately three items per source and one or two per near-duplicate family. These are diversity caps, not permission to include an off-target case. `--mode deep` reverses the primary ordering so strict `coverage` leads the fixed visual-review pool while retaining the quick tiers as secondary discovery signals.

`coverage` remains the strict deep-match retrieval label:

- `exact`: the candidate covers every requested mechanism, scene, and style group represented by the local expansion map.
- `adjacent`: the candidate covers only part of that request or has partial direct lexical overlap.
- `gap`: no meaningful local lexical or expanded match remains.

Treat platform as a compatibility filter, not a visual exactness requirement. Do not relabel an `adjacent` item as exact merely because it looks promising. Formal deep results still cannot be padded with adjacent cases. When strict provenance labels are useful, keep `本地准确匹配` and `本地相邻参考` separate. The quick pass may use `quick_tier=strong | related | exploratory` regardless of strict `coverage`, but it must exclude `off-target`.

The script reports strict `coverage`, separate `quick_coverage`, and the diversified `quick_candidates` list. `quick_coverage.complete=true` means the local delivery-ready pool reached the requested quick-result count with at least three sources by default. `coverage.complete=true` still means the exact local pool reached the separate formal target. Current catalog metadata is preliminary retrieval evidence only: it may be shown in the labeled fuzzy pass, but apply [source-health.md](source-health.md) before selected-case verification, capture, or formal deep ranking.

## Escalate to the public Web

Consider external search only after the quick-mode stopping rule recorded by the trace has completed: taxonomy plus the global fuzzy scan, and bilingual expansion only when fewer than ten meaningful candidates remained, no strong candidate existed, or the core behavior was still missing. Follow the deterministic `external_search.decision` three-state decision:

- `skip`: the local quick pool is sufficient; do not search externally.
- `offer`: show local results first, then ask whether the user wants one focused external supplement. Do not run it before confirmation.
- `required`: fewer than four delivery-ready `strong | related | exploratory` candidates remain; announce the gap and run one focused external query. `external_search.recommended=true` is reserved for this state.

Before opening a search engine or an external result, tell the user:

```text
本地目录已完成类目、全库和同义词检索，仍存在覆盖缺口；现在进行一次聚焦的外网补充。
```

Use the emitted `external_search.query` for one focused initial query. Do not start an open-ended crawl. Search only for the missing mechanisms or combinations, not for already-covered facets.

While video search is unauthorized, rewrite only the source-type portion of the focused query to target public code demos, snippets, packages, components, GitHub or CodePen examples, and the confirmed target stack. Exclude video platforms, social reels, stock footage, and video-template pages. If fewer than the requested number survive the code-first and source-health gates, report that code-case shortfall and ask whether the user wants a separate video supplement. Do not run it until the user confirms.

After confirmation, keep the same motion brief, run one bounded video-focused supplement, and label every surviving item `视频补充（已授权）`. Never treat authorization for one search as standing permission for later tasks.

For every external item:

- label provenance `外网补充`;
- keep local exact cases, local adjacent references, and external supplements visibly separate;
- deduplicate canonical item URLs against every local and previously shown result;
- apply the same direct-item and source-health gates before eligibility;
- never use an external category, search, collection, or homepage to fill a case slot;
- stop rather than pad when fewer than the requested number survive verification.

Do not add newly discovered external items to the catalog during ordinary discovery. Use the separate catalog maintenance and release workflow after review.

## Preserve the trace

Keep these fields in structured or internal results:

```yaml
strategy: auto
retrieval_level: taxonomy | global | global-expanded
examples_total: integer
coverage:
  status: exact | adjacent | gap
  complete: boolean
  exact_count: integer
  adjacent_count: integer
retrieval_trace: []
external_search:
  decision: skip | offer | required
  recommended: boolean
  reason: string
  query: string
  provenance_label: 外网补充
```

When explaining a shortfall, report quick strong/related/exploratory counts separately from strict exact/adjacent counts and external supplements.
