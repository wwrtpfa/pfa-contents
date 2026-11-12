#!/usr/bin/env node
/** Attach to an existing Chromium CDP session and upload one archive package. */

import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";

const UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload";

function arg(name, fallback = undefined) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : fallback;
}

function hasFlag(name) {
  return process.argv.includes(name);
}

function loadPlaywright() {
  const candidates = [];
  if (process.env.PLAYWRIGHT_NODE_PATH) candidates.push(process.env.PLAYWRIGHT_NODE_PATH);
  candidates.push("/Users/pengfanao/.npm/_npx/9833c18b2d85bc59/node_modules");
  for (const candidate of candidates) {
    const packagePath = path.basename(candidate) === "playwright"
      ? candidate
      : path.join(candidate, "playwright");
    try {
      return createRequire(path.join(packagePath, "package.json"))(packagePath);
    } catch {
      // Try the next known installation.
    }
  }
  try {
    return createRequire(import.meta.url)("playwright");
  } catch {
    throw new Error("找不到 Playwright。设置 PLAYWRIGHT_NODE_PATH 指向包含 playwright 的 node_modules。 ");
  }
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeJson(file, value) {
  const temporary = `${file}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  fs.renameSync(temporary, file);
}

function archiveFiles(archiveDir) {
  const metadata = readJson(path.join(archiveDir, "metadata.json"));
  const video = path.join(archiveDir, metadata.video);
  const cover = path.join(archiveDir, metadata.cover);
  const caption = metadata.caption || fs.readFileSync(path.join(archiveDir, "caption.md"), "utf8");
  for (const file of [video, cover]) {
    if (!fs.statSync(file).isFile()) throw new Error(`归档文件不存在: ${file}`);
  }
  return { metadata, video, cover, caption };
}

function updateState(archiveDir, patch) {
  const file = path.join(archiveDir, "upload-state.json");
  const current = fs.existsSync(file) ? readJson(file) : {};
  writeJson(file, { ...current, ...patch });
}

function allPages(browser) {
  return browser.contexts().flatMap((context) => context.pages());
}

async function findExistingDouyinPage(browser) {
  const pages = allPages(browser);
  const page = pages.find((candidate) => /douyin\.com/i.test(candidate.url()));
  if (!page) {
    const urls = pages.map((candidate) => candidate.url()).filter(Boolean);
    throw new Error(`当前 CDP 会话没有已打开的抖音页面。现有页面: ${urls.join(" | ") || "无"}`);
  }
  return page;
}

async function visibleFileInputs(page) {
  const locator = page.locator('input[type="file"]');
  const count = await locator.count();
  const result = [];
  for (let index = 0; index < count; index += 1) {
    const item = locator.nth(index);
    // File inputs are often intentionally hidden behind a styled upload button;
    // Playwright can still set their files without a screenshot or a click.
    result.push({ item, accept: (await item.getAttribute("accept")) || "" });
  }
  return result;
}

function pickFileInput(inputs, kind) {
  const expected = kind === "video" ? /video|mp4|mov/i : /image|png|jpe?g|webp/i;
  return inputs.find(({ accept }) => expected.test(accept)) || (kind === "video" ? inputs[0] : undefined);
}

async function fillCaption(page, title, caption, tags) {
  const hashtagLine = tags.length
    ? `\n\n${tags.map((tag) => (tag.startsWith("#") ? tag : `#${tag}`)).join(" ")}`
    : "";
  const candidates = [
    page.locator('textarea[placeholder*="描述"]').first(),
    page.locator('textarea[placeholder*="作品"]').first(),
    page.locator("textarea").first(),
    page.locator('[contenteditable="true"]').first(),
  ];
  for (const candidate of candidates) {
    if (await candidate.count() && await candidate.isVisible().catch(() => false)) {
      await candidate.fill(`${title}\n${caption}${hashtagLine}`);
      return true;
    }
  }
  return false;
}

async function clickPublish(page) {
  const buttons = page.getByRole("button", { name: /发布|发表/ });
  const count = await buttons.count();
  for (let index = count - 1; index >= 0; index -= 1) {
    const button = buttons.nth(index);
    if (await button.isVisible().catch(() => false) && await button.isEnabled().catch(() => false)) {
      await button.click();
      return true;
    }
  }
  return false;
}

async function main() {
  const archiveDir = path.resolve(arg("--archive-dir", ""));
  if (!archiveDir || !fs.existsSync(archiveDir)) throw new Error("需要 --archive-dir 指向已创建的归档目录");
  const mode = arg("--mode", "chrome-cdp");
  if (!new Set(["chrome-cdp", "douyin-app-cdp"]).has(mode)) throw new Error(`不支持的上传模式: ${mode}`);
  const { metadata, video, cover, caption } = archiveFiles(archiveDir);
  const title = arg("--title", metadata.title || "");
  const publish = hasFlag("--publish");
  const cdpUrl = arg("--cdp-url", mode === "chrome-cdp" ? process.env.DOUYIN_CHROME_CDP_URL : process.env.DOUYIN_APP_CDP_URL);
  const statePatch = {
    status: cdpUrl ? "running" : "failed",
    mode,
    cdp_url: cdpUrl ? cdpUrl.replace(/\/\/.+@/, "//***@") : null,
    started_at: new Date().toISOString(),
    error: null,
  };
  updateState(archiveDir, statePatch);
  if (!cdpUrl) {
    const error = `没有 CDP 地址。设置 ${mode === "chrome-cdp" ? "DOUYIN_CHROME_CDP_URL" : "DOUYIN_APP_CDP_URL"}，脚本不会启动新窗口。`;
    updateState(archiveDir, { ...statePatch, status: "failed", finished_at: new Date().toISOString(), error });
    throw new Error(error);
  }
  if (hasFlag("--dry-run")) {
    console.log(JSON.stringify({ mode, cdp_url: statePatch.cdp_url, archive_dir: archiveDir, video, cover }, null, 2));
    updateState(archiveDir, { ...statePatch, status: "dry-run", finished_at: new Date().toISOString() });
    return;
  }

  let browser;
  try {
    const { chromium } = loadPlaywright();
    browser = await chromium.connectOverCDP(cdpUrl);
    const page = await findExistingDouyinPage(browser);
    if (!/creator\.douyin\.com/i.test(page.url())) await page.goto(UPLOAD_URL, { waitUntil: "domcontentloaded" });
    const videoInput = pickFileInput(await visibleFileInputs(page), "video");
    if (!videoInput) throw new Error("找不到可见的视频文件输入框；页面结构可能已变化。");
    await videoInput.item.setInputFiles(video);
    await page.waitForTimeout(1500);
    let imageInput = pickFileInput(await visibleFileInputs(page), "image");
    if (!imageInput) {
      const coverButtons = page.getByRole("button", { name: /封面|更换封面|上传封面/ });
      for (let index = 0; index < await coverButtons.count(); index += 1) {
        const button = coverButtons.nth(index);
        if (await button.isVisible().catch(() => false)) {
          await button.click();
          await page.waitForTimeout(300);
          imageInput = pickFileInput(await visibleFileInputs(page), "image");
          if (imageInput) break;
        }
      }
    }
    if (!imageInput) throw new Error("视频已选择，但找不到封面图片输入框；未提交发布。");
    await imageInput.item.setInputFiles(cover);
    const filled = await fillCaption(page, title, caption, metadata.tags || []);
    if (!filled) throw new Error("找不到可见的作品描述输入框；未提交发布。");
    await page.waitForTimeout(2500);
    if (publish) {
      const published = await clickPublish(page);
      if (!published) throw new Error("找不到可用的发布按钮；未提交发布。");
      await page.waitForTimeout(2500);
    }
    const bodyText = await page.locator("body").innerText().catch(() => "");
    const success = /上传成功|上传完成|发布成功|审核中|已发布|草稿/.test(bodyText);
    const result = {
      status: publish ? (success ? "submitted" : "submitted_unverified") : (success ? "draft_ready" : "draft_unverified"),
      page_url: page.url(),
      finished_at: new Date().toISOString(),
      success_text_found: success,
      publish_clicked: publish,
    };
    updateState(archiveDir, result);
    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    const result = { status: "failed", finished_at: new Date().toISOString(), error: String(error?.stack || error) };
    updateState(archiveDir, result);
    throw error;
  }
  // Do not call browser.close(): this is an attached user session, not a process we launched.
}

main().catch((error) => {
  console.error(`douyin upload failed: ${error.message || error}`);
  process.exitCode = 1;
});
