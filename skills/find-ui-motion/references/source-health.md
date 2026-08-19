# Source Health Gate

Apply this gate before showing any direct dynamic or interactive case link. A successful outer-page request proves only that the publisher's shell is reachable; it does not prove that the named item still exists or renders.

## Collect current browser evidence

Open the exact public item in an available browser, wait for the catalog `settle_ms`, then record only visible or browser-reported evidence. When an `official-media` record exposes `preview_url`, treat that exact official item preview as the watch target and keep `url` as the attribution/source page:

- final item URL and outer HTTP status when available;
- failed or non-success responses for critical item data observed during this load;
- console errors that identify missing or unavailable item data;
- expected visible render targets such as `canvas`, `video`, `iframe`, image, or the named demo region, including non-zero visible dimensions;
- whether the source visibly rendered even if capture failed;
- capture success and later motion-analysis depth when applicable.

For official video, GIF, Lottie, or Rive previews, require a non-zero visible player or canvas and observable frame change after settling. A successful Range request or catalog field alone is transport evidence, not `render_verified`. If the exact official preview renders but the attribution page does not, link the preview as `观看动效`, label the page separately as `来源页（当前不可用）`, and do not imply that the page itself was healthy.

Do not discover private endpoints, inspect minified source, or guess provider-specific asset URLs. Use only requests and errors emitted by the current public page.

## Classify before eligibility

Use exactly one state:

- `shell_reachable`: the outer page loads but current content rendering is unconfirmed, unavailable, or access-restricted;
- `render_verified`: the named item produces a visible non-zero render target or was directly observed after settling;
- `capture_restricted`: the item visibly renders, but the available capture path fails or is restricted;
- `broken`: the selected exact item or official watch target, or its critical item data, returns 404/410/5xx, reports a content-fetch/not-found error, redirects away from the item, or lacks the expected render target after settling.

Run the deterministic classifier when several signals are involved:

```bash
python3 scripts/classify_source_health.py <browser-observation-manifest.json>
```

The manifest shape is:

```json
{
  "cases": [
    {
      "id": "catalog-example-id",
      "outer_status": 200,
      "settled": true,
      "redirected_away": false,
      "access_restricted": false,
      "expects_render_target": true,
      "critical_responses": [{"label": "project-data", "status": 404}],
      "console_errors": ["Error fetching data for project id"],
      "render_targets": [],
      "visually_observed": false,
      "capture_attempted": true,
      "capture_succeeded": false,
      "analysis_depth": "metadata-only"
    }
  ]
}
```

Treat `quick_eligible=true` as the minimum direct-case gate. Treat `deep_eligible=true` as an additional ranking gate, not a replacement for source health.

## Hard exclusions

- Never infer health from HTTP 200 on the wrapper alone.
- Never call an empty page a GPU or screenshot limitation before checking current item-data failures, console errors, and expected render targets.
- Never use `open-source-only` to rescue a `broken` item. That evidence class is allowed only when the exact source exists and its content is visible or the named case is resolved through an explicit category locator.
- Never show `shell_reachable` or `broken` items in the eligible quick-case list. Return fewer results and state that the content-health gate exhausted the pool.
- Keep `last_shallow_check` as metadata recall only. It cannot satisfy current eligibility.

## Capture boundary

If capture fails after visible content is confirmed, classify `capture_restricted`, link the exact source, and exclude it from visual deep ranking. If both content and capture are unconfirmed, classify `shell_reachable`; do not present it as a watchable case.
