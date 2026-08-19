# Retrieval Ladder

Use this deterministic ladder for every concrete-case discovery request. Exhaust local retrieval before considering the public Web.

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

## Interpret coverage

Use the script's deterministic candidate labels as a retrieval gate, then apply design judgment and source-health checks:

- `exact`: the candidate covers every requested mechanism, scene, and style group represented by the local expansion map.
- `adjacent`: the candidate covers only part of that request or has partial direct lexical overlap.
- `gap`: no meaningful local lexical or expanded match remains.

Treat platform as a compatibility filter, not a visual exactness requirement. Do not relabel an `adjacent` item as exact merely because it looks promising. Do not pad an eight-item result target with adjacent cases; show them separately as `本地相邻参考` when useful.

The script reports both `coverage.status` and `coverage.complete`. `status=exact` means at least one exact local case exists; `complete=true` means the exact local pool reached the requested result target. Current catalog metadata is still only retrieval evidence. Apply [source-health.md](source-health.md) before showing an item as eligible.

## Escalate to the public Web

Consider external search only when all three local stages have completed and `external_search.recommended=true`.

Before opening a search engine or an external result, tell the user:

```text
本地目录已完成类目、全库和同义词检索，仍存在覆盖缺口；现在进行一次聚焦的外网补充。
```

Use the emitted `external_search.query` for one focused initial query. Do not start an open-ended crawl. Search only for the missing mechanisms or combinations, not for already-covered facets.

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
  recommended: boolean
  reason: string
  query: string
  provenance_label: 外网补充
```

When explaining a shortfall, report the actual completed stage, exact count, adjacent count, and external supplement count separately.
