# Exact Search

## Stage gate

Treat requests phrased as “find”, “show”, “recommend”, or “give me options” as discovery, even when the request contains enough detail to write code.

- Return exactly eight eligible concrete item links in the quick pass by default and at most ten when explicitly requested before emitting deployable code. Reduce below eight only when the current filters yield fewer unique, relevant, accessible item cases; return every eligible remainder, state why the target was not reached, and never add weak or duplicate links.
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
3. Run `scripts/search_catalog.py` with the user's natural-language request and confirmed filters.
4. Group near-duplicate results. Resolve concrete item URLs and return sparse quick links with one fit sentence each. Put collection or search routes under `继续探索入口`, never in the case list.
5. Unless the user requests quick results only, read [visual-deep-match.md](visual-deep-match.md), visually inspect a bounded 12-20-item pool, and return eight eligible ranked results by default or at most ten when explicitly requested.
6. When the user explicitly asks for a side-by-side comparison or saved result, read [source-preview.md](source-preview.md) and build verified evidence only after the direct links are available.
7. Transition to reference rebuild when the user asks to copy, integrate, download, or reproduce one candidate.

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
  evidence: official-media | live-capture | storyboard | open-source-only | local-synthesis
tradeoff: one meaningful limitation
```

Do not precede quick links with a visible Motion Brief. Track `confirmed`, `inferred`, and materially important `unresolved` facts internally.

Attach `source` and `verification` to every candidate; do not place one ambiguous verification note after the whole list.

If `evidence=local-synthesis`, require `site=local synthesis` and `url=null`. Never combine synthetic media with a source claim.

Do not claim a result is copyable until the current example page and license have been checked. Do not show internal score percentages as user-facing certainty.
