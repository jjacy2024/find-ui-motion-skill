# Catalog maintenance

This directory is maintainer-only and is not part of the installable Skill subtree.

## Cadence

- Weekly: run a shallow URL health report. Treat a single timeout or anti-bot response as evidence to review, not proof that a site is dead.
- Monthly: open representative pages in a normal browser and verify search, preview, copy/package/asset paths, authentication requirements, and current terms.
- Quarterly: collect candidates, score them against the weakest site in the same category, and keep roughly 12-16 active sites.
- Continuously: keep `examples.jsonl` near 280-300 current concrete item URLs across the active sites. Prioritize breadth of motion intent over many near-identical examples from one source.

## Lifecycle

Use `candidate -> active -> degraded -> quarantined -> retired` in maintainer records. The distributed `sites.json` contains only `active` and `degraded` sites. A degraded site remains searchable at lower rank; quarantined and retired sites stay outside the Skill.

## Update sequence

1. Edit the source catalog under `skills/find-ui-motion/references/sites.json` and representative deep examples under `references/examples.jsonl`.
2. Run `python3 skills/find-ui-motion/scripts/validate_catalog.py`.
3. Run `python3 maintainer/check_site_health.py` and `python3 maintainer/check_example_health.py`; investigate changes.
4. Shallow-check every exact item URL and update `last_shallow_check`. Browser-review selected items and trigger recipes; update `last_verified` only after interacting with the exact current item.
5. Run the repository tests.
6. Build a release manifest with `build_release_catalog.py` after immutable catalog and examples URLs are known. Keep the examples resource optional for compatibility with old single-file releases.
7. Test `check_catalog_update.py` and `update_catalog.py` against the release files in an isolated cache.
8. Publish the catalog and manifest only after review. Publication does not update user caches automatically.

## Admission gates

Require a real motion collection, one supported workflow, safe access, and an explicit capability boundary. Score relevance, uniqueness, delivery usefulness, license clarity, route stability, and freshness. Treat an unclear license as inspiration/recreate-only until a selected item is verified.

Do not silently add a remote URL, execute remote code, scrape protected implementations, or remove a site after one failed health check.

Do not commit captured screenshots, videos, or third-party assets. The examples index stores exact public item or official-source URLs, semantic trigger hints, preview strategy, shallow-check date, optional live-verification date, and rights boundary. If a publisher has no item permalink, use `source-with-category-preview`: keep the exact official source as `url`, the category locator as `preview_url`, and never mark it visually verified until the named case is observed there. Use `last_verified: null` until the current motion has been triggered or observed on the exact item.

`check_example_health.py` falls back to the system `curl` transport when the bundled Python TLS stack cannot negotiate with a source. Treat this as a transport compatibility path, not as deeper visual verification.

## Visual-index strategy

Precompute compact motion signatures during maintenance when repeated query-time capture becomes expensive. Store only the example ID, algorithm version, analysis depth, structured motion features, compressed numeric vectors when needed, and verification date. Keep source clips and keyframes transient and outside the repository.

Recompute a signature after the item URL, trigger behavior, or visible result changes. Treat a stale or metadata-only signature as text recall, not as visual deep-match evidence. Query-time analysis should refresh only missing, stale, or top-ranked candidates instead of recapturing the whole catalog.

Build a derived index from a reviewed capture manifest with `python3 skills/find-ui-motion/scripts/build_visual_index.py <manifest>`. Keep the resulting `index.npz`, metadata, OpenCLIP checkpoint, and source captures in the external cache or a release artifact, never under the installable Skill. Record the encoder model, checkpoint, source-media hash, and capture date. Rebuild only changed cases, and test retrieval with `search_visual_index.py` before publishing a compatible index.

The default LAION OpenCLIP ViT-B/32 checkpoint occupies roughly 577 MB in the local cache while a three-case, four-keyframe test index was about 24 KB. Treat checkpoint size and license as deployment concerns separate from the Skill package and derived index. Do not redistribute a model merely because the OpenCLIP library itself is permissively licensed.
