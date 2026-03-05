#!/usr/bin/env node

/**
 * Scrape Spreadshirt-style grid pages and write output_image_urls.json.
 *
 * Usage:
 *   node scrape.js --url "https://shop.example.com/#!/?page=1"
 *   node scrape.js --url "https://shop.example.com/" --out output_image_urls.json
 *
 * Notes:
 * - Requires Playwright: npm i -D playwright
 * - The script opens a headless browser, paginates via hash routes, and
 *   collects only real image URLs (skips data:image placeholders).
 */

const fs = require("fs");
const path = require("path");

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i += 1) {
    const token = argv[i];
    if (token === "--url" || token === "-u") {
      args.url = argv[i + 1];
      i += 1;
      continue;
    }
    if (token === "--out" || token === "-o") {
      args.out = argv[i + 1];
      i += 1;
      continue;
    }
    if (token === "--help" || token === "-h") {
      args.help = true;
      continue;
    }
  }
  return args;
}

function printHelp() {
  console.log(
    [
      "Usage:",
      "  node scrape.js --url <store-url> [--out output_image_urls.json]",
      "",
      "Examples:",
      "  node scrape.js --url \"https://shop.spreadshirt.com/your-store/#!/?page=1\"",
      "  node scrape.js --url \"https://shop.spreadshirt.com/your-store/\" --out output_image_urls.json",
      "",
      "Requirements:",
      "  npm i -D playwright",
    ].join("\n")
  );
}

function normalizeName(value) {
  return value
    .toLowerCase()
    .replace(/&amp;/g, " and ")
    .replace(/&/g, " and ")
    .replace(/[’']/g, "")
    .replace(/\+/g, " plus ")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function baseName(value) {
  return value.split(/\s+-\s+/)[0].trim();
}

function toPageUrl(startUrl, pageNum) {
  if (startUrl.includes("?page=")) {
    return startUrl.replace(/\?page=\d+/, `?page=${pageNum}`);
  }
  if (startUrl.includes("#!/")) {
    if (startUrl.includes("#!/?page=")) {
      return startUrl.replace(/#!\/\?page=\d+/, `#!/?page=${pageNum}`);
    }
    return `${startUrl.replace(/#.*$/, "")}#!/?page=${pageNum}`;
  }
  return `${startUrl.replace(/\/+$/, "")}/#!/?page=${pageNum}`;
}

async function waitForGrid(page) {
  await page.waitForSelector(".sprd-product-list-item img[alt]", {
    timeout: 30000,
  });
}

async function forceLazyLoad(page) {
  await page.evaluate(async () => {
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    const max = Math.max(
      document.body.scrollHeight,
      document.documentElement.scrollHeight
    );
    const step = Math.max(400, Math.floor(window.innerHeight * 0.8));

    for (let y = 0; y <= max + step; y += step) {
      window.scrollTo(0, y);
      await sleep(120);
    }
    window.scrollTo(0, 0);
    await sleep(350);
  });
}

async function readPageCount(page) {
  const label = await page.$eval(
    ".sprd-pagination__page-counter",
    (el) => el.textContent || ""
  ).catch(() => "");

  const match = label.match(/Page\s+\d+\s+of\s+(\d+)/i);
  if (match) return Number(match[1]);

  return await page.$$eval(".sprd-pagination__page", (nodes) => {
    const nums = nodes
      .map((n) => Number((n.textContent || "").trim()))
      .filter((n) => Number.isFinite(n));
    return nums.length ? Math.max(...nums) : 1;
  });
}

async function readCurrentPageNumber(page) {
  const label = await page
    .$eval(".sprd-pagination__page-counter", (el) => el.textContent || "")
    .catch(() => "");
  const match = label.match(/Page\s+(\d+)\s+of\s+\d+/i);
  return match ? Number(match[1]) : null;
}

async function ensurePageNumber(page, startUrl, pageNum) {
  const baseNoHash = startUrl.replace(/#.*$/, "").replace(/\/+$/, "");
  const candidates = [
    `${baseNoHash}/?page=${pageNum}`,
    `${baseNoHash}/#!/?page=${pageNum}`,
  ];

  if (startUrl.includes("?page=")) {
    candidates.unshift(startUrl.replace(/\?page=\d+/, `?page=${pageNum}`));
  } else if (startUrl.includes("#!/?page=")) {
    candidates.unshift(startUrl.replace(/#!\/\?page=\d+/, `#!/?page=${pageNum}`));
  }

  for (const target of candidates) {
    await page.goto(target, {
      waitUntil: "domcontentloaded",
      timeout: 45000,
    });
    await waitForGrid(page);
    for (let i = 0; i < 30; i += 1) {
      const current = await readCurrentPageNumber(page);
      if (current === pageNum) return true;
      await page.waitForTimeout(150);
    }
  }

  // Fallback: click an explicit pagination link if present.
  const selectors = [
    `.sprd-pagination__page[href="#!/?page=${pageNum}"]`,
    `.sprd-pagination__page[href*="?page=${pageNum}"]`,
  ];
  for (const selector of selectors) {
    const link = await page.$(selector);
    if (!link) continue;
    await link.click();
    for (let i = 0; i < 30; i += 1) {
      const current = await readCurrentPageNumber(page);
      if (current === pageNum) return true;
      await page.waitForTimeout(150);
    }
  }

  return false;
}

async function collectRows(page) {
  return page.$$eval(".sprd-product-list-item", (tiles) =>
    tiles.map((tile) => {
      const img = tile.querySelector("img[alt]");
      const link = tile.querySelector(".sprd-product-list-item__link");
      return {
        name: (img?.getAttribute("alt") || "").trim(),
        url: (img?.getAttribute("src") || "").trim(),
        href: (link?.getAttribute("href") || "").trim(),
      };
    })
  );
}

async function resolveDetailImage(page, startUrl, tileHref) {
  if (!tileHref || !tileHref.startsWith("#!/")) return "";
  const base = startUrl.replace(/#.*$/, "");
  const detailUrl = `${base}${tileHref}`;

  try {
    await page.goto(detailUrl, {
      waitUntil: "domcontentloaded",
      timeout: 45000,
    });
    await page.waitForSelector("img", { timeout: 12000 });
    await forceLazyLoad(page);

    const candidates = await page.$$eval("img", (imgs) =>
      imgs
        .map((img) => (img.getAttribute("src") || "").trim())
        .filter(Boolean)
    );

    const real = candidates.find(
      (u) =>
        u.startsWith("https://image.spreadshirtmedia.com/image-server/") &&
        !u.startsWith("data:image/")
    );
    return real || "";
  } catch {
    return "";
  }
}

async function main() {
  const args = parseArgs(process.argv);
  if (args.help || !args.url) {
    printHelp();
    process.exit(args.help ? 0 : 1);
  }

  const outPath = path.resolve(args.out || "output_image_urls.json");

  let chromium;
  try {
    ({ chromium } = require("playwright"));
  } catch (err) {
    console.error("Missing dependency: playwright");
    console.error("Install it with: npm i -D playwright");
    process.exit(1);
  }

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 2000 },
  });

  const dedup = new Map();
  let pageCount = 1;
  const placeholders = [];

  try {
    await ensurePageNumber(page, args.url, 1);
    await forceLazyLoad(page);
    pageCount = await readPageCount(page);

    for (let p = 1; p <= pageCount; p += 1) {
      const ok = await ensurePageNumber(page, args.url, p);
      const actual = await readCurrentPageNumber(page);

      await forceLazyLoad(page);
      const rows = await collectRows(page);

      for (const row of rows) {
        const rawName = row.name;
        const rawUrl = row.url;
        if (!rawName) continue;

        const prettyName = baseName(rawName);
        const key = normalizeName(prettyName);
        if (!key) continue;

        if (rawUrl && !rawUrl.startsWith("data:image/")) {
          if (!dedup.has(key)) {
            dedup.set(key, { name: prettyName, URL: rawUrl });
          }
          continue;
        }

        if (!dedup.has(key)) {
          placeholders.push({ key, name: prettyName, href: row.href || "" });
        }
      }

      const pageLabel = ok ? `${p}` : `${p} (actual ${actual ?? "?"})`;
      console.log(
        `Scraped page ${pageLabel}/${pageCount} (${dedup.size} real URLs, ${rows.length} tiles)`
      );
    }

    if (placeholders.length) {
      const unresolved = [];
      let resolvedCount = 0;
      for (const item of placeholders) {
        if (dedup.has(item.key)) continue;
        const resolved = await resolveDetailImage(page, args.url, item.href);
        if (resolved) {
          dedup.set(item.key, { name: item.name, URL: resolved });
          resolvedCount += 1;
        } else {
          unresolved.push(item.name);
        }
      }
      console.log(`Resolved ${resolvedCount} placeholder-only designs`);
      if (unresolved.length) {
        console.log(
          `Could not resolve ${unresolved.length} placeholder-only designs`
        );
      }
    }
  } finally {
    await browser.close();
  }

  const output = Array.from(dedup.values()).sort((a, b) =>
    a.name.localeCompare(b.name)
  );
  fs.writeFileSync(outPath, `${JSON.stringify(output, null, 2)}\n`, "utf8");

  console.log(`Wrote ${output.length} entries to ${outPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
