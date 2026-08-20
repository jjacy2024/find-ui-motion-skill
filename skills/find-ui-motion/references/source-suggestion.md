# New source suggestion

Use this workflow only after a bounded external supplement produces a genuinely strong source that is absent from the current Catalog. The purpose is to invite a minimal, user-approved maintainer review, not to collect browsing context or automatically expand the Catalog.

## Apply every eligibility gate

Offer a suggestion only when all conditions are true:

- the normalized source domain is absent from the current `references/sites.json`;
- the case is a concrete, stable item page rather than a homepage, category, collection, or search page;
- semantic match quality is `exact` and evidence confidence is `high`;
- the current item is `render_verified` through live inspection;
- the item is `code-backed` or `runtime-backed`, not a video-only case;
- the same domain has not already been suggested in the current task.

Run the deterministic check from the Skill directory:

```bash
python3 scripts/source_suggestion.py \
  --site-name "<public site name>" \
  --item-url "<verified concrete item URL>" \
  --match-quality exact \
  --confidence high \
  --source-health render_verified \
  --support-kind code-backed \
  --concrete-item
```

The item URL is local evaluation input only. Never include it in the suggestion payload.

## Ask before generating anything

When the script returns `eligible=true`, show this exact message once for that domain:

> 发现一个尚未收录的高质量动效来源 example.com。是否生成来源推荐，交给 find-ui-motion Catalog 维护者审核？审核通过后会加入下一个版本的内置清单中

Replace only `example.com` with the normalized public domain. Do not interrupt the requested case results to ask; append the invitation after the relevant result or final ranked list. Stay silent when any gate fails.

## Keep the payload to one field

After the user agrees, show the complete proposed payload before opening a handoff channel. It contains exactly one field:

- `网站名称与域名`: `<public site name> — <normalized domain>`

Do not submit or encode the case URL, case title, motion details, technical stack, license, verification date, Skill or Catalog version, user prompt, identity, browsing history, cookies, screenshots, caches, or local paths. Do not add hidden analytics or tracking parameters.

## Handoff without automatic submission

- Prefer the prefilled GitHub Issue URL returned by the script. Opening it does not create an Issue; the user performs the final GitHub submission.
- Generate the optional `mailto:` fallback only when a maintainer email address is explicitly configured. It contains the same single field and nothing else.
- Never create an Issue, send email, or perform another external write merely because the user agreed to generate the recommendation.
- Direct creation is allowed only when the user explicitly asks the agent to submit it after seeing the one-field payload and an authenticated GitHub tool is available. Do not treat prior search, browsing, or recommendation authorization as submission authorization.
- Acceptance into a later Catalog version is a maintainer decision, not a promise. The user-facing message may say it will be added only after review passes.
