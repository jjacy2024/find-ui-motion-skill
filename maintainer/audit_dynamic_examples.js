#!/usr/bin/env node
"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const { URL } = require("url");
const { chromium } = require("playwright");

const REPO_ROOT = path.resolve(__dirname, "..");
const DEFAULT_EXAMPLES = path.join(REPO_ROOT, "skills", "find-ui-motion", "references", "examples.jsonl");
const DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

function parseArgs(argv) {
  const args = {
    examples: DEFAULT_EXAMPLES,
    output: null,
    mode: null,
    workers: 6,
    timeout: 15000,
    settleMax: 2500,
    limit: null,
    sources: [],
    chrome: DEFAULT_CHROME,
    retryFrom: null,
    checkedAt: null,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (flag === "--examples") args.examples = value;
    else if (flag === "--output") args.output = value;
    else if (flag === "--mode") args.mode = value;
    else if (flag === "--workers") args.workers = Number(value);
    else if (flag === "--timeout") args.timeout = Number(value);
    else if (flag === "--settle-max") args.settleMax = Number(value);
    else if (flag === "--limit") args.limit = Number(value);
    else if (flag === "--source") args.sources.push(value);
    else if (flag === "--chrome") args.chrome = value;
    else if (flag === "--retry-from") args.retryFrom = value;
    else if (flag === "--checked-at") args.checkedAt = value;
    else throw new Error(`Unknown argument: ${flag}`);
    index += 1;
  }
  if (!args.output) throw new Error("--output is required");
  if (!["rive-media", "page"].includes(args.mode)) throw new Error("--mode must be rive-media or page");
  if (!Number.isInteger(args.workers) || args.workers < 1 || args.workers > 12) throw new Error("--workers must be 1-12");
  if (!Number.isFinite(args.timeout) || args.timeout < 5000 || args.timeout > 60000) throw new Error("--timeout must be 5000-60000");
  if (!Number.isFinite(args.settleMax) || args.settleMax < 500 || args.settleMax > 5000) throw new Error("--settle-max must be 500-5000");
  if (args.limit !== null && (!Number.isInteger(args.limit) || args.limit < 1)) throw new Error("--limit must be positive");
  if (args.checkedAt !== null && !/^\d{4}-\d{2}-\d{2}$/.test(args.checkedAt)) throw new Error("--checked-at must be YYYY-MM-DD");
  return args;
}

function readExamples(filePath) {
  return fs.readFileSync(filePath, "utf8").split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
}

function sha256(buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

function redirectAway(original, finalUrl) {
  try {
    const before = new URL(original);
    const after = new URL(finalUrl);
    const beforePath = before.pathname.replace(/\/$/, "") || "/";
    const afterPath = after.pathname.replace(/\/$/, "") || "/";
    return before.hostname !== after.hostname || (beforePath !== "/" && afterPath === "/");
  } catch (_) {
    return true;
  }
}

function isContentError(message) {
  return /error fetching data|project[^\n]*(not found|does not exist|unavailable)|failed to load resource[^\n]*(404|410)/i.test(message);
}

async function auditRiveMedia(page, record, args) {
  const mediaUrl = record.source_evidence.official_media_url;
  const started = Date.now();
  try {
    await page.setContent("<!doctype html><meta charset=utf-8><body></body>");
    const evidence = await page.evaluate(async ({ url, timeout }) => {
      const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
      const video = document.createElement("video");
      video.crossOrigin = "anonymous";
      video.muted = true;
      video.playsInline = true;
      video.preload = "auto";
      document.body.appendChild(video);
      const loaded = new Promise((resolve, reject) => {
        video.addEventListener("loadedmetadata", resolve, { once: true });
        video.addEventListener("error", () => reject(new Error(`video-error-${video.error ? video.error.code : "unknown"}`)), { once: true });
        setTimeout(() => reject(new Error("metadata-timeout")), timeout);
      });
      video.src = url;
      video.load();
      await loaded;
      if (!(video.videoWidth > 0 && video.videoHeight > 0 && Number.isFinite(video.duration) && video.duration > 0)) {
        throw new Error("invalid-video-metadata");
      }
      const canvas = document.createElement("canvas");
      canvas.width = 64;
      canvas.height = 64;
      const context = canvas.getContext("2d", { willReadFrequently: true });
      async function sample(time) {
        video.currentTime = Math.max(0, Math.min(time, Math.max(0, video.duration - 0.02)));
        await new Promise((resolve, reject) => {
          const timer = setTimeout(() => reject(new Error("seek-timeout")), Math.min(timeout, 8000));
          video.addEventListener("seeked", () => { clearTimeout(timer); resolve(); }, { once: true });
        });
        await wait(40);
        context.drawImage(video, 0, 0, 64, 64);
        return Array.from(context.getImageData(0, 0, 64, 64).data);
      }
      const sampleTimes = [
        Math.min(0.05, video.duration * 0.05),
        Math.min(video.duration - 0.02, Math.max(0.16, video.duration * 0.33)),
        Math.min(video.duration - 0.02, Math.max(0.32, video.duration * 0.72)),
      ].filter((value, index, values) => value >= 0 && (index === 0 || Math.abs(value - values[index - 1]) > 0.03));
      const samples = [];
      for (const sampleTime of sampleTimes) samples.push(await sample(sampleTime));
      let changed = 0;
      let absolute = 0;
      const pixels = samples[0].length / 4;
      for (let left = 0; left < samples.length; left += 1) {
        for (let right = left + 1; right < samples.length; right += 1) {
          let pairChanged = 0;
          let pairAbsolute = 0;
          for (let index = 0; index < samples[left].length; index += 4) {
            const delta = Math.abs(samples[left][index] - samples[right][index]) + Math.abs(samples[left][index + 1] - samples[right][index + 1]) + Math.abs(samples[left][index + 2] - samples[right][index + 2]);
            pairAbsolute += delta / 3;
            if (delta > 12) pairChanged += 1;
          }
          changed = Math.max(changed, pairChanged);
          absolute = Math.max(absolute, pairAbsolute);
        }
      }
      return {
        width: video.videoWidth,
        height: video.videoHeight,
        duration: video.duration,
        sample_times: sampleTimes,
        changed_pixel_ratio: changed / pixels,
        mean_absolute_difference: absolute / pixels,
      };
    }, { url: mediaUrl, timeout: args.timeout });
    const dynamic = evidence.changed_pixel_ratio >= 0.001 || evidence.mean_absolute_difference >= 0.25;
    return {
      id: record.id,
      site_id: record.site_id,
      audited_url: mediaUrl,
      state: dynamic ? "dynamic" : "static",
      evidence_kind: "official-media-frame-difference",
      evidence,
      elapsed_ms: Date.now() - started,
    };
  } catch (error) {
    return {
      id: record.id,
      site_id: record.site_id,
      audited_url: mediaUrl,
      state: /video-error|invalid-video-metadata/.test(String(error.message)) ? "broken" : "unverified",
      evidence_kind: "official-media-frame-difference",
      error: String(error.message || error),
      elapsed_ms: Date.now() - started,
    };
  }
}

async function chooseTarget(page) {
  const handle = await page.evaluateHandle(() => {
    const visible = (element) => {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return rect.width >= 120 && rect.height >= 80 && style.visibility !== "hidden" && style.display !== "none" && Number(style.opacity || 1) > 0;
    };
    const explicit = [...document.querySelectorAll("video,canvas,iframe,lottie-player,dotlottie-player,dotlottie-wc,rive-player")]
      .filter(visible)
      .map((element) => ({ element, rect: element.getBoundingClientRect() }))
      .sort((left, right) => right.rect.width * right.rect.height - left.rect.width * left.rect.height);
    if (explicit.length) return { element: explicit[0].element, kind: explicit[0].element.tagName.toLowerCase(), confidence: "explicit" };
    const candidates = [...document.querySelectorAll("[id*='stage'],[class*='preview'],[class*='demo'],[class*='example'],[class*='presentation'],[class*='playground'],main section,main [class*='component'],main,body > div")]
      .filter(visible)
      .map((element) => {
        const rect = element.getBoundingClientRect();
        const text = `${element.id} ${element.className}`.toLowerCase();
        const semantic = /preview|demo|example|component|stage|playground|presentation/.test(text) ? 4 : element.tagName === "MAIN" ? 1 : 0;
        const viewportArea = Math.min(rect.width, innerWidth) * Math.min(rect.height, innerHeight * 1.5);
        return { element, rect, score: semantic * 1e8 + viewportArea };
      })
      .sort((left, right) => right.score - left.score);
    if (!candidates.length) return { element: null, kind: null, confidence: "none" };
    return { element: candidates[0].element, kind: candidates[0].element.tagName.toLowerCase(), confidence: candidates[0].score >= 4e8 ? "semantic" : "fallback" };
  });
  const payload = await handle.getProperty("element");
  const element = payload.asElement();
  const kind = await (await handle.getProperty("kind")).jsonValue();
  const confidence = await (await handle.getProperty("confidence")).jsonValue();
  await handle.dispose();
  return { element, kind, confidence };
}

async function targetSnapshot(page, element) {
  if (!element) return null;
  try {
    return await element.screenshot({ animations: "allow", timeout: 6000 });
  } catch (_) {}
  try {
    const box = await element.boundingBox();
    if (!box || box.width < 1 || box.height < 1) return null;
    return await page.screenshot({
      animations: "allow",
      clip: { x: box.x, y: box.y, width: box.width, height: box.height },
      timeout: 6000,
    });
  } catch (_) { return null; }
}

async function targetSignals(element) {
  if (!element) return { running_animations: 0, videos: [] };
  try {
    return await element.evaluate((root) => ({
      running_animations: root.getAnimations({ subtree: true }).filter((animation) => animation.playState === "running").length,
      videos: [...root.querySelectorAll("video")].map((video) => ({
        current_time: video.currentTime,
        duration: Number.isFinite(video.duration) ? video.duration : null,
        width: video.videoWidth,
        height: video.videoHeight,
        paused: video.paused,
        ready_state: video.readyState,
      })),
    }));
  } catch (_) {
    return { running_animations: 0, videos: [] };
  }
}

async function auditPage(page, record, args) {
  const auditUrl = record.link_scope === "source-with-category-preview" && record.preview_url ? record.preview_url : record.url;
  const started = Date.now();
  const consoleErrors = [];
  const criticalResponses = [];
  const onConsole = (message) => { if (message.type() === "error") consoleErrors.push(message.text().slice(0, 500)); };
  const onResponse = (response) => {
    const status = response.status();
    if (status === 404 || status === 410 || status >= 500) criticalResponses.push({ url: response.url(), status });
  };
  page.on("console", onConsole);
  page.on("response", onResponse);
  try {
    let response = null;
    let navigationWarning = null;
    try {
      response = await page.goto(auditUrl, { waitUntil: "domcontentloaded", timeout: args.timeout });
    } catch (error) {
      const message = String(error.message || error);
      const timedOut = /Timeout .* exceeded|TimeoutError/i.test(message);
      const partialPage = timedOut ? await page.evaluate(() => ({
        ready_state: document.readyState,
        body_text_length: (document.body && document.body.innerText ? document.body.innerText.trim().length : 0),
        media_count: document.querySelectorAll("video,canvas,iframe,lottie-player,dotlottie-player,dotlottie-wc,rive-player").length,
      })).catch(() => null) : null;
      const finalUrl = page.url();
      const exactPageStillOpen = !redirectAway(auditUrl, finalUrl);
      const hasInspectableContent = partialPage && (partialPage.body_text_length >= 80 || partialPage.media_count > 0);
      if (!timedOut || !exactPageStillOpen || !hasInspectableContent) throw error;
      navigationWarning = {
        kind: "domcontentloaded-timeout-with-inspectable-content",
        message: message.slice(0, 500),
        ...partialPage,
      };
    }
    const outerStatus = response ? response.status() : null;
    const finalUrl = page.url();
    const redirected = redirectAway(auditUrl, finalUrl);
    const settleMs = Math.min(args.settleMax, Math.max(500, Number(record.trigger && record.trigger.settle_ms) || 1000));
    await page.waitForTimeout(settleMs);
    const { element, kind, confidence } = await chooseTarget(page);
    if (!element || redirected || outerStatus === 404 || outerStatus === 410 || (outerStatus !== null && outerStatus >= 500) || consoleErrors.some(isContentError)) {
      if (element) await element.dispose();
      return {
        id: record.id, site_id: record.site_id, audited_url: auditUrl,
        state: "broken", evidence_kind: "browser-page-motion",
        outer_status: outerStatus, final_url: finalUrl, redirected_away: redirected,
        navigation_warning: navigationWarning,
        target: element ? { kind, confidence } : null,
        critical_responses: criticalResponses.slice(0, 20), console_errors: consoleErrors.filter(isContentError).slice(0, 20),
        elapsed_ms: Date.now() - started,
      };
    }
    const box = await element.boundingBox();
    const frames = [];
    const first = await targetSnapshot(page, element);
    if (first) frames.push(sha256(first));
    const signalsBefore = await targetSignals(element);
    await page.waitForTimeout(800);
    const second = await targetSnapshot(page, element);
    if (second) frames.push(sha256(second));
    if (new Set(frames).size < 2 && record.trigger && record.trigger.kind === "click") {
      const previewControl = page.locator("article button,article [role='button']").first();
      if (await previewControl.count()) {
        try {
          await previewControl.click({ timeout: 2500 });
          await page.waitForTimeout(120);
          const activated = await targetSnapshot(page, element);
          if (activated) frames.push(sha256(activated));
          await page.waitForTimeout(650);
          const activatedSettled = await targetSnapshot(page, element);
          if (activatedSettled) frames.push(sha256(activatedSettled));
        } catch (_) {}
      }
    }
    if (new Set(frames).size < 2 && box) {
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.waitForTimeout(120);
      const hovered = await targetSnapshot(page, element);
      if (hovered) frames.push(sha256(hovered));
      await page.waitForTimeout(650);
      const hoverSettled = await targetSnapshot(page, element);
      if (hoverSettled) frames.push(sha256(hoverSettled));
    }
    if (new Set(frames).size < 2) {
      const replay = page.locator("button,a,[role='button']").filter({ hasText: /replay|restart|play again|reset/i }).first();
      if (await replay.count()) {
        try {
          await replay.click({ timeout: 2500 });
          await page.waitForTimeout(120);
          const replayed = await targetSnapshot(page, element);
          if (replayed) frames.push(sha256(replayed));
          await page.waitForTimeout(650);
          const replaySettled = await targetSnapshot(page, element);
          if (replaySettled) frames.push(sha256(replaySettled));
        } catch (_) {}
      }
    }
    if (new Set(frames).size < 2) {
      const button = await element.$("button:not([disabled]),[role='button']");
      if (button) {
        try {
          const label = await button.evaluate((node) => `${node.getAttribute("aria-label") || ""} ${node.textContent || ""}`.toLowerCase());
          if (!/copy|install|github|menu|navigation|code/.test(label)) {
            await button.click({ timeout: 2500 });
            await page.waitForTimeout(500);
            const clicked = await targetSnapshot(page, element);
            if (clicked) frames.push(sha256(clicked));
          }
        } catch (_) {}
        await button.dispose();
      }
    }
    if (new Set(frames).size < 2) {
      await page.mouse.wheel(0, 500);
      await page.waitForTimeout(500);
      const scrolled = await targetSnapshot(page, element);
      if (scrolled) frames.push(sha256(scrolled));
    }
    const signalsAfter = await targetSignals(element);
    await element.dispose();
    const videoAdvanced = signalsBefore.videos.some((before, index) => {
      const after = signalsAfter.videos[index];
      return after && before.width > 0 && before.height > 0 && after.current_time > before.current_time + 0.05;
    });
    const frameChanged = new Set(frames).size >= 2;
    const cssAnimated = Math.max(signalsBefore.running_animations, signalsAfter.running_animations) > 0;
    const dynamic = frameChanged || videoAdvanced || cssAnimated;
    return {
      id: record.id, site_id: record.site_id, audited_url: auditUrl,
      state: dynamic ? "dynamic" : "unverified", evidence_kind: "browser-page-motion",
      outer_status: outerStatus, final_url: finalUrl, redirected_away: false,
      navigation_warning: navigationWarning,
      target: { kind, confidence, width: box ? box.width : 0, height: box ? box.height : 0 },
      unique_frame_hashes: new Set(frames).size, captured_frames: frames.length,
      running_animations: Math.max(signalsBefore.running_animations, signalsAfter.running_animations),
      video_advanced: videoAdvanced,
      no_motion_observed: !dynamic,
      critical_responses: criticalResponses.slice(0, 20),
      elapsed_ms: Date.now() - started,
    };
  } catch (error) {
    return {
      id: record.id, site_id: record.site_id, audited_url: auditUrl,
      state: "unverified", evidence_kind: "browser-page-motion",
      error: String(error.message || error), console_errors: consoleErrors.filter(isContentError).slice(0, 20),
      elapsed_ms: Date.now() - started,
    };
  } finally {
    page.off("console", onConsole);
    page.off("response", onResponse);
  }
}

async function atomicWrite(filePath, payload) {
  fs.mkdirSync(path.dirname(path.resolve(filePath)), { recursive: true });
  const temp = `${filePath}.tmp-${process.pid}`;
  fs.writeFileSync(temp, payload);
  fs.renameSync(temp, filePath);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  let records = readExamples(args.examples);
  records = records.filter((record) => args.mode === "rive-media"
    ? record.site_id === "rive-community" && record.source_evidence && record.source_evidence.kind === "public-list-api"
    : !(record.source_evidence && record.source_evidence.kind === "public-list-api"));
  if (args.sources.length) records = records.filter((record) => args.sources.includes(record.site_id));
  if (args.retryFrom) {
    const prior = JSON.parse(fs.readFileSync(args.retryFrom, "utf8"));
    const retryIds = new Set((prior.results || []).filter((result) => result.state !== "dynamic").map((result) => result.id));
    records = records.filter((record) => retryIds.has(record.id));
  }
  if (args.limit !== null) records = records.slice(0, args.limit);

  const browser = await chromium.launch({ headless: true, executablePath: args.chrome });
  const results = new Array(records.length);
  let cursor = 0;
  let completed = 0;
  const workers = Array.from({ length: Math.min(args.workers, Math.max(1, records.length)) }, async () => {
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: "no-preference" });
    const page = await context.newPage();
    page.setDefaultTimeout(args.timeout);
    while (true) {
      const index = cursor;
      cursor += 1;
      if (index >= records.length) break;
      results[index] = args.mode === "rive-media"
        ? await auditRiveMedia(page, records[index], args)
        : await auditPage(page, records[index], args);
      completed += 1;
      if (completed % 100 === 0 || completed === records.length) {
        process.stderr.write(`[${args.mode}] ${completed}/${records.length}\n`);
      }
    }
    await context.close();
  });
  await Promise.all(workers);
  await browser.close();
  const states = {};
  const sources = {};
  for (const result of results) {
    states[result.state] = (states[result.state] || 0) + 1;
    sources[result.site_id] = sources[result.site_id] || {};
    sources[result.site_id][result.state] = (sources[result.site_id][result.state] || 0) + 1;
  }
  const report = {
    schema_version: 1,
    mode: args.mode,
    checked_at: args.checkedAt ? `${args.checkedAt}T00:00:00.000Z` : new Date().toISOString(),
    checked: results.length,
    states,
    sources,
    results,
    note: args.mode === "rive-media"
      ? "Dynamic requires decoded official MP4 frame change; metadata or HTTP alone is insufficient."
      : "Dynamic requires a current visible target with frame change, video progress, or a running target-local CSS animation.",
  };
  await atomicWrite(args.output, `${JSON.stringify(report, null, 2)}\n`);
  process.stdout.write(`${JSON.stringify({ checked: report.checked, states, sources, output: path.resolve(args.output) }, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(2);
});
