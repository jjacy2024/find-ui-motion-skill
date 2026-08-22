# Source Evidence Preview

Use this workflow when the user asks to see real examples, when visual comparison would materially improve a discovery decision, or before implementing a selected live reference.

This workflow does not authorize searching for video-only cases. Keep `video_case_search_authorized=false` unless the user explicitly asks for video cases or explicitly approves a proposed video supplement. A generic request to see examples is not authorization.

## Keep evidence classes separate

Use exactly one label for every visual:

- `official-media`: media intentionally published by the source for this exact item;
- `live-capture`: a transient local capture of the current source page while the agent triggers the visible interaction;
- `storyboard`: two or more real source-page states such as rest, peak, and settled;
- `open-source-only`: no captured media; open the exact item page for the user;
- `local-synthesis`: an agent-created direction with no source claim.

Never attach a source site, item title, or source URL to `local-synthesis`. Never present generic shapes, reconstructed motion, or a nearby site route as evidence of an exact source item.

## Resolve examples

1. Shortlist motion directions with `scripts/search_catalog.py` before browsing, then apply the code-first source policy from [retrieval-ladder.md](retrieval-ladder.md).
2. Prefer a matching code-backed or runtime-backed item from `references/examples.jsonl`. Exclude video-only items while video search is unauthorized.
3. Read [source-health.md](source-health.md), wait for the current `settle_ms`, and verify that the named item or its exact `official-media` preview renders. A wrapper HTTP 200 or successful Range request is not visual availability.
4. If no indexed item fits, open the selected site's category route and choose one visible item whose behavior matches. Record its exact item URL; do not retain a category page as the item source.
5. When a publisher exposes no item permalink, keep the exact official source file as `url`, add the public category as `preview_url`, set `link_scope: source-with-category-preview`, and use `open-source-only`. Show both links and say that the preview is a category locator, not a direct or visually verified item link.
6. For a user-facing evidence comparison, live-verify no more than three examples unless the user asks for more. The separate visual-deep-match workflow may recall at most 64 items, live-check at most 24, and capture at most 16 for ranking.

Interpret example dates precisely: `last_shallow_check` confirms only that the exact public item wrapper was reachable at the recorded time. `last_verified` is non-null only after visible motion was observed or triggered on that item at the recorded time. Either field may order a preliminary fuzzy lead, but neither proves current availability; never call a shallow-only or historical record currently live-verified.

## Return direct links before media

For the preliminary quick pass, show about fifteen concrete item links by default and never more than twenty when explicitly requested. Do not wait for current `render_verified` or `capture_restricted` evidence; use catalog metadata, fuzzy relevance, cached health fields, and direct item scope. Reduce below fifteen only when the full fuzzy scan, plus expansion when fewer than ten candidates remain, no strong candidate exists, or the core behavior is still missing, cannot supply enough meaningful unique leads. Never pad with known broken records, duplicates, category routes, off-target items, unauthorized video-only items, or crowded near-duplicates. Keep each item to a linked title and one sentence. Mark the whole list `快速模糊初筛，尚未实时视觉复核`.

Soft-singular requests such as `帮我找一个` or `推荐一个` do not reduce this default comparison set. Put one clearly labeled recommendation first or in a separate `最推荐` block, then show the other preliminary quick links. Reduce to one only for an explicit exclusive constraint such as `只要一个，不要其他候选`, and still deliver it as a visible quick pass unless the user also explicitly says `直接深度匹配`.

When a catalog record supplies an `official-media` `preview_url`, the fuzzy pass may link it as `观看动效（未实时复核）` and keep the catalog `url` beside it as `来源页`. Live-observe the official preview before selected-case evidence or formal deep ranking. If the source page is unavailable but the exact official preview renders, say so on that verified item instead of sending the user to the empty page.

Do not use a category, search, collection, or homepage as if it were a direct case result. Put a useful non-item route under `继续探索入口`. For `source-with-category-preview`, show `查看官网分类预览` beside the exact source link and state that the user must locate the named case there. Do not create a board or static screenshot page merely to bridge the user to a source that already has a direct item URL.

Treat `target_hint` and trigger recipes as semantic hints, not stable selectors. Re-resolve the visible target from the current page.

## Paginate and deduplicate follow-ups

Treat the first evidence delivery and every follow-up as pages in one exploration session. Keep a lightweight in-task ledger containing the current query and filters, page number, shown example IDs, and shown canonical item URLs. Do not persist this ledger outside the current task.

The three-item page size below applies only to media-rich verified-evidence follow-ups. It does not replace the default fifteen fuzzy quick links or the default eight formal visual deep-match results. An unqualified `换一批` refers to the next fifteen unseen fuzzy links; an explicit request for more verified media uses the three-item evidence pagination below.

- Use at most three verified examples on page 1.
- Interpret an unqualified request such as "more", "show me more", or "再来一些" as the next page of exactly three examples, or every remaining unique match when fewer than three remain. Do not ask how many.
- When the user requests a number, paginate it in groups of three, with a final smaller page when needed. Continue without asking between pages unless an unresolved permission, access, or scope issue blocks capture.
- Before browsing or capturing each page, exclude every previously shown example ID and canonical item URL. Never refill a short page with a duplicate.
- Canonicalize an item URL by lowercasing the host, removing its fragment, normalizing a trailing slash, and dropping only known tracking parameters such as `utm_*`. Preserve query parameters that identify the example or state.
- Label each delivery with the page number, number in this page, cumulative unique count, and whether more verified candidates are known. Do not claim a complete total when discovery is still open-ended.
- If the current filters yield fewer unique verified examples than requested, return the available remainder, state that the filtered set is exhausted, and offer to broaden one constraint. Do not silently recycle earlier examples.
- Start a new page sequence when the user materially changes the motion goal or filters. Continue excluding examples already shown in the task unless the user explicitly asks to revisit them.

## Capture real behavior

Prefer evidence in this order:

1. Use an official interactive preview, GIF, Lottie, Rive, or video preview when the source intentionally exposes it and current terms allow local viewing. A video preview is allowed without video-search authorization only when it previews the same code-backed or runtime-backed case already selected; a video-only candidate still requires authorization.
2. Otherwise open the exact item in an available browser, capture a rest state, perform the visible trigger, then capture the peak or settled state. Create a 3-5 second clip when recording is available; otherwise create a storyboard with at least two real states.
3. If capture fails, inspect critical item-data responses, console errors, and the expected render target before choosing a fallback. Classify missing data or an absent settled render target as `broken` and exclude it.
4. Use `open-source-only` only when the exact item visibly exists but capture is restricted or when `source-with-category-preview` resolves the named case. Never use it for an empty or broken page.

For hover, include the pointer-away rest state and the settled hover state. For click, capture before and after. For scroll or mount, reload or use the page's replay control only when it is publicly exposed. Do not modify the page to manufacture a state.

Store captured media only in the current task output. Do not add third-party media to the Skill, GitHub catalog, or release package. A local short-lived cache is acceptable only when the URL, trigger recipe, viewport, and verification date are shown and the source remains current.

Recording a transient clip from a code-backed interactive page for visual analysis is evidence capture, not a video-case search, and does not change the authorization state.

## Apply rights and safety gates

- Do not bypass authentication, paywalls, anti-bot controls, disabled downloads, or embedding restrictions.
- Do not extract hidden page scripts or private media URLs.
- Treat a source preview as identification evidence, not permission to copy code or assets.
- If capture rights are unclear, keep the capture transient and local or fall back to `open-source-only`.
- Verify item-level code, package, asset, and license rights separately during reference rebuild.

## Build the evidence board only on request

Build a board only when the user explicitly requests side-by-side comparison, an organized page, or saved results. Do not build it during retrieval, as an intermediate status surface, or as the default delivery.

Create a JSON manifest containing only verified item URLs and locally available media, then run:

```bash
python3 scripts/build_evidence_board.py --manifest <absolute-manifest.json> --output <absolute-evidence.html>
```

The builder rejects `synthetic` evidence and source cards without real media unless the item is explicitly labeled `open-source-only`.

Each card must show:

- exact source item and link;
- evidence class and capture time;
- trigger performed;
- live verification boundary;
- motion DNA and one meaningful tradeoff;
- a reminder that preview evidence is not reuse permission.

Deliver direct source item links before asking the user to choose. When a board was explicitly requested, deliver it as an optional comparison artifact after those links. Text descriptions remain supporting metadata, not a substitute for visual evidence.
