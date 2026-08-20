# Catalog overview

Use this local-only workflow to tell the user what the bundled Catalog contains and, on request, expose its public source homepages.

## Announce once when the Skill starts

On the first `find-ui-motion` use in each task, run from the Skill directory:

```bash
python3 scripts/catalog_overview.py
```

Include the returned `announcement` once in the first substantive user-facing reply. Keep it compact and continue the user's actual motion task without waiting for a response. Do not repeat the announcement later in the same task.

The counts must come from the bundled `references/sites.json` and `references/examples.jsonl`; never hardcode or estimate them. If the local files cannot be validated, do not invent counts. State that the Catalog overview is temporarily unavailable and continue the primary task.

## Show the website list only on interest

If the user asks to view the source websites, accepts the invitation, or otherwise expresses interest, run:

```bash
python3 scripts/catalog_overview.py --list-sites --format markdown
```

Return every listed website as a clickable Markdown link to its public `homepage`. Preserve the Catalog order, and label a non-active status when present. Do not truncate a complete list, substitute category pages, or turn homepage links into case recommendations.

The website list is Catalog navigation, not a case result. It does not count toward the default eight concrete-case links. Showing the list does not authorize opening, browsing, verifying, downloading from, or submitting data to any website. Let the user manually click a link unless they separately ask the agent to visit it.
