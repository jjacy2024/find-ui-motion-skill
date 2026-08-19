#!/usr/bin/env node
"use strict";

const { chromium } = require("playwright");
const { URL } = require("url");

const DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

function parseArgs(argv) {
  const args = { index: null, host: null, pathRegex: null, timeout: 20000, chrome: DEFAULT_CHROME };
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (flag === "--index") args.index = value;
    else if (flag === "--host") args.host = value;
    else if (flag === "--path-regex") args.pathRegex = value;
    else if (flag === "--timeout") args.timeout = Number(value);
    else if (flag === "--chrome") args.chrome = value;
    else throw new Error(`Unknown argument: ${flag}`);
    index += 1;
  }
  if (!args.index || !args.host || !args.pathRegex) throw new Error("--index, --host, and --path-regex are required");
  if (!Number.isFinite(args.timeout) || args.timeout < 5000 || args.timeout > 60000) throw new Error("--timeout must be 5000-60000");
  return args;
}

function redirectedAway(original, finalUrl) {
  try {
    return new URL(original).hostname !== new URL(finalUrl).hostname;
  } catch (_) {
    return true;
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const browser = await chromium.launch({ headless: true, executablePath: args.chrome });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: "no-preference" });
  const page = await context.newPage();
  let report;
  try {
    const response = await page.goto(args.index, { waitUntil: "domcontentloaded", timeout: args.timeout });
    await page.waitForTimeout(1800);
    const status = response ? response.status() : null;
    const finalUrl = page.url();
    const summary = await page.evaluate(() => ({
      title: document.title,
      body: (document.body && document.body.innerText ? document.body.innerText : "").slice(0, 1200),
      hrefs: [...document.querySelectorAll("a[href]")].map((anchor) => anchor.href),
    }));
    const blocked = /attention required|access denied|domain blocked|security verification|you have been blocked|域名拦截/i.test(`${summary.title}\n${summary.body}`);
    const pattern = new RegExp(args.pathRegex);
    const links = [...new Set(summary.hrefs.filter((href) => {
      try {
        const parsed = new URL(href);
        return parsed.protocol === "https:" && parsed.hostname === args.host && !parsed.search && !parsed.hash && pattern.test(parsed.pathname);
      } catch (_) {
        return false;
      }
    }))];
    report = {
      index_url: args.index,
      status,
      final_url: finalUrl,
      title: summary.title,
      state: blocked || redirectedAway(args.index, finalUrl) || status === 403 || status === 404 || (status !== null && status >= 500)
        ? "blocked-or-broken"
        : "reachable",
      links,
    };
  } catch (error) {
    report = { index_url: args.index, final_url: page.url(), state: "unverified", error: String(error.message || error), links: [] };
  } finally {
    await context.close();
    await browser.close();
  }
  process.stdout.write(`${JSON.stringify(report)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(2);
});
