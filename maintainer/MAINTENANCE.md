# Catalog maintenance

This directory is maintainer-only and is not part of the installable Skill subtree.

## Cadence

- Weekly: run a shallow URL health report. Treat a single timeout or anti-bot response as evidence to review, not proof that a site is dead.
- Monthly: open representative pages in a normal browser and verify search, preview, copy/package/asset paths, authentication requirements, and current terms.
- Quarterly: collect candidates, score them against the weakest site in the same category, and keep roughly 16-20 active sites while the 3,000-case catalog remains compact enough for local retrieval.
- Continuously: grow the evidence-backed active index toward or above 3,000 concrete item URLs through allowlisted public indexes. Never retain or re-add an unverified case merely to satisfy the count. Preserve source diversity in search results and keep the largest source at or below 80% of bundled records.

## Lifecycle

Use `candidate -> active -> degraded -> quarantined -> retired` in maintainer records. The distributed `sites.json` contains only `active` and `degraded` sites. A degraded site remains searchable at lower rank; quarantined and retired sites stay outside the Skill.

## Update sequence

1. Edit the source catalog under `skills/find-ui-motion/references/sites.json` and representative deep examples under `references/examples.jsonl`.
   For the 3,000-case target, run `python3 maintainer/expand_rive_catalog.py --target-count 3000 --exclude-jsonl <latest-quarantine.jsonl> --apply`. This uses only the public listing request observed from the Marketplace page and stages records with an exact item slug, an official non-zero MP4 preview, and a public `.riv` runtime file. The later motion audit still decides active eligibility.
2. Expand non-Rive sources incrementally. Use `python3 maintainer/expand_public_sitemaps.py --prune-ineligible --exclude-jsonl <latest-quarantine.jsonl> --apply` for allowlisted official sitemaps from Motion, React Bits, Magic UI, Originkit, and Design Spells. Use `python3 maintainer/expand_public_indexes.py --output <candidate.jsonl> --exclude-jsonl <latest-quarantine.jsonl> --apply` for allowlisted exact links exposed on Aceternity UI, Animate UI, and 21st.dev public index pages. The index-page workflow never edits the active catalog; pass its independent candidate JSONL to curation only after the dynamic audit. Motion Primitives and Fancy Components browser discovery remain disabled by default because their pages were intermittently redirected to a security block on 2026-08-19; explicitly retry them only after normal browser access is stable. Never add an unreviewed host, index page, or route pattern merely because it contains many links; maintain source-level exclusions for known static component pages.
3. Run `python3 maintainer/verify_rive_assets.py --retry-rounds 2 --apply`. Require both the official MP4 and `.riv` URL to return a valid 32-byte range before counting the generated Rive record as asset-healthy. Retry transport failures at lower concurrency; never delete an item from a single timeout.
4. Run two evidence passes with `maintainer/audit_dynamic_examples.js`: use `--mode rive-media` to decode and compare official MP4 frames, and `--mode page` to observe exact non-Rive pages in Chrome. Retry only non-dynamic results with `--retry-from <first-report>`. Treat missing interaction evidence as `unverified`, not as proof that the page is static.
5. Run `maintainer/curate_examples.py` with first-pass and retry reports. For an incremental non-Rive batch, pass `--candidate-jsonl <candidate.jsonl> --preserve-current-verified`; this keeps existing verified cases unchanged and admits only audited dynamic candidates. Move duplicates, broken cases, confirmed-static media, and unverified pages into the recoverable quarantine JSONL, then inspect the audit summary before `--apply`.
6. Run `python3 maintainer/check_catalog_balance.py --max-source-share 0.80` and investigate any dominant-source failure.
7. Run `python3 skills/find-ui-motion/scripts/validate_catalog.py`.
8. Run `python3 maintainer/check_site_health.py` and `python3 maintainer/check_example_health.py`; investigate changes.
9. Shallow-check every exact item wrapper and update `last_shallow_check`. For every item admitted to a release candidate, apply the installable `references/source-health.md` gate in a browser; require a visible render target or direct observation and reject wrapper-only HTTP 200. Update `last_verified` only after interacting with the exact current item.
10. Run the repository tests.
11. Build a release manifest with `build_release_catalog.py` after immutable catalog and examples URLs are known. Keep the examples resource optional for compatibility with old single-file releases.
12. Test `check_catalog_update.py` and `update_catalog.py` against the release files in an isolated cache.
13. Publish the catalog and manifest only after review. Publication does not update user caches automatically.

## Admission gates

Require a real motion collection, one supported workflow, safe access, and an explicit capability boundary. Score relevance, uniqueness, delivery usefulness, license clarity, route stability, and freshness. Treat an unclear license as inspiration/recreate-only until a selected item is verified.

Do not silently add a remote URL, execute remote code, scrape protected implementations, or remove a site after one failed health check.

Keep the active examples index evidence-backed. A title match, sitemap route, wrapper HTTP 200, media extension, or one failed browser run is insufficient. Preserve every removed record in the dated quarantine output so a later successful audit can restore it without rediscovery.

Do not commit captured screenshots, videos, or third-party assets. The examples index stores exact public item or official-source URLs, semantic trigger hints, preview strategy, shallow-check date, optional live-verification date, rights boundary, and public discovery provenance. `source_evidence.kind=public-sitemap` proves only that an allowlisted official sitemap exposed the exact route on the recorded date. `source_evidence.kind=public-index-page` proves only that an allowlisted public page linked the exact item; it does not prove that the item renders or moves. If a publisher has no item permalink, use `source-with-category-preview`: keep the exact official source as `url`, the category locator as `preview_url`, and never mark it visually verified until the named case is observed there. Use `last_verified: null` until the current motion has been triggered or observed on the exact item.

`check_example_health.py` falls back to the system `curl` transport when the bundled Python TLS stack cannot negotiate with a source. Its `shell-reachable` state means only that the wrapper responded; it is never quick-link eligibility or deeper visual verification. Feed browser observations into `skills/find-ui-motion/scripts/classify_source_health.py` before admitting dynamic examples.

## Visual-index strategy

Use a staged `48 default / 64 maximum -> 24 live checks -> 16 captures -> 8 results` funnel for deep matching. Keep 64 as the hard text-recall ceiling until a labeled retrieval benchmark justifies a larger pool. Emit `--candidate-pool-only --json` during deep retrieval so widening the pool does not duplicate the per-motion payload; do not widen the browser or capture stages merely because local recall is cheap.

Precompute compact motion signatures during maintenance when repeated query-time capture becomes expensive. Store only the example ID, algorithm version, analysis depth, structured motion features, compressed numeric vectors when needed, and verification date. Keep source clips and keyframes transient and outside the repository.

Recompute a signature after the item URL, trigger behavior, or visible result changes. Treat a stale or metadata-only signature as text recall, not as visual deep-match evidence. Query-time analysis should refresh only missing, stale, or top-ranked candidates instead of recapturing the whole catalog.

Build a derived index from a reviewed capture manifest with `python3 skills/find-ui-motion/scripts/build_visual_index.py <manifest>`. Keep the resulting `index.npz`, metadata, OpenCLIP checkpoint, and source captures in the external cache or a release artifact, never under the installable Skill. Record the encoder model, checkpoint, source-media hash, and capture date. Rebuild only changed cases, and test retrieval with `search_visual_index.py` before publishing a compatible index.

The default LAION OpenCLIP ViT-B/32 checkpoint occupies roughly 577 MB in the local cache while a three-case, four-keyframe test index was about 24 KB. Treat checkpoint size and license as deployment concerns separate from the Skill package and derived index. Do not redistribute a model merely because the OpenCLIP library itself is permissively licensed.
