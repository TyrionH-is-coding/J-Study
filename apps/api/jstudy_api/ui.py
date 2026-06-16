from __future__ import annotations

INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>J Study</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
  <style>
    :root {
      --bg: #f5f6f7;
      --surface: #ffffff;
      --surface-alt: #f3f4f5;
      --border: #d0d6e0;
      --border-light: #e6e6e6;
      --text: #171717;
      --text-secondary: #6b7280;
      --text-muted: #9ca3af;
      --accent: #5e6ad2;
      --accent-hover: #7170ff;
      --accent-soft: #eef0ff;
      --warn: #dc2626;
      --success: #10b981;
      --shadow-sm: 0 1px 2px rgba(0,0,0,.04);
      --shadow-md: 0 4px 12px rgba(0,0,0,.06);
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { overflow: hidden; height: 100%; }
    body {
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      color: var(--text);
      background: var(--bg);
      -webkit-font-smoothing: antialiased;
    }
    .workspace {
      display: grid;
      grid-template-columns: 300px 5px 1fr 5px 360px;
      height: 100vh;
      overflow: hidden;
    }
    aside, main, .pdf-panel {
      min-width: 0;
      min-height: 0;
      border-right: 1px solid var(--border-light);
    }
    .resize-handle {
      width: 5px;
      cursor: col-resize;
      background: transparent;
      transition: background .15s;
      position: relative;
      z-index: 10;
    }
    .resize-handle:hover,
    .resize-handle.active {
      background: var(--accent);
      opacity: .35;
    }
    aside {
      padding: 20px 16px;
      background: var(--surface-alt);
      overflow-y: auto;
    }
    h1 {
      font-size: 18px;
      font-weight: 600;
      letter-spacing: -.3px;
    }
    h2 {
      font-size: 13px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: .5px;
      color: var(--text-secondary);
      margin-top: 20px;
      margin-bottom: 8px;
    }
    label {
      display: block;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-secondary);
      margin-top: 14px;
      margin-bottom: 4px;
    }
    input[type="file"],
    input[type="email"],
    input[type="password"],
    input[type="text"],
    select {
      width: 100%;
      padding: 8px 10px;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--surface);
      font-size: 13px;
      color: var(--text);
      font-family: inherit;
    }
    input:focus, select:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-soft);
    }
    button {
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--surface);
      color: var(--text);
      padding: 8px 14px;
      font-size: 13px;
      font-weight: 500;
      font-family: inherit;
      cursor: pointer;
      transition: background .12s, border-color .12s;
    }
    button:hover { background: var(--surface-alt); border-color: var(--text-muted); }
    button:disabled { opacity: .5; cursor: not-allowed; }
    .btn-primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
      font-weight: 600;
    }
    .btn-primary:hover { background: var(--accent-hover); border-color: var(--accent-hover); }
    .btn-primary:disabled { opacity: .5; }
    .run { width: 100%; margin-top: 14px; }
    .status {
      margin-top: 16px;
      padding-top: 12px;
      border-top: 1px solid var(--border-light);
      font-size: 12px;
      color: var(--text-secondary);
      line-height: 1.5;
      word-break: break-word;
    }
    /* Auth panel */
    #authPanel form { margin-top: 8px; }
    #authPanel form + form { margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--border-light); }

    /* Main output */
    main {
      padding: 28px 32px;
      overflow-y: auto;
      overflow-x: hidden;
      background: var(--bg);
    }
    .output {
      max-width: 820px;
      font-size: 14px;
      line-height: 1.75;
      color: var(--text);
    }
    .output h1 { font-size: 22px; font-weight: 700; margin: 24px 0 12px; letter-spacing: -.4px; }
    .output h2 { font-size: 17px; font-weight: 600; margin: 20px 0 8px; text-transform: none; letter-spacing: -.2px; color: var(--text); }
    .output h3 { font-size: 15px; font-weight: 600; margin: 16px 0 6px; color: var(--text); }
    .output h4, .output h5, .output h6 { font-size: 14px; font-weight: 600; margin: 12px 0 4px; }
    .output p { margin: 8px 0; }
    .output pre {
      overflow: auto;
      padding: 14px;
      border: 1px solid var(--border-light);
      border-radius: 6px;
      background: var(--surface);
      font-family: 'JetBrains Mono', ui-monospace, monospace;
      font-size: 13px;
      line-height: 1.5;
      white-space: pre-wrap;
    }
    .output code {
      font-family: 'JetBrains Mono', ui-monospace, monospace;
      font-size: .9em;
      padding: 1px 4px;
      border-radius: 3px;
      background: var(--surface-alt);
    }
    .output pre code { background: none; padding: 0; }
    .output table {
      width: 100%;
      border-collapse: collapse;
      margin: 12px 0;
      font-size: 13px;
      border: 1px solid var(--border-light);
      border-radius: 6px;
      overflow: hidden;
    }
    .output th, .output td {
      border: 1px solid var(--border-light);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }
    .output th {
      background: var(--surface-alt);
      font-weight: 600;
    }
    .output hr { border: none; border-top: 1px solid var(--border-light); margin: 20px 0; }
    .output ul, .output ol { padding-left: 20px; margin: 6px 0; }
    .output li { margin: 3px 0; }
    .output blockquote {
      border-left: 3px solid var(--accent);
      padding-left: 12px;
      margin: 10px 0;
      color: var(--text-secondary);
    }
    .empty {
      color: var(--text-muted);
      border: 1px dashed var(--border);
      padding: 24px;
      border-radius: 8px;
      text-align: center;
      font-size: 13px;
    }

    /* Evidence buttons */
    .evidence-btn {
      display: inline-flex;
      align-items: center;
      margin-left: 4px;
      padding: 1px 7px;
      border-radius: 999px;
      border: 1px solid #c4cde0;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 11px;
      font-weight: 600;
      line-height: 1.5;
      cursor: pointer;
      transition: background .12s;
      font-family: inherit;
    }
    .evidence-btn:hover { background: #dde2f5; }

    /* PDF panel */
    .pdf-panel {
      display: grid;
      grid-template-rows: auto minmax(100px, 16vh) minmax(0, 1fr);
      min-height: 0;
      background: var(--surface-alt);
      border-right: 0;
    }
    .pdf-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 10px 14px;
      border-bottom: 1px solid var(--border-light);
      font-size: 12px;
      color: var(--text-secondary);
    }
    .pdf-head-right { display: flex; align-items: center; gap: 10px; }
    .dl-btn {
      font-size: 11px; font-weight: 600; color: var(--accent);
      text-decoration: none; padding: 3px 8px;
      border: 1px solid var(--accent); border-radius: 6px;
      transition: background .12s;
    }
    .dl-btn:hover { background: var(--accent-soft); }
    .quality-badge {
      display: inline-block; font-size: 11px; font-weight: 600;
      padding: 2px 8px; border-radius: 999px; margin-left: 8px;
    }
    .quality-badge.pass { background: #d1fae5; color: #065f46; }
    .quality-badge.fail { background: #fee2e2; color: #991b1b; }
    .citation-list {
      overflow: auto;
      padding: 10px;
      border-bottom: 1px solid var(--border-light);
      background: var(--surface);
    }
    .citation-item {
      width: 100%;
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 4px 10px;
      margin-bottom: 6px;
      padding: 8px;
      border: 1px solid var(--border-light);
      border-radius: 6px;
      background: var(--surface);
      color: var(--text);
      text-align: left;
      font-size: 12px;
      cursor: pointer;
      font-family: inherit;
      transition: border-color .12s, background .12s;
    }
    .citation-item:last-child { margin-bottom: 0; }
    .citation-item:hover,
    .citation-item.active { border-color: var(--accent); background: var(--accent-soft); }
    .citation-ref { color: var(--accent); font-weight: 700; white-space: nowrap; }
    .citation-meta { color: var(--text-muted); font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .citation-quote {
      grid-column: 1 / -1;
      color: var(--text-secondary);
      font-size: 12px;
      line-height: 1.4;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .pdf-pages {
      width: 100%;
      height: 100%;
      min-height: 0;
      overflow: auto;
      padding: 14px 14px 24px;
      background: #eef1ec;
      scroll-behavior: smooth;
    }
    .pdf-page {
      margin: 0 auto 14px;
      max-width: 100%;
      border: 1px solid #c6cec7;
      border-radius: 6px;
      background: #fff;
      box-shadow: var(--shadow-md);
      overflow: hidden;
    }
    .pdf-page.active {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(94,106,210,.2), var(--shadow-md);
    }
    .pdf-page-label {
      padding: 6px 10px;
      border-bottom: 1px solid var(--border-light);
      background: var(--surface-alt);
      color: var(--text-secondary);
      font-size: 11px;
      font-weight: 600;
    }
    .pdf-page img { display: block; width: 100%; height: auto; background: #fff; }

    .error { color: var(--warn); font-weight: 600; font-size: 13px; }

    @media (max-width: 980px) {
      .workspace { grid-template-columns: 1fr; height: auto; overflow: visible; }
      aside, main, .pdf-panel { border-right: 0; border-bottom: 1px solid var(--border-light); }
      .pdf-panel { min-height: 60vh; }
    }

    /* KaTeX display math spacing */
    .output .katex-display { margin: 8px 0; overflow-x: auto; overflow-y: hidden; }
    .output .katex { font-size: 1.05em; }

    /* === Card selector === */
    .section-label {
      font-size: 11px; font-weight: 600; text-transform: uppercase;
      letter-spacing: .6px; color: var(--text-secondary);
      margin: 8px 0 4px; }
    .section-label:first-of-type { margin-top: 4px; }
    .scenario-cards { display: flex; flex-direction: column; gap: 5px; }
    .scenario-card {
      display: flex; align-items: center; gap: 10px;
      padding: 8px 10px;
      border: 1px solid var(--border); border-radius: 8px;
      background: var(--surface);
      cursor: pointer;
      transition: border-color .12s, background .12s, box-shadow .12s;
    }
    .scenario-card:hover { border-color: var(--text-muted); }
    .scenario-card.active {
      border-color: var(--accent);
      background: var(--accent-soft);
      box-shadow: 0 0 0 3px rgba(94,106,210,.1);
    }
    .scenario-icon {
      width: 32px; height: 32px; border-radius: 6px;
      display: flex; align-items: center; justify-content: center;
      font-size: 16px; flex-shrink: 0;
    }
    .scenario-name { font-size: 13px; font-weight: 600; color: var(--text); }
    .scenario-desc { font-size: 11px; color: var(--text-secondary); margin-top: 1px; }
    .mode-pills { display: flex; gap: 4px; margin-top: 2px; }
    .mode-pill {
      flex: 1; padding: 6px 4px;
      border: 1px solid var(--border); border-radius: 6px;
      background: var(--surface);
      font-size: 11px; font-weight: 500; color: var(--text-secondary);
      text-align: center; cursor: pointer;
      transition: all .12s; font-family: inherit;
    }
    .mode-pill:hover { border-color: var(--text-muted); color: var(--text); }
    .mode-pill.active {
      border-color: var(--accent); background: var(--accent);
      color: #fff; font-weight: 600;
    }
    .icon-med { background: #fce7f3; }
    .icon-gen { background: #dbeafe; }
    .icon-eng { background: #e0e7ff; }

    /* History list */
    .history {
      margin-top: 12px;
      padding-top: 10px;
      border-top: 1px solid var(--border-light);
    }
    .history-header {
      display: flex; align-items: center; justify-content: space-between;
      font-size: 12px; font-weight: 600; color: var(--text-secondary);
      cursor: pointer; user-select: none; padding: 2px 0;
    }
    .history-header:hover { color: var(--text); }
    .history-count {
      font-size: 10px; font-weight: 600; color: var(--text-muted);
      background: var(--border-light); padding: 1px 6px; border-radius: 999px;
    }
    .history-list {
      display: flex; flex-direction: column; gap: 3px; margin-top: 6px; max-height: 240px; overflow-y: auto;
    }
    .history-item {
      display: grid; grid-template-columns: 1fr auto;
      gap: 2px 8px;
      padding: 6px 8px;
      border: 1px solid var(--border-light); border-radius: 6px;
      background: var(--surface);
      cursor: pointer; font-size: 11px; text-align: left; font-family: inherit; color: var(--text);
      transition: border-color .12s, background .12s;
    }
    .history-item:hover { border-color: var(--text-muted); }
    .history-item:active { background: var(--accent-soft); border-color: var(--accent); }
    .history-item-title { font-weight: 600; }
    .history-item-meta { color: var(--text-muted); font-size: 10px; }
    .history-item-mode { font-size: 10px; color: var(--text-secondary); }
    .history-item-q-pass { color: #065f46; font-weight: 600; }
    .history-item-q-fail { color: #991b1b; font-weight: 600; }
    .history-empty { font-size: 11px; color: var(--text-muted); padding: 6px 0; }
  </style>
</head>
<body>
  <div class="workspace">
    <aside>
      <h1>J Study</h1>
      <section id="authPanel">
        <h2>Login</h2>
        <form id="loginForm" method="POST" action="/api/auth/login">
          <label>Email</label>
          <input name="email" type="email" autocomplete="email" required />
          <label>Password</label>
          <input name="password" type="password" autocomplete="current-password" required />
          <button class="btn-primary run" type="submit">Login</button>
        </form>
        <h2>Register</h2>
        <form id="registerForm" method="POST" action="/api/auth/register">
          <label>Email</label>
          <input name="email" type="email" autocomplete="email" required />
          <label>Password</label>
          <input name="password" type="password" autocomplete="new-password" required />
          <label>Invite code</label>
          <input name="invite_code" type="text" autocomplete="off" />
          <button class="btn-primary run" type="submit">Register</button>
        </form>
      </section>
      <form id="form" hidden>
        <div class="section-label">学科</div>
        <div class="scenario-cards" id="scenarioCards"></div>
        <div class="section-label">模式</div>
        <div class="mode-pills" id="modePills">
          <div class="mode-pill active" data-mode="">总结</div>
          <div class="mode-pill" data-mode="exam-quick">考前速记</div>
          <div class="mode-pill" data-mode="rewrite">改写重述</div>
        </div>
        <label>课件 PDF</label>
        <input name="pdf" type="file" accept="application/pdf" required />
        <label>课程大纲</label>
        <input name="outline" type="file" accept=".md,.txt,.pdf" />
        <input type="hidden" name="scenario_id" id="scenarioIdInput" value="" />
        <input type="hidden" name="mode" id="modeInput" value="" />
        <input type="hidden" name="parser_profile_id" id="parserProfileIdInput" value="fast" />
        <button class="btn-primary run" id="run" type="submit">生成学习资料</button>
      </form>
      <div class="status" id="status">等待上传</div>
      <div class="history" id="historySection" hidden>
        <div class="history-header" id="historyToggle">
          <span>📋 历史记录</span>
          <span class="history-count" id="historyCount">0</span>
        </div>
        <div class="history-list" id="historyList"></div>
      </div>
    </aside>
    <div class="resize-handle" data-target="aside" data-min="220" data-max="500"></div>
    <main>
      <article class="output" id="output"><div class="empty">生成后显示学习资料</div></article>
    </main>
    <div class="resize-handle" data-target="pdf" data-min="260" data-max="700"></div>
    <section class="pdf-panel">
      <div class="pdf-head">
        <strong>课件依据</strong>
        <div class="pdf-head-right">
          <span id="pdfMeta">未选择</span>
          <a class="dl-btn" id="downloadBtn" hidden href="#" download>⬇ 下载 .md</a>
        </div>
      </div>
      <div class="citation-list" id="evidenceList"><div class="empty">生成后显示 citation 对照</div></div>
      <div class="pdf-pages" id="pdfPages"><div class="empty">生成后显示 PDF 页面预览</div></div>
    </section>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
  <script>
    const authPanel = document.getElementById("authPanel");
    const form = document.getElementById("form");
    const loginForm = document.getElementById("loginForm");
    const registerForm = document.getElementById("registerForm");
    const run = document.getElementById("run");
    const statusBox = document.getElementById("status");
    const output = document.getElementById("output");
    const pdfMeta = document.getElementById("pdfMeta");
    const evidenceList = document.getElementById("evidenceList");
    const pdfPages = document.getElementById("pdfPages");
    const scenarioCards = document.getElementById("scenarioCards");
    const scenarioIdInput = document.getElementById("scenarioIdInput");
    const modeInput = document.getElementById("modeInput");
    const parserProfileIdInput = document.getElementById("parserProfileIdInput");
    const modePills = document.getElementById("modePills");
    const downloadBtn = document.getElementById("downloadBtn");
    const historySection = document.getElementById("historySection");
    const historyToggle = document.getElementById("historyToggle");
    const historyCount = document.getElementById("historyCount");
    const historyList = document.getElementById("historyList");
    let currentJob = "";
    let evidenceLinks = [];

    function escapeHtml(value) {
      return value.replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
    }

    const SCENARIO_ICONS = { "medicine": "icon-med", "general": "icon-gen", "engineering": "icon-eng" };
    const SCENARIO_EMOJI = { "medicine": "\uD83E\uDE7A", "general": "\uD83D\uDCD8", "engineering": "\uD83D\uDD27" };
    const SCENARIO_DESC = { "medicine": "医学课件", "general": "通用学科", "engineering": "工科课程" };

    function renderScenarioCard(item) {
      const id = String(item.id || "");
      const subj = String(item.subject || "");
      const emoji = SCENARIO_EMOJI[subj] || "\uD83D\uDCC4";
      const iconCls = SCENARIO_ICONS[subj] || "";
      const desc = SCENARIO_DESC[subj] || subj;
      return `<div class="scenario-card" data-id="${escapeHtml(id)}">
        <div class="scenario-icon ${iconCls}">${emoji}</div>
        <div class="scenario-info">
          <div class="scenario-name">${escapeHtml(item.display_name || item.id || "")}</div>
          <div class="scenario-desc">${desc}</div>
        </div>
      </div>`;
    }

    function selectScenario(id) {
      scenarioIdInput.value = id;
      scenarioCards.querySelectorAll(".scenario-card").forEach(c => {
        c.classList.toggle("active", c.dataset.id === id);
      });
    }

    function selectMode(mode) {
      modeInput.value = mode;
      modePills.querySelectorAll(".mode-pill").forEach(p => {
        p.classList.toggle("active", p.dataset.mode === mode);
      });
    }

    async function loadOptions() {
      const res = await fetch("/api/options");
      const opts = await res.json();
      const scenarios = opts.scenarios || [];
      // Render scenario cards
      scenarioCards.innerHTML = scenarios.map(renderScenarioCard).join("");
      // Card click handlers
      scenarioCards.querySelectorAll(".scenario-card").forEach(card => {
        card.addEventListener("click", () => selectScenario(card.dataset.id));
      });
      // Select default
      const defaultId = opts.default_scenario_id || (scenarios[0] && scenarios[0].id) || "";
      selectScenario(defaultId);
    }
    loadOptions().catch(() => {});

    // Mode pill click handler
    modePills.querySelectorAll(".mode-pill").forEach(pill => {
      pill.addEventListener("click", () => selectMode(pill.dataset.mode));
    });
    // Default mode = summary (empty string)
    selectMode("");

    function showAuthenticated(user) {
      authPanel.hidden = true;
      form.hidden = false;
      statusBox.textContent = `已登录 ${user.email}`;
      loadHistory();
    }
    function showSignedOut() {
      authPanel.hidden = false;
      form.hidden = true;
      statusBox.textContent = "请先登录";
      historySection.hidden = true;
    }

    const MODE_LABELS = { "": "总结", "exam-quick": "考前速记", "rewrite": "改写" };
    const SCENARIO_DISPLAY = { "medicine-default": "Medicine", "general-default": "General", "engineering-default": "Engineering" };

    async function loadHistory() {
      try {
        const res = await fetch("/api/jobs");
        if (!res.ok) return;
        const jobs = await res.json();
        if (!jobs.length) { historySection.hidden = true; return; }
        historySection.hidden = false;
        historyCount.textContent = jobs.length;
        historyList.innerHTML = jobs.map(j => {
          const scenarioName = SCENARIO_DISPLAY[j.scenario_id] || j.scenario_id;
          const modeName = MODE_LABELS[j.mode] || j.mode;
          const qCls = j.quality === "pass" ? "history-item-q-pass" : "history-item-q-fail";
          const qText = j.quality === "pass" ? "✅" : "❌";
          const pdfName = j.pdf_name ? j.pdf_name.slice(0, 28) + (j.pdf_name.length > 28 ? "…" : "") : "";
          const commit = j.build_commit || "";
          return `<button class="history-item" data-job-id="${j.job_id}">
            <span class="history-item-title">${escapeHtml(scenarioName)}</span>
            <span class="history-item-mode">${escapeHtml(modeName)} <span class="${qCls}">${qText}</span></span>
            <span class="history-item-meta">${escapeHtml(pdfName)}</span>
            <span class="history-item-meta">${commit ? escapeHtml(commit) : ""}${escapeHtml(j.job_id.slice(0, 12))}…</span>
          </button>`;
        }).join("");
        // Click to reload
        historyList.querySelectorAll(".history-item").forEach(item => {
          item.addEventListener("click", () => loadJob(item.dataset.jobId));
        });
      } catch { historySection.hidden = true; }
    }

    async function loadJob(jobId) {
      currentJob = jobId;
      statusBox.textContent = `加载中…  (${jobId})`;
      output.innerHTML = `<div class="empty">加载中</div>`;
      evidenceList.innerHTML = `<div class="empty">加载引用</div>`;
      pdfPages.innerHTML = `<div class="empty">加载 PDF</div>`;
      downloadBtn.hidden = true;
      try {
        const [outRes, evidenceRes, pdfInfoRes] = await Promise.all([
          fetch(`/api/jobs/${jobId}/output`),
          fetch(`/api/jobs/${jobId}/evidence`),
          fetch(`/api/jobs/${jobId}/pdf-info`)
        ]);
        if (outRes.status === 401) { statusBox.innerHTML = `<span class="error">会话已过期，请刷新页面重新登录</span>`; return; }
        if (!outRes.ok) { statusBox.innerHTML = `<span class="error">输出不存在或已清理</span>`; return; }
        const out = await outRes.json();
        const evidence = await evidenceRes.json();
        const pdfInfo = await pdfInfoRes.json();
        evidenceLinks = evidence.evidence_links || [];
        output.innerHTML = renderMarkdown(out.markdown);
        // Quality badge
        const qualRes = await fetch(`/api/jobs/${jobId}`);
        if (qualRes.ok) {
          const jobData = await qualRes.json();
          if (jobData.quality && jobData.quality.status) {
            const badge = document.createElement("span");
            badge.className = `quality-badge ${jobData.quality.status}`;
            badge.textContent = jobData.quality.status === "pass" ? "✅ 通过" : "❌ 未通过";
            const firstH = output.querySelector("h1, h2");
            if (firstH) firstH.insertAdjacentElement("afterend", badge);
            else output.insertBefore(badge, output.firstChild);
          }
        }
        renderEvidencePanel(evidenceLinks);
        renderPdfPages(pdfInfo.page_count || 0);
        pdfMeta.textContent = "已生成";
        downloadBtn.href = `/api/jobs/${jobId}/export`;
        downloadBtn.hidden = false;
        statusBox.textContent = `已完成  (${jobId})`;
      } catch (e) {
        console.error("loadJob error:", e);
        statusBox.innerHTML = `<span class="error">加载失败: ${escapeHtml(String(e.message || e))}。请刷新页面重新登录</span>`;
      }
    }

    async function loadSession() {
      const res = await fetch("/api/auth/me");
      if (!res.ok) { showSignedOut(); return; }
      showAuthenticated(await res.json());
    }
    async function submitAuth(path, formEl) {
      const payload = Object.fromEntries(new FormData(formEl));
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const body = await response.json();
      if (!response.ok) {
        statusBox.innerHTML = `<span class="error">${escapeHtml(String(body.detail || "认证失败"))}</span>`;
        return;
      }
      showAuthenticated(body);
    }

    loginForm.addEventListener("submit", e => {
      e.preventDefault();
      submitAuth("/api/auth/login", loginForm).catch(err => { statusBox.innerHTML = `<span class="error">${escapeHtml(err.message)}</span>`; });
    });
    registerForm.addEventListener("submit", e => {
      e.preventDefault();
      submitAuth("/api/auth/register", registerForm).catch(err => { statusBox.innerHTML = `<span class="error">${escapeHtml(err.message)}</span>`; });
    });
    loadSession().catch(showSignedOut);

    // --- Markdown renderer with KaTeX ---

    function renderKatex(text, displayMode) {
      try {
        return katex.renderToString(text, { displayMode, throwOnError: false });
      } catch {
        return escapeHtml(text);
      }
    }

    function evidenceButtons(ids, seenRefs) {
      return ids.map(id => {
        seenRefs[id] = (seenRefs[id] || 0) + 1;
        return `<button class="evidence-btn" data-ref="${id}" data-occurrence="${seenRefs[id]}" type="button">依据 ${id}</button>`;
      }).join("");
    }

    function renderMarkdown(markdown) {
      // Step 1: Extract LaTeX blocks and replace with placeholders
      const latexPlaceholders = [];
      let processed = markdown.replace(/\$\$([\s\S]*?)\$\$/g, (_, expr) => {
        const idx = latexPlaceholders.length;
        latexPlaceholders.push({ expr: expr.trim(), display: true });
        return `\x00LATEX_DISPLAY_${idx}\x00`;
      });
      processed = processed.replace(/\$(.+?)\$/g, (_, expr) => {
        const idx = latexPlaceholders.length;
        latexPlaceholders.push({ expr: expr.trim(), display: false });
        return `\x00LATEX_INLINE_${idx}\x00`;
      });

      // --- Inner helpers (closure over latexPlaceholders) ---

      function renderInlineMarkdown(line) {
        return line
          .split(/(<button class="evidence-btn"[\s\S]*?<\/button>)/g)
          .map(part => {
            if (part.startsWith("<button")) return part;
            let processed = escapeHtml(part);
            // Replace LaTeX placeholders with KaTeX HTML
            processed = processed.replace(/\x00LATEX_INLINE_(\d+)\x00/g, (_, idx) => {
              const { expr } = latexPlaceholders[parseInt(idx)];
              return renderKatex(expr, false);
            });
            processed = processed.replace(/\x00LATEX_DISPLAY_(\d+)\x00/g, (_, idx) => {
              const { expr } = latexPlaceholders[parseInt(idx)];
              return renderKatex(expr, true);
            });
            return processed
              .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
              .replace(/`([^`]+)`/g, "<code>$1</code>");
          })
          .join("");
      }

      function isTableLine(line) { return /^\s*\|.+\|\s*$/.test(line); }
      function isTableSeparator(line) {
        return /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$/.test(line);
      }
      function splitTableRow(line) {
        return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(c => c.trim());
      }
      function renderTableBlock(lines) {
        const rows = lines.filter(l => !isTableSeparator(l)).map(splitTableRow);
        if (!rows.length) return "";
        const h = rows[0], b = rows.slice(1);
        return `<table><thead><tr>${h.map(c => `<th>${renderInlineMarkdown(c)}</th>`).join("")}</tr></thead><tbody>${b.map(r => `<tr>${r.map(c => `<td>${renderInlineMarkdown(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
      }
      function renderCodeBlock(lines) {
        return `<pre><code>${escapeHtml(lines.join("\n"))}</code></pre>`;
      }

      // --- End inner helpers ---

      // Step 2: Insert evidence buttons
      const seenRefs = {};
      const withButtons = processed.replace(/<!--\s*evidence:\s*([^>]+?)\s*-->/gi, (_, raw) => {
        const ids = raw.match(/E\d{3}/g) || [];
        return evidenceButtons(ids, seenRefs);
      });

      // Step 3: Parse lines into HTML blocks
      const lines = withButtons.split(/\r?\n/);
      const blocks = [];
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (line.startsWith("\x00LATEX_DISPLAY_") || line.startsWith("\x00LATEX_INLINE_")) {
          // LaTeX on its own line — keep as block
          blocks.push(line);
          continue;
        }
        if (line.startsWith("```")) {
          const codeLines = [];
          i++;
          while (i < lines.length && !lines[i].startsWith("```")) {
            codeLines.push(lines[i]);
            i++;
          }
          blocks.push(renderCodeBlock(codeLines));
          continue;
        }
        if (isTableLine(line)) {
          const tableLines = [];
          while (i < lines.length && isTableLine(lines[i])) {
            tableLines.push(lines[i]);
            i++;
          }
          i--;
          blocks.push(renderTableBlock(tableLines));
          continue;
        }
        const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
        if (headingMatch) {
          const level = Math.min(headingMatch[1].length + 1, 6);
          blocks.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
          continue;
        }
        if (line.trim() === "---") {
          blocks.push("<hr>");
          continue;
        }
        if (!line.trim()) continue;

        // Process inline LaTeX inside a paragraph — protect KaTeX HTML from escapeHtml
        let htmlLine = line;
        const katexSpans = [];
        htmlLine = htmlLine.replace(/\x00LATEX_INLINE_(\d+)\x00/g, (_, idx) => {
          const { expr } = latexPlaceholders[parseInt(idx)];
          const kidx = katexSpans.length;
          katexSpans.push(renderKatex(expr, false));
          return `\x00KATEX_SPAN_${kidx}\x00`;
        });
        htmlLine = htmlLine.replace(/\x00LATEX_DISPLAY_(\d+)\x00/g, (_, idx) => {
          const { expr } = latexPlaceholders[parseInt(idx)];
          const kidx = katexSpans.length;
          katexSpans.push(renderKatex(expr, true));
          return `\x00KATEX_SPAN_${kidx}\x00`;
        });
        blocks.push(`<p>${renderInlineMarkdown(htmlLine).replace(/\x00KATEX_SPAN_(\d+)\x00/g, (_, idx) => katexSpans[parseInt(idx)])}</p>`);
      }

      // Step 4: Restore LaTeX placeholders that ended up as standalone blocks
      const html = blocks.map(b => {
        if (typeof b !== "string") return b;
        const displayMatch = b.match(/^\x00LATEX_DISPLAY_(\d+)\x00$/);
        if (displayMatch) {
          const { expr } = latexPlaceholders[parseInt(displayMatch[1])];
          return renderKatex(expr, true);
        }
        const inlineMatch = b.match(/^\x00LATEX_INLINE_(\d+)\x00$/);
        if (inlineMatch) {
          const { expr } = latexPlaceholders[parseInt(inlineMatch[1])];
          return renderKatex(expr, false);
        }
        return b;
      }).join("");

      return html;
    }

    function findEvidenceLink(ref, occurrence) {
      const wanted = Number(occurrence || 1);
      return evidenceLinks.find(item => item.ref_id === ref && Number(item.occurrence || 1) === wanted)
        || evidenceLinks.find(item => item.ref_id === ref);
    }

    function renderEvidencePanel(links) {
      if (!links.length) {
        evidenceList.innerHTML = `<div class="empty">没有可显示的引用</div>`;
        return;
      }
      evidenceList.innerHTML = links.map(link => {
        const target = link.target || {};
        const page = target.page || 1;
        const chunk = target.chunk_id || "";
        const quote = String(target.quote || "").slice(0, 220);
        return `<button class="citation-item" data-ref="${link.ref_id}" data-occurrence="${link.occurrence || 1}" type="button">
          <span class="citation-ref">${escapeHtml(link.ref_id)}</span>
          <span class="citation-meta">page ${escapeHtml(String(page))}${chunk ? " · " + escapeHtml(chunk) : ""}</span>
          <span class="citation-quote">${escapeHtml(quote)}</span>
        </button>`;
      }).join("");
    }

    function renderPdfPages(pageCount) {
      if (!pageCount) {
        pdfPages.innerHTML = `<div class="empty">无法读取 PDF 页面</div>`;
        return;
      }
      pdfPages.innerHTML = Array.from({ length: pageCount }, (_, i) => {
        const page = i + 1;
        return `<figure class="pdf-page" data-page="${page}">
          <figcaption class="pdf-page-label">Page ${page}</figcaption>
          <img loading="lazy" src="/api/jobs/${currentJob}/pdf-page/${page}.png" alt="PDF page ${page}">
        </figure>`;
      }).join("");
    }

    function scrollPdfPageIntoView(page) {
      document.querySelectorAll(".pdf-page.active").forEach(el => el.classList.remove("active"));
      const target = pdfPages.querySelector(`.pdf-page[data-page="${page}"]`);
      if (!target) return;
      target.classList.add("active");
      const containerRect = pdfPages.getBoundingClientRect();
      const targetRect = target.getBoundingClientRect();
      const top = pdfPages.scrollTop + targetRect.top - containerRect.top - ((pdfPages.clientHeight - targetRect.height) / 2);
      pdfPages.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
    }

    function showEvidenceLink(link, opts = {}) {
      if (!link || !currentJob) return;
      const page = link.target && link.target.page ? link.target.page : 1;
      pdfMeta.textContent = `${link.ref_id} / page ${page}`;
      scrollPdfPageIntoView(page);
      document.querySelectorAll(".citation-item.active").forEach(el => el.classList.remove("active"));
      const sel = `.citation-item[data-ref="${link.ref_id}"][data-occurrence="${link.occurrence || 1}"]`;
      const active = evidenceList.querySelector(sel);
      if (active) active.classList.add("active");
      if (opts.scrollCitationList && active) active.scrollIntoView({ block: "nearest" });
    }

    const PROGRESS_STAGES = ["解析课件…", "检索证据…", "生成学习资料…"];

    async function poll(jobId, pollCount) {
      pollCount = pollCount || 0;
      const res = await fetch(`/api/jobs/${jobId}`);
      const job = await res.json();
      // Show progress stages while running/pending
      if (job.status !== "completed" && job.status !== "failed") {
        const stage = PROGRESS_STAGES[Math.min(pollCount, PROGRESS_STAGES.length - 1)];
        statusBox.textContent = `${stage}  (${jobId})`;
      } else {
        statusBox.textContent = `状态：${job.status}  (${jobId})`;
      }
      if (job.status === "completed") {
        try {
          const [outRes, evidenceRes, pdfInfoRes] = await Promise.all([
            fetch(job.output_url),
            fetch(job.evidence_url),
            fetch(job.pdf_info_url)
          ]);
          if (!outRes.ok) { statusBox.innerHTML = `<span class="error">获取输出失败 (${outRes.status})</span>`; run.disabled = false; return; }
          const out = await outRes.json();
          const evidence = await evidenceRes.json();
          const pdfInfo = await pdfInfoRes.json();
          evidenceLinks = evidence.evidence_links || [];
          output.innerHTML = renderMarkdown(out.markdown);
        // Quality badge — insert before first heading or at top
        if (job.quality && job.quality.status) {
          const badge = document.createElement("span");
          badge.className = `quality-badge ${job.quality.status}`;
          badge.textContent = job.quality.status === "pass" ? "✅ 通过" : "❌ 未通过";
          const firstH = output.querySelector("h1, h2");
          if (firstH) firstH.insertAdjacentElement("afterend", badge);
          else output.insertBefore(badge, output.firstChild);
        }
        renderEvidencePanel(evidenceLinks);
        renderPdfPages(pdfInfo.page_count || 0);
        pdfMeta.textContent = "已生成";
        // Download button
        downloadBtn.href = `/api/jobs/${jobId}/export`;
        downloadBtn.hidden = false;
        run.disabled = false;
        loadHistory();
        return;
        } catch (e) {
          console.error("poll render error:", e);
          statusBox.innerHTML = `<span class="error">渲染失败: ${escapeHtml(e.message || String(e))}</span>`;
          run.disabled = false;
          return;
        }
      }
      if (job.status === "failed") {
        statusBox.innerHTML = `<span class="error">${escapeHtml(job.error || "生成失败")}</span>`;
        run.disabled = false;
        return;
      }
      setTimeout(() => poll(jobId, pollCount + 1), 1200);
    }

    form.addEventListener("submit", async e => {
      e.preventDefault();
      run.disabled = true;
      statusBox.textContent = "上传中…";
      output.innerHTML = `<div class="empty">生成中</div>`;
      evidenceList.innerHTML = `<div class="empty">等待引用</div>`;
      pdfPages.innerHTML = `<div class="empty">等待 PDF 预览</div>`;
      downloadBtn.hidden = true;
      const res = await fetch("/api/generate", { method: "POST", body: new FormData(form) });
      const data = await res.json();
      if (!res.ok) {
        statusBox.innerHTML = `<span class="error">${escapeHtml(String(data.detail || "请求失败"))}</span>`;
        run.disabled = false;
        return;
      }
      currentJob = data.job_id;
      poll(currentJob);
    });

    output.addEventListener("click", e => {
      const btn = e.target.closest(".evidence-btn");
      if (!btn || !currentJob) return;
      const link = findEvidenceLink(btn.dataset.ref, btn.dataset.occurrence);
      showEvidenceLink(link, { scrollCitationList: false });
    });

    evidenceList.addEventListener("click", e => {
      const btn = e.target.closest(".citation-item");
      if (!btn || !currentJob) return;
      const link = findEvidenceLink(btn.dataset.ref, btn.dataset.occurrence);
      showEvidenceLink(link, { scrollCitationList: true });
    });

    // --- Column resize ---
    document.addEventListener("DOMContentLoaded", function() {
      const handles = document.querySelectorAll(".resize-handle");
      const workspace = document.querySelector(".workspace");
      const aside = document.querySelector("aside");
      const pdfPanel = document.querySelector(".pdf-panel");
      if (!workspace || !aside || !pdfPanel) return;
      let drag = null;

      // Initialize grid with defaults
      workspace.style.gridTemplateColumns = "300px 5px 1fr 5px 360px";

      handles.forEach(h => {
        h.addEventListener("mousedown", e => {
          e.preventDefault();
          const target = h.dataset.target;
          const minW = parseInt(h.dataset.min) || 200;
          const maxW = parseInt(h.dataset.max) || 800;
          const current = target === "aside" ? aside.offsetWidth : pdfPanel.offsetWidth;
          const startX = e.clientX;
          h.classList.add("active");
          drag = { target, minW, maxW, startX, current, h };
        });
      });

      document.addEventListener("mousemove", e => {
        if (!drag) return;
        const delta = e.clientX - drag.startX;
        const sign = drag.target === "aside" ? 1 : -1;
        const newW = Math.min(drag.maxW, Math.max(drag.minW, drag.current + sign * delta));
        const asideW = drag.target === "aside" ? newW : aside.offsetWidth;
        const pdfW = drag.target === "pdf" ? newW : pdfPanel.offsetWidth;
        workspace.style.gridTemplateColumns = `${asideW}px 5px 1fr 5px ${pdfW}px`;
      });

      document.addEventListener("mouseup", () => {
        if (!drag) return;
        drag.h.classList.remove("active");
        drag = null;
      });
    });
  </script>
</body>
</html>
"""