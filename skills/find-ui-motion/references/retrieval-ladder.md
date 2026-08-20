# Retrieval Ladder

Use this deterministic ladder for every concrete-case discovery request. Exhaust local retrieval before considering the public Web.

## Apply the code-first source policy

Treat `video_case_search_authorized=false` as the default. The local script may recall mixed source types, so apply this policy after every retrieval stage and before computing the user-facing eligible count:

- `code-backed`: the exact item exposes an intentional snippet, documented package or component API, or a credible implementation source for the target stack.
- `runtime-backed`: the exact item provides a compatible Rive, Lottie, or similar runtime asset or documented integration path. A video used only to preview this same implementable item does not make it video-only.
- `video-only`: the item is useful only as recorded media or a video template and has no verified code, runtime asset, component API, or credible implementation path attached to it.

Rank `code-backed` and `runtime-backed` cases first. Exclude `video-only` cases from candidate pools, exact counts, the eight-item quota, external supplements, and follow-up pages unless the user explicitly asks for video cases or confirms a proposed video supplement. An uploaded video can remain the user's reference without changing this authorization state.

Capturing a transient clip of a code-backed interactive demo for keyframe or trajectory analysis is allowed and is not video-case search.

## Run the local ladder

Run from the Skill directory:

```bash
python3 scripts/search_catalog.py "<user request>" --strategy auto --target-count 8 --candidate-limit 48 --trace --json
```

Use `--candidate-limit 64` only for broad, ambiguous, or visually exacting requests. Keep `--target-count 8` unless the user explicitly requests up to ten.

`auto` executes only the stages needed:

1. `taxonomy`: rank the compact motion taxonomy and recall its indexed examples.
2. `global`: scan every eligible concrete example using its title, search terms, motion metadata, trigger, and stack.
3. `global-expanded`: scan the same full local index with bundled bilingual mechanism, scene, style, and platform equivalences.

Never infer that the global stage ran from the candidate count. Require a completed `global` trace record and report its real `examples_scanned` value when retrieval provenance matters.

## Interpret quick and strict coverage

Use two independent labels, then apply design judgment and source-health checks.

`quick_fit` controls quick discovery:

- `strong`: matches every explicitly represented core target, behavior, and trigger group; preference keywords are not required.
- `usable`: matches at least half of those core groups, or is a useful preference-led result when no core group is present.
- `weak`: misses the core behavior or target and cannot fill the quick-result quota.

Style, feeling, intensity, and visual-tone groups are preferences. They improve `quick_score` and ordering but their absence never turns an otherwise useful quick candidate into an external-search requirement. Platform groups describe compatibility; a mismatch demotes a quick candidate to `reference-only` instead of silently treating Web code as native implementation.

`coverage` remains the strict deep-match retrieval label:

- `exact`: the candidate covers every requested mechanism, scene, and style group represented by the local expansion map.
- `adjacent`: the candidate covers only part of that request or has partial direct lexical overlap.
- `gap`: no meaningful local lexical or expanded match remains.

Treat platform as a compatibility filter, not a visual exactness requirement. Do not relabel an `adjacent` item as exact merely because it looks promising. Formal deep results still cannot be padded with adjacent cases. When strict provenance labels are useful, keep `本地准确匹配` and `本地相邻参考` separate. The quick pass may use `quick_fit=strong | usable` regardless of strict `coverage`, but it must exclude `quick_fit=weak`.

The script reports strict `coverage` and separate `quick_coverage`. `quick_coverage.complete=true` means the local delivery-ready pool reached the requested quick-result count with at least three sources by default. `coverage.complete=true` still means the exact local pool reached the formal target. Current catalog metadata is still only retrieval evidence. Apply [source-health.md](source-health.md) before showing an item as eligible.

## Escalate to the public Web

Consider external search only after the local stages recorded by the trace have completed. Follow the deterministic `external_search.decision` three-state decision:

- `skip`: the local quick pool is sufficient; do not search externally.
- `offer`: show local results first, then ask whether the user wants one focused external supplement. Do not run it before confirmation.
- `required`: fewer than four delivery-ready strong/usable candidates remain or the core behavior is absent; announce the gap and run one focused external query. `external_search.recommended=true` is reserved for this state.

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

When explaining a shortfall, report quick strong/usable counts separately from strict exact/adjacent counts and external supplements.
