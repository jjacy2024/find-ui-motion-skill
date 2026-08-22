# Exact Search

## Stage gate

Treat requests phrased as “find”, “show”, “recommend”, or “give me options” as discovery, even when the request contains enough detail to write code.

- Deliver a user-visible quick pass before visual deep matching. Only the user's explicit phrase `直接深度匹配` in the current request authorizes skipping that delivery. A screenshot, a highly specific brief, a request to choose or implement, urgency, internal retrieval, or a progress update does not authorize the skip.
- Default to `video_case_search_authorized=false`. A user must explicitly request video cases or explicitly approve a proposed video supplement before any video-only source search begins. Generic requests for examples, inspiration, or something cool do not authorize video search.
- Among semantically eligible candidates, prioritize cases with an attached public snippet, documented package or component API, compatible Rive or Lottie runtime asset, or credible platform-native recreation path. Exclude video-only cases from retrieval, result quotas, and follow-up pages while authorization is false.
- Return about fifteen concrete item links in the quick pass by default and at most twenty when explicitly requested before emitting deployable code. Use metadata, keywords, tags, synonyms, targets, triggers, and motion mechanisms for fuzzy recall. Quick eligibility accepts `quick_tier=strong | related | exploratory`; exclude only `off-target` and the hard exclusions in `SKILL.md`. Do not live-open every page before this pass. Reduce below fifteen only when the global fuzzy scan, plus synonym expansion when fewer than ten meaningful candidates remain or the core behavior is still missing, cannot supply enough unique cases.
- Treat `帮我找一个`, `推荐一个`, `给我一个最像的`, `选一个最合适的`, and equivalent soft-singular wording as recommendation intent. Keep `--quick-count 15 --formal-target 8`, mark the strongest quick case `recommended` or place it in a separate `最推荐` block, and preserve the remaining comparison set. Use a one-result quick target only for an explicit exclusive constraint such as `只要一个，不要其他候选`.
- Do not turn small add-ons to one base effect into separate candidates. Vary the core motion model, trigger response, or visual channel.
- Do not select for the user unless they ask the agent to decide. When they do ask, mark one candidate `recommended`, explain the choice briefly, and preserve the comparison unless they explicitly forbid other candidates.
- Transition to reference rebuild only after the user selects a candidate or explicitly asks to both choose and implement.
- If the user explicitly asks to both choose and implement, state the selected candidate and selection rationale, then follow the reference-rebuild gates before providing code.
- Attach a site or URL only when it belongs to the same catalog motion record as the candidate. Label a newly synthesized direction `local synthesis` with no source claim; never borrow a nearby site's name as evidence for a variant it did not supply.

## Workflow

1. Parse the request into a compact Motion Brief:
   - target;
   - trigger;
   - purpose;
   - motion channels;
   - feeling and intensity;
   - target platform;
   - stack and delivery constraints.
   - video-case search authorization.
2. Infer harmless omissions and label them `inferred`. Ask only when the missing answer changes the result class.
3. Read [retrieval-ladder.md](retrieval-ladder.md), then run `scripts/search_catalog.py` with `--mode quick --quick-count 15 --formal-target 8 --strategy auto --trace` and the user's confirmed filters. Let the script combine taxonomy and the full-index fuzzy scan; run bilingual expansion only when fewer than ten meaningful candidates remain, no `strong` candidate exists, or no candidate covers at least half of the explicit core groups. Post-filter and rerank the pool by the code-first source policy before counting `strong | related | exploratory` results. Preserve strict `coverage` and its separate formal target for deep matching.
4. Follow `external_search.decision`. For `skip`, use the local pool. For `offer`, return local results first and ask whether the user wants one focused supplement. For `required`, announce the local core-coverage gap and run one focused external query using the emitted query. Keep local results and `外网补充` visibly separate. While video search is unauthorized, constrain that query to code demos, snippets, packages, components, runtime assets, and target-platform implementation sources; exclude video platforms and video-template results. Group near-duplicate results and canonical URLs across every provenance class.
5. Resolve direct item URLs from catalog metadata, remove known broken records, canonical duplicates, collection/search/home routes, off-target items, unauthorized video-only items, and crowded near-duplicates. Do not collect live browser health evidence yet. Put useful collection or search routes under `继续探索入口`, never in the case list.
6. Unless the current request explicitly contains `直接深度匹配`, deliver the labeled quick pass now. Do not replace it with a retrieval count, progress summary, or early recommendation. For soft-singular wording, show the recommended case first and the rest of the default comparison set immediately after it.
7. Unless the user requests quick results only, read [visual-deep-match.md](visual-deep-match.md) and immediately begin its interruptible small-batch queue in the same task. Recall 48 cases by default and at most 64, then narrow to the documented 24-item live-check and 16-item capture limits before returning eight eligible ranked results by default or at most ten when explicitly requested. User feedback reprioritizes this queue; it is not a prerequisite for starting it.
8. When the user explicitly asks for a side-by-side comparison or saved result, read [source-preview.md](source-preview.md) and build verified evidence only after the direct links are available.
9. Transition to reference rebuild when the user asks to copy, integrate, download, or reproduce one candidate.

## Ranking priorities

Apply these priorities after removing semantically irrelevant candidates:

1. code implementation readiness and compatibility with the target platform and stack;
2. semantic and interaction fit;
3. delivery capability requested by the user;
4. source and license clarity;
5. site health and freshness;
6. dependency, accessibility, and performance cost.

Within the semantically eligible pool, rank a code-backed case above a video-only reference by default. Do not promote a weak or different behavior solely because code exists. When the user authorizes video search, preserve code-first results and label video results `视频补充（已授权）` unless the user explicitly asks to prioritize video inspiration.

## Internal result record

Keep this record internally or show it only when the user requests technical detail:

```yaml
direction: concise motion name
why_it_fits: one sentence
motion_dna:
  target: card
  trigger: enter
  channels: [opacity, translateY, scale]
  timing: soft spring, 280-420ms
delivery:
  likely_mode: snippet | package | asset | recreate
  platform: web | ios | android | cross-platform | unspecified
  stack: [css, javascript, react]
source:
  site: site name | local synthesis
  url: current or catalog route | null
  verification: catalog-only | live-verified
  health: shell_reachable | render_verified | capture_restricted | broken
  evidence: official-media | live-capture | storyboard | open-source-only | local-synthesis
tradeoff: one meaningful limitation
```

Do not precede quick links with a visible Motion Brief. Track `confirmed`, `inferred`, and materially important `unresolved` facts internally.

Attach `source` and `verification` to every candidate; do not place one ambiguous verification note after the whole list.

`verification: catalog-only` is allowed only in the explicitly labeled fuzzy quick pass and never proves current watchability. Do not use `health: shell_reachable` for selected-case evidence or formal deep ranking. When a later live check shows that the wrapper loads but critical item data fails, record `health: broken`, remove the item from the deep queue, and correct the earlier preliminary link if needed.

If `evidence=local-synthesis`, require `site=local synthesis` and `url=null`. Never combine synthetic media with a source claim.

Do not claim a result is copyable until the current example page and license have been checked. Do not show internal score percentages as user-facing certainty.
