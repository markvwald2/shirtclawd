function resolveAppPath(path) {
  return new URL(`../${path}`, window.location.href).toString();
}

async function loadUsageEvents() {
  const response = await fetch(resolveAppPath("data/ai_usage.jsonl"), { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load usage log: ${response.status}`);
  }
  const text = await response.text();
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

async function loadPostIndex() {
  const response = await fetch(resolveAppPath("output/post_index.json"), { cache: "no-store" });
  if (!response.ok) {
    return { files: [] };
  }
  return response.json();
}

async function loadApprovalQueue() {
  const response = await fetch(resolveAppPath("data/x_approval_queue.json"), { cache: "no-store" });
  if (!response.ok) {
    return { approved_posts: [] };
  }
  return response.json();
}

async function loadPostBatch(path) {
  const response = await fetch(resolveAppPath(path), { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load post batch: ${response.status}`);
  }
  return response.json();
}

function formatNumber(value) {
  return new Intl.NumberFormat("en-US").format(value || 0);
}

function formatCurrency(value) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
  }).format(value);
}

function renderCards(events) {
  const summary = {
    requests: events.length,
    tokens: events.reduce((sum, event) => sum + (event.total_tokens || 0), 0),
    fallbacks: events.filter((event) => event.status === "fallback").length,
    avgLatency: events.length
      ? Math.round(events.reduce((sum, event) => sum + (event.latency_ms || 0), 0) / events.length)
      : 0,
    cost: events.reduce((sum, event) => sum + (event.estimated_cost_usd || 0), 0),
  };

  const cards = [
    ["AI Requests", formatNumber(summary.requests)],
    ["Total Tokens", formatNumber(summary.tokens)],
    ["Fallbacks", formatNumber(summary.fallbacks)],
    ["Avg Latency", `${formatNumber(summary.avgLatency)} ms`],
    ["Estimated Cost", formatCurrency(summary.cost)],
  ];

  document.getElementById("summary-cards").innerHTML = cards
    .map(
      ([label, value]) => `
        <article class="card">
          <div class="card-label">${label}</div>
          <div class="card-value">${value}</div>
        </article>
      `
    )
    .join("");
}

function renderPostFileOptions(postIndex) {
  const select = document.getElementById("post-file-select");
  const files = postIndex.files || [];
  if (!files.length) {
    select.innerHTML = '<option value="">No batches yet</option>';
    select.disabled = true;
    document.getElementById("post-preview-grid").innerHTML =
      '<p class="empty">No generated post batches found yet. Run the bot to populate previews.</p>';
    return null;
  }

  select.disabled = false;
  select.innerHTML = files
    .map(
      (file) =>
        `<option value="${file.path}">${file.filename} · ${file.platform} · ${file.post_count} posts</option>`
    )
    .join("");
  return files[0].path;
}

function renderPostPreview(posts, filePath, approvalQueue) {
  const grid = document.getElementById("post-preview-grid");
  if (!posts.length) {
    grid.innerHTML = '<p class="empty">This batch has no posts.</p>';
    return;
  }

  const approved = new Set(
    (approvalQueue.approved_posts || [])
      .filter((item) => item.source_file === filePath)
      .map((item) => item.shirt_id)
  );

  grid.innerHTML = posts
    .map((post) => renderPlatformPreview(post, approved.has(post.shirt_id)))
    .join("");
}

function renderPlatformPreview(post, isApproved) {
  const platform = (post.platform || "default").toLowerCase();
  const meta = buildMetaPills(post, platform, isApproved);

  if (platform === "instagram" || platform === "reels" || platform === "tiktok") {
    const captionPreview = buildInstagramCaptionPreview(post);
    const platformLabel = platform === "reels" ? "Reels draft preview" : platform === "tiktok" ? "TikTok draft preview" : "Sponsored draft preview";
    return `
      <article class="post-card post-card-instagram">
        ${meta}
        <div class="platform-shell instagram-shell">
          <div class="instagram-topbar">
            <div class="instagram-avatar">TS</div>
            <div>
              <div class="instagram-handle">thirdstringshirts</div>
              <div class="instagram-label">${platformLabel}</div>
            </div>
          </div>
          <div class="instagram-image-wrap">
            <img class="platform-image" src="${post.image_url || ""}" alt="${post.alt_text || ""}">
          </div>
          <div class="instagram-actions">
            <span>♡</span>
            <span>✦</span>
            <span>➤</span>
          </div>
          <div class="instagram-copy">
            <div class="instagram-caption"><span class="platform-author">thirdstringshirts</span> ${captionPreview.html}</div>
            ${captionPreview.truncated ? '<button class="instagram-more" type="button" disabled>more</button>' : ""}
          </div>
          <div class="instagram-footer">
            <div class="instagram-meta-line">${buildShortFormMetaLine(platform)}</div>
          </div>
        </div>
      </article>
    `;
  }

  if (platform === "x" || platform === "bluesky") {
    const tweetPreview = buildXTweetPreview(post, platform);
    const handle = platform === "bluesky" ? "@thirdstringshirts.bsky.social" : "@3rdStringShirts";
    return `
      <article class="post-card post-card-x">
        ${meta}
        <div class="platform-shell x-shell">
          <div class="x-topbar">
            <div class="x-avatar">TS</div>
            <div class="x-identity">
              <div class="x-name-row">
                <strong>Third String Shirts</strong>
                <span class="x-handle">${handle}</span>
              </div>
              <div class="x-headline">${post.headline || ""}</div>
            </div>
          </div>
          <div class="x-text">${tweetPreview.text}</div>
          ${
            post.url
              ? `
                <div class="x-link-card">
                  <div class="x-link-domain">thirdstringshirts.myspreadshop.com</div>
                  <div class="x-link-title">${post.title || "Product link"}</div>
                </div>
              `
              : ""
          }
          ${
            post.image_url
              ? `<div class="x-media-wrap"><img class="platform-image" src="${post.image_url}" alt="${post.alt_text || ""}"></div>`
              : ""
          }
          <div class="x-footer">
            <span>${tweetPreview.characters}/${tweetPreview.limit}</span>
          </div>
        </div>
      </article>
    `;
  }

  return `
    <article class="post-card">
      ${meta}
      <div class="platform-shell">
        <h3>${post.title || "Untitled"}</h3>
        <p class="post-headline">${post.headline || ""}</p>
        <div class="post-caption">${post.caption || ""}</div>
        <div class="post-footer">
          <span>${post.theme || ""}</span>
          <a class="post-link" href="${post.url || "#"}" target="_blank" rel="noreferrer">Product link</a>
        </div>
      </div>
    </article>
  `;
}

function buildInstagramCaptionPreview(post) {
  const caption = String(post.caption || "");
  const sanitized = caption
    .replace(/https?:\/\/\S+/g, "")
    .replace(/\s+/g, " ")
    .trim();
  const limit = 220;
  if (sanitized.length <= limit) {
    return { html: sanitized, truncated: false };
  }
  const shortened = sanitized.slice(0, limit).trimEnd();
  const safeBreak = Math.max(shortened.lastIndexOf(" "), Math.floor(limit * 0.7));
  return {
    html: `${shortened.slice(0, safeBreak).trimEnd()}…`,
    truncated: true,
  };
}

function buildXTweetPreview(post, platform = "x") {
  const caption = String(post.caption || "");
  const normalized = caption
    .replace(/https?:\/\/\S+/g, "")
    .replace(/#@/g, "#")
    .replace(/\s+/g, " ")
    .trim();
  const limit = platform === "bluesky" ? 300 : 280;
  return {
    text: normalized,
    characters: normalized.length,
    limit,
  };
}

function buildShortFormMetaLine(platform) {
  if (platform === "reels") {
    return "Draft preview for Reels cover + caption";
  }
  if (platform === "tiktok") {
    return "Draft preview for TikTok caption card";
  }
  return "Draft preview for Instagram feed";
}

function buildMetaPills(post, platform, isApproved) {
  const pills = [
    `platform: ${platform}`,
    `writer: ${post.writer_mode || "unknown"}`,
  ];

  const postType = String(post.post_type || "").trim().toLowerCase();
  if (postType && postType !== platform && postType !== "unknown" && postType !== "social_post") {
    pills.push(`type: ${post.post_type}`);
  }

  if (platform === "x" || platform === "bluesky") {
    pills.push(`status: ${isApproved ? "approved" : "not approved"}`);
  }

  return `
    <div class="post-meta">
      ${pills.map((pill) => `<span class="pill">${pill}</span>`).join("")}
    </div>
  `;
}

function groupByDay(events) {
  const days = {};
  for (const event of events) {
    const day = (event.logged_at || "").slice(0, 10);
    if (!day) continue;
    days[day] = days[day] || { input: 0, output: 0 };
    days[day].input += event.input_tokens || 0;
    days[day].output += event.output_tokens || 0;
  }
  return Object.entries(days).sort(([a], [b]) => a.localeCompare(b));
}

function renderDailyChart(events) {
  const grouped = groupByDay(events).slice(-14);
  const maxTokens = Math.max(
    1,
    ...grouped.flatMap(([, totals]) => [totals.input, totals.output])
  );

  const html = grouped.length
    ? grouped
        .map(([day, totals]) => {
          const inputHeight = Math.max(2, Math.round((totals.input / maxTokens) * 200));
          const outputHeight = Math.max(2, Math.round((totals.output / maxTokens) * 200));
          return `
            <div class="day-group">
              <div class="bar-col">
                <div class="bar input" style="height:${inputHeight}px" title="Input ${totals.input}"></div>
              </div>
              <div class="bar-col">
                <div class="bar output" style="height:${outputHeight}px" title="Output ${totals.output}"></div>
              </div>
              <div class="bar-label">${day.slice(5)}</div>
            </div>
          `;
        })
        .join("")
    : '<p class="empty">No usage events logged yet.</p>';

  document.getElementById("daily-chart").innerHTML = html;
}

function renderStatusChart(events) {
  const statuses = ["success", "fallback", "error"];
  const total = Math.max(events.length, 1);
  const colors = {
    success: "status-success",
    fallback: "status-fallback",
    error: "status-error",
  };

  document.getElementById("status-chart").innerHTML = statuses
    .map((status) => {
      const count = events.filter((event) => event.status === status).length;
      const pct = Math.round((count / total) * 100);
      return `
        <div class="status-row">
          <div class="status-meta">
            <span>${status}</span>
            <span>${count} (${pct}%)</span>
          </div>
          <div class="status-track">
            <div class="status-fill ${colors[status]}" style="width:${pct}%"></div>
          </div>
        </div>
      `;
    })
    .join("");
}

function renderModelTable(events) {
  const models = {};
  for (const event of events) {
    const model = event.model || "unknown";
    models[model] = models[model] || { requests: 0, tokens: 0, cost: 0 };
    models[model].requests += 1;
    models[model].tokens += event.total_tokens || 0;
    models[model].cost += event.estimated_cost_usd || 0;
  }

  const rows = Object.entries(models)
    .sort(([, a], [, b]) => b.tokens - a.tokens)
    .map(
      ([model, stats]) => `
        <tr>
          <td>${model}</td>
          <td>${formatNumber(stats.requests)}</td>
          <td>${formatNumber(stats.tokens)}</td>
          <td>${formatCurrency(stats.cost)}</td>
        </tr>
      `
    )
    .join("");

  document.getElementById("model-table").innerHTML = rows
    ? `<table><thead><tr><th>Model</th><th>Requests</th><th>Tokens</th><th>Estimated Cost</th></tr></thead><tbody>${rows}</tbody></table>`
    : '<p class="empty">No model usage yet.</p>';
}

function renderEventsTable(events) {
  const rows = events
    .slice()
    .sort((a, b) => (b.logged_at || "").localeCompare(a.logged_at || ""))
    .slice(0, 20)
    .map(
      (event) => `
        <tr>
          <td>${event.logged_at ? event.logged_at.replace("T", " ").slice(0, 19) : ""}</td>
          <td>${event.title}</td>
          <td><span class="pill">${event.status}</span></td>
          <td>${formatNumber(event.total_tokens)}</td>
          <td>${event.latency_ms ? `${formatNumber(Math.round(event.latency_ms))} ms` : ""}</td>
          <td>${event.error || ""}</td>
        </tr>
      `
    )
    .join("");

  document.getElementById("events-table").innerHTML = rows
    ? `<table><thead><tr><th>Time</th><th>Shirt</th><th>Status</th><th>Tokens</th><th>Latency</th><th>Error</th></tr></thead><tbody>${rows}</tbody></table>`
    : '<p class="empty">No logged events yet. Run the bot in auto or ai mode to populate this view.</p>';
}

async function init() {
  try {
    const [events, postIndex, approvalQueue] = await Promise.all([
      loadUsageEvents(),
      loadPostIndex(),
      loadApprovalQueue(),
    ]);
    renderCards(events);
    const initialPath = renderPostFileOptions(postIndex);
    if (initialPath) {
      const posts = await loadPostBatch(initialPath);
      renderPostPreview(posts, initialPath, approvalQueue);
      const select = document.getElementById("post-file-select");
      select.addEventListener("change", async (event) => {
        const nextPosts = await loadPostBatch(event.target.value);
        renderPostPreview(nextPosts, event.target.value, approvalQueue);
      });
    }
    renderDailyChart(events);
    renderStatusChart(events);
    renderModelTable(events);
    renderEventsTable(events);
  } catch (error) {
    document.getElementById("summary-cards").innerHTML = `<article class="card"><div class="card-label">Dashboard Error</div><div>${error.message}</div></article>`;
  }
}

init();
