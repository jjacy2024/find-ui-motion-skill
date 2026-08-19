# Source Evidence Preview

Use this workflow when the user asks to see real examples, when visual comparison would materially improve a discovery decision, or before implementing a selected live reference.

## Keep evidence classes separate

Use exactly one label for every visual:

- `official-media`: media intentionally published by the source for this exact item;
- `live-capture`: a transient local capture of the current source page while the agent triggers the visible interaction;
- `storyboard`: two or more real source-page states such as rest, peak, and settled;
- `open-source-only`: no captured media; open the exact item page for the user;
- `local-synthesis`: an agent-created direction with no source claim.

Never attach a source site, item title, or source URL to `local-synthesis`. Never present generic shapes, reconstructed motion, or a nearby site route as evidence of an exact source item.

## Resolve examples

1. Shortlist motion directions with `scripts/search_catalog.py` before browsing.
2. Prefer a matching item from `references/examples.jsonl`.
3. If no indexed item fits, open the selected site's category route and choose one visible item whose behavior matches. Record its exact item URL; do not retain a category page as the item source.
4. When a publisher exposes no item permalink, keep the exact official source file as `url`, add the public category as `preview_url`, set `link_scope: source-with-category-preview`, and use `open-source-only`. Show both links and say that the preview is a category locator, not a direct or visually verified item link.
5. For a user-facing evidence comparison, live-verify no more than three examples unless the user asks for more. The separate visual-deep-match workflow may inspect a bounded 12-20-item candidate pool for ranking.

Interpret example dates precisely: `last_shallow_check` confirms only that the exact public item URL remained reachable; `last_verified` is non-null only after the current visible motion was observed or triggered on that item. Never call a shallow-only record live-verified.

## Return direct links before media

For the quick pass, show exactly eight eligible concrete item links by default and never more than ten when explicitly requested. Reduce below eight only when fewer unique, relevant, accessible item cases satisfy the current filters; return every eligible remainder and state the shortfall reason. Never pad with duplicates, category routes, inaccessible items, or weak matches. Keep each item to a linked title and one sentence. Mark links that have not yet been visually reviewed as `快速初筛`.

Do not use a category, search, collection, or homepage as if it were a direct case result. Put a useful non-item route under `继续探索入口`. For `source-with-category-preview`, show `查看官网分类预览` beside the exact source link and state that the user must locate the named case there. Do not create a board or static screenshot page merely to bridge the user to a source that already has a direct item URL.

Treat `target_hint` and trigger recipes as semantic hints, not stable selectors. Re-resolve the visible target from the current page.

## Paginate and deduplicate follow-ups

Treat the first evidence delivery and every follow-up as pages in one exploration session. Keep a lightweight in-task ledger containing the current query and filters, page number, shown example IDs, and shown canonical item URLs. Do not persist this ledger outside the current task.

The three-item page size below applies only to media-rich verified-evidence follow-ups. It does not replace the default eight direct case links in either the quick pass or the visual deep-match result list.

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

1. Use an official GIF, video, Lottie, Rive, or official interactive preview when the source intentionally exposes it and current terms allow local viewing.
2. Otherwise open the exact item in an available browser, capture a rest state, perform the visible trigger, then capture the peak or settled state. Create a 3-5 second clip when recording is available; otherwise create a storyboard with at least two real states.
3. If capture is blocked, restricted, or misleading, use `open-source-only` and put the exact live page in front of the user.

For hover, include the pointer-away rest state and the settled hover state. For click, capture before and after. For scroll or mount, reload or use the page's replay control only when it is publicly exposed. Do not modify the page to manufacture a state.

Store captured media only in the current task output. Do not add third-party media to the Skill, GitHub catalog, or release package. A local short-lived cache is acceptable only when the URL, trigger recipe, viewport, and verification date are shown and the source remains current.

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
