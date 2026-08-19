# Exact Search

## Stage gate

Treat requests phrased as “find”, “show”, “recommend”, or “give me options” as discovery, even when the request contains enough detail to write code.

- Return exactly eight eligible concrete item links in the quick pass by default and at most ten when explicitly requested before emitting deployable code. Read and apply [source-health.md](source-health.md) first; only `render_verified` and `capture_restricted` items are eligible. Reduce below eight when the current filters yield fewer unique, relevant, content-healthy cases; return every eligible remainder, state why the target was not reached, and never add weak, duplicate, shell-only, or broken links.
- Do not turn small add-ons to one base effect into separate candidates. Vary the core motion model, trigger response, or visual channel.
- Do not select for the user unless they ask the agent to decide. Mark one candidate `recommended` when useful, but preserve the comparison.
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
2. Infer harmless omissions and label them `inferred`. Ask only when the missing answer changes the result class.
3. Read [retrieval-ladder.md](retrieval-ladder.md), then run `scripts/search_catalog.py` with `--strategy auto --target-count 8 --trace` and the user's confirmed filters. Let the script exhaust taxonomy, full-index, and expanded local retrieval before any Web supplement.
4. Keep `本地准确匹配`, `本地相邻参考`, and `外网补充` visibly separate. If and only if `external_search.recommended=true`, announce the local coverage gap and run one focused external query using the emitted query. Group near-duplicate results and canonical URLs across every provenance class.
5. Resolve concrete item URLs, collect current source-health evidence after `settle_ms`, and classify ambiguous observations with `scripts/classify_source_health.py`. Exclude `shell_reachable` and `broken` items before returning sparse quick links with one fit sentence each. Put collection or search routes under `继续探索入口`, never in the case list.
6. Unless the user requests quick results only, read [visual-deep-match.md](visual-deep-match.md), recall 48 cases by default and at most 64, then narrow to the documented 24-item live-check and 16-item capture limits before returning eight eligible ranked results by default or at most ten when explicitly requested.
7. When the user explicitly asks for a side-by-side comparison or saved result, read [source-preview.md](source-preview.md) and build verified evidence only after the direct links are available.
8. Transition to reference rebuild when the user asks to copy, integrate, download, or reproduce one candidate.

## Ranking priorities

Apply these priorities after the local score:

1. semantic and interaction fit;
2. compatibility with the target platform and stack;
3. delivery capability requested by the user;
4. source and license clarity;
5. site health and freshness;
6. dependency, accessibility, and performance cost.

Never rank a public snippet above a better behavioral match solely because it is easy to copy. Explain the tradeoff instead.

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

Never use `verification: catalog-only` or `health: shell_reachable` as direct-case eligibility. When the wrapper loads but critical item data fails, record `health: broken` and exclude the item.

If `evidence=local-synthesis`, require `site=local synthesis` and `url=null`. Never combine synthetic media with a source claim.

Do not claim a result is copyable until the current example page and license have been checked. Do not show internal score percentages as user-facing certainty.
