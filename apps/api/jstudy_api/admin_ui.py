from __future__ import annotations


ADMIN_SETTINGS_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>J Study Admin Settings</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #18221e;
      --muted: #65706b;
      --line: #d7ded8;
      --paper: #f8faf7;
      --panel: #ffffff;
      --soft: #edf4ef;
      --accent: #0f766e;
      --danger: #9a3412;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
      color: var(--ink);
      background: var(--paper);
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      padding: 18px 26px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    h1, h2, h3 { margin: 0; line-height: 1.2; letter-spacing: 0; }
    h1 { font-size: 22px; }
    h2 { font-size: 16px; }
    h3 { font-size: 14px; color: var(--muted); }
    button {
      border: 1px solid var(--accent);
      border-radius: 6px;
      background: var(--accent);
      color: #fff;
      padding: 8px 12px;
      font-weight: 700;
      cursor: pointer;
    }
    button.secondary {
      background: var(--panel);
      color: var(--accent);
    }
    button:disabled { opacity: .55; cursor: wait; }
    main {
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(360px, .75fr);
      gap: 18px;
      padding: 20px 26px 34px;
    }
    section {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 18px;
    }
    .stack { display: grid; gap: 18px; }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 13px 14px;
      margin-top: 14px;
    }
    label {
      display: grid;
      gap: 6px;
      min-width: 0;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    input, select, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      padding: 8px 9px;
      font: inherit;
      font-size: 13px;
    }
    textarea {
      min-height: 220px;
      resize: vertical;
      font-family: Consolas, "Cascadia Mono", monospace;
      line-height: 1.45;
    }
    .full { grid-column: 1 / -1; }
    .hint {
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
    }
    .toolbar {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    #status {
      min-height: 18px;
      color: var(--muted);
      font-size: 13px;
    }
    #status.error { color: var(--danger); font-weight: 700; }
    pre {
      max-height: 240px;
      overflow: auto;
      margin: 12px 0 0;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #111;
      color: #ddd;
      padding: 12px;
      font-size: 12px;
      white-space: pre-wrap;
    }
    .invite-list {
      display: grid;
      gap: 10px;
      margin-top: 12px;
    }
    .invite-row {
      display: grid;
      gap: 8px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--soft);
      padding: 10px;
    }
    .invite-meta {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
      word-break: break-word;
    }
    @media (max-width: 960px) {
      main { grid-template-columns: 1fr; padding: 16px; }
      header { align-items: flex-start; flex-direction: column; padding: 16px; }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>J Study Admin Settings</h1>
      <div class="hint">Operator-only runtime configuration. End users should not see this page.</div>
    </div>
    <div class="toolbar">
      <button class="secondary" id="reloadBtn" type="button">Reload</button>
      <button id="saveBtn" type="button">Save</button>
      <span id="status"></span>
    </div>
  </header>
  <main id="adminSettingsApp">
    <div class="stack">
      <section>
        <h2>Model, RAG, and Web Search</h2>
        <div class="grid">
          <label>Chat provider <input id="llmBinding"></label>
          <label>Chat model <input id="llmModel"></label>
          <label class="full">Chat base URL <input id="llmBaseUrl"></label>
          <label class="full">Chat API key <input id="llmApiKey" type="password" autocomplete="new-password" placeholder="leave blank to keep existing key"></label>
          <label>Embedding provider <input id="embeddingBinding"></label>
          <label>Embedding model <input id="embeddingModel"></label>
          <label class="full">Embedding base URL <input id="embeddingBaseUrl"></label>
          <label class="full">Embedding API key <input id="embeddingApiKey" type="password" autocomplete="new-password" placeholder="leave blank to keep existing key"></label>
          <label>Chunk max chars <input id="ragChunkMaxChars" inputmode="numeric"></label>
          <label>Chunk overlap <input id="ragChunkOverlap" inputmode="numeric"></label>
          <label>Top-k candidates <input id="ragTopK" inputmode="numeric"></label>
          <label>Per-query limit <input id="ragPerQuery" inputmode="numeric"></label>
          <label>Mnemonic limit <input id="ragMnemonicLimit" inputmode="numeric"></label>
          <label>Search provider
            <select id="searchProvider">
              <option value="none">None</option>
              <option value="duckduckgo">DuckDuckGo</option>
              <option value="brave">Brave</option>
              <option value="tavily">Tavily</option>
              <option value="jina">Jina</option>
              <option value="searxng">SearXNG</option>
              <option value="perplexity">Perplexity</option>
              <option value="serper">Serper</option>
            </select>
          </label>
          <label>Search max results <input id="searchMaxResults" inputmode="numeric"></label>
          <label class="full">Search base URL <input id="searchBaseUrl"></label>
          <label class="full">Search API key <input id="searchApiKey" type="password" autocomplete="new-password" placeholder="leave blank to keep existing key"></label>
        </div>
        <div class="toolbar" style="margin-top:14px">
          <button class="secondary" data-test="llm" type="button">Test LLM</button>
          <button class="secondary" data-test="embedding" type="button">Test Embedding</button>
          <button class="secondary" data-test="search" type="button">Test Search</button>
        </div>
        <pre id="diagnostics">Diagnostics output appears here.</pre>
      </section>
      <section>
        <h2>Document Parsing</h2>
        <div class="grid">
          <label>Default parser profile <select id="defaultParserProfileId"></select></label>
          <label>Parser backend
            <select id="parserBackend">
              <option value="pymupdf">PyMuPDF</option>
              <option value="mineru">MinerU</option>
            </select>
          </label>
          <label>MinerU mode
            <select id="mineruMode">
              <option value="local">Local</option>
              <option value="cloud">Cloud</option>
            </select>
          </label>
          <label class="full">MinerU API base URL <input id="mineruApiBaseUrl"></label>
          <label class="full">MinerU API token <input id="mineruApiToken" type="password" autocomplete="new-password"></label>
          <label><span><input id="parserOcr" type="checkbox"> OCR</span></label>
          <label><span><input id="parserTables" type="checkbox"> Tables</span></label>
          <label><span><input id="parserFormulas" type="checkbox"> Formulas</span></label>
          <label><span><input id="qualityEnabled" type="checkbox"> Enable quality profile</span></label>
          <label><span><input id="qualityVisibleToUsers" type="checkbox"> Show quality profile to users</span></label>
        </div>
      </section>
    </div>
    <div class="stack">
      <section>
        <h2>Content Pack</h2>
        <div class="grid">
          <label>Default scenario <select id="defaultScenarioId"></select></label>
          <label class="full">Pack name <input id="packName"></label>
          <label>Subject <input id="packSubject"></label>
          <label>Enabled <select id="packEnabled"><option value="true">Enabled</option><option value="false">Disabled</option></select></label>
          <label class="full">Soul path <input id="packSoulPath"></label>
          <label class="full">Mnemonics Markdown path <input id="packMnemonicsPath"></label>
          <label class="full">Mnemonics JSON path <input id="packMnemonicsJsonPath"></label>
        </div>
      </section>
      <section>
        <h2>Invite Codes</h2>
        <div class="grid">
          <label class="full">Code <input id="inviteCodeInput" autocomplete="off"></label>
          <label class="full">Label <input id="inviteLabelInput"></label>
        </div>
        <div class="toolbar" style="margin-top:14px">
          <button class="secondary" id="createInviteBtn" type="button">Create Invite</button>
          <button class="secondary" id="reloadInvitesBtn" type="button">Reload Invites</button>
        </div>
        <div class="invite-list" id="inviteCodes">Invite codes appear here.</div>
        <pre id="inviteCodeUses">Invite usage appears here.</pre>
      </section>
      <section>
        <h2>Mnemonics JSON</h2>
        <h3>JSON is the management source; Markdown is rendered for prompts.</h3>
        <textarea id="mnemonicsJson" spellcheck="false"></textarea>
      </section>
    </div>
  </main>
  <script>
    const ids = [
      "llmBinding", "llmModel", "llmBaseUrl", "llmApiKey",
      "embeddingBinding", "embeddingModel", "embeddingBaseUrl", "embeddingApiKey",
      "ragChunkMaxChars", "ragChunkOverlap", "ragTopK", "ragPerQuery", "ragMnemonicLimit",
      "searchProvider", "searchMaxResults", "searchBaseUrl", "searchApiKey",
      "defaultParserProfileId", "parserBackend", "mineruMode", "mineruApiBaseUrl", "mineruApiToken",
      "parserOcr", "parserTables", "parserFormulas", "qualityEnabled", "qualityVisibleToUsers",
      "defaultScenarioId", "packName", "packSubject", "packEnabled", "packSoulPath", "packMnemonicsPath",
      "packMnemonicsJsonPath", "mnemonicsJson"
    ];
    const el = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));
    const statusBox = document.getElementById("status");
    const diagnostics = document.getElementById("diagnostics");
    const inviteCodeInput = document.getElementById("inviteCodeInput");
    const inviteLabelInput = document.getElementById("inviteLabelInput");
    const inviteCodes = document.getElementById("inviteCodes");
    const inviteCodeUses = document.getElementById("inviteCodeUses");
    let settings = null;

    function apiPath(path) {
      return `${path}${window.location.search || ""}`;
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
    }

    function setStatus(text, error = false) {
      statusBox.textContent = text;
      statusBox.className = error ? "error" : "";
    }

    function activeProfile(service) {
      const group = settings.model_catalog.services[service];
      return group.profiles.find(p => p.id === group.active_profile_id) || group.profiles[0];
    }

    function activeModel(service) {
      const group = settings.model_catalog.services[service];
      const profile = activeProfile(service);
      return profile.models.find(m => m.id === group.active_model_id) || profile.models[0];
    }

    function activePack() {
      return settings.content_pack.packs.find(p => p.id === settings.content_pack.active_pack_id) || settings.content_pack.packs[0];
    }

    function qualityProfile() {
      const parserProfiles = settings.runtime.parser_profiles || { profiles: [] };
      return parserProfiles.profiles.find(profile => profile.id === "quality") || {};
    }

    function renderSelect(select, items, value) {
      select.innerHTML = items.map(item => `<option value="${item.id}">${item.display_name || item.name || item.id}</option>`).join("");
      select.value = value || (items[0] && items[0].id) || "";
    }

    function render() {
      const llmProfile = activeProfile("llm");
      const llmModel = activeModel("llm");
      const embeddingProfile = activeProfile("embedding");
      const embeddingModel = activeModel("embedding");
      const searchProfile = activeProfile("search");
      const rag = settings.runtime.rag;
      const parser = settings.runtime.parser;
      const parserProfiles = settings.runtime.parser_profiles || { default_profile_id: "fast", profiles: [] };
      const quality = qualityProfile();
      const pack = activePack();
      const scenarios = settings.content_pack.scenarios || [];
      el.llmBinding.value = llmProfile.binding || "";
      el.llmModel.value = llmModel.model || "";
      el.llmBaseUrl.value = llmProfile.base_url || "";
      el.llmApiKey.value = "";
      el.embeddingBinding.value = embeddingProfile.binding || "";
      el.embeddingModel.value = embeddingModel.model || "";
      el.embeddingBaseUrl.value = embeddingProfile.base_url || "";
      el.embeddingApiKey.value = "";
      el.ragChunkMaxChars.value = rag.chunk_max_chars;
      el.ragChunkOverlap.value = rag.chunk_overlap;
      el.ragTopK.value = rag.top_k_candidates;
      el.ragPerQuery.value = rag.per_query_limit;
      el.ragMnemonicLimit.value = rag.mnemonic_limit;
      el.searchProvider.value = searchProfile.provider || "none";
      el.searchMaxResults.value = searchProfile.max_results || 5;
      el.searchBaseUrl.value = searchProfile.base_url || "";
      el.searchApiKey.value = "";
      renderSelect(el.defaultParserProfileId, parserProfiles.profiles || [], parserProfiles.default_profile_id || "fast");
      el.parserBackend.value = parser.backend || "pymupdf";
      el.mineruMode.value = (parser.mineru && parser.mineru.mode) || "local";
      el.mineruApiBaseUrl.value = (parser.mineru && parser.mineru.api_base_url) || "https://mineru.net";
      el.mineruApiToken.value = "";
      el.parserOcr.checked = Boolean(parser.ocr);
      el.parserTables.checked = Boolean(parser.tables);
      el.parserFormulas.checked = Boolean(parser.formulas);
      el.qualityEnabled.checked = Boolean(quality.enabled);
      el.qualityVisibleToUsers.checked = Boolean(quality.visible_to_users);
      renderSelect(el.defaultScenarioId, scenarios, settings.content_pack.default_scenario_id);
      el.packName.value = pack.name || "";
      el.packSubject.value = pack.subject || "";
      el.packEnabled.value = String(pack.enabled !== false);
      el.packSoulPath.value = pack.soul_path || "";
      el.packMnemonicsPath.value = pack.mnemonics_path || "";
      el.packMnemonicsJsonPath.value = pack.mnemonics_json_path || "";
      el.mnemonicsJson.value = JSON.stringify(settings.mnemonics, null, 2);
    }

    function renderInviteCodes(items) {
      if (!items.length) {
        inviteCodes.textContent = "No invite codes.";
        return;
      }
      inviteCodes.innerHTML = items.map(item => {
        const enabledText = item.enabled ? "Enabled" : "Disabled";
        const toggleText = item.enabled ? "Disable" : "Enable";
        const usageCount = Number(item.usage_count || 0);
        return `
          <div class="invite-row">
            <strong>${escapeHtml(item.code)}</strong>
            <div class="invite-meta">${escapeHtml(item.label || "No label")} | ${enabledText} | uses: ${usageCount}</div>
            <div class="toolbar">
              <button class="secondary" data-invite-toggle="${escapeHtml(item.id)}" data-next-enabled="${item.enabled ? "false" : "true"}" type="button">${toggleText}</button>
              <button class="secondary" data-invite-uses="${escapeHtml(item.id)}" type="button">View Uses</button>
            </div>
          </div>
        `;
      }).join("");
    }

    async function loadInviteCodes() {
      const response = await fetch(apiPath("/api/admin/invite-codes"));
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
      renderInviteCodes(payload);
    }

    async function createInviteCode() {
      const code = inviteCodeInput.value.trim();
      if (!code) throw new Error("Invite code is required");
      const response = await fetch(apiPath("/api/admin/invite-codes"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, label: inviteLabelInput.value.trim() })
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
      inviteCodeInput.value = "";
      inviteLabelInput.value = "";
      inviteCodeUses.textContent = "Invite usage appears here.";
      await loadInviteCodes();
    }

    async function setInviteEnabled(inviteId, enabled) {
      const response = await fetch(apiPath(`/api/admin/invite-codes/${inviteId}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled })
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
      await loadInviteCodes();
    }

    async function loadInviteUses(inviteId) {
      const response = await fetch(apiPath(`/api/admin/invite-codes/${inviteId}/uses`));
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
      inviteCodeUses.textContent = JSON.stringify(payload, null, 2);
    }

    async function load() {
      setStatus("Loading...");
      const response = await fetch(apiPath("/api/admin/settings"));
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      settings = await response.json();
      render();
      await loadInviteCodes();
      setStatus("Loaded");
    }

    function collect() {
      const llmProfile = activeProfile("llm");
      const llmModel = activeModel("llm");
      const embeddingProfile = activeProfile("embedding");
      const embeddingModel = activeModel("embedding");
      const searchProfile = activeProfile("search");
      const rag = settings.runtime.rag;
      const parser = settings.runtime.parser;
      const parserProfiles = settings.runtime.parser_profiles || { profiles: [] };
      const quality = qualityProfile();
      const pack = activePack();
      llmProfile.binding = el.llmBinding.value.trim();
      llmModel.model = el.llmModel.value.trim();
      llmProfile.base_url = el.llmBaseUrl.value.trim();
      if (el.llmApiKey.value.trim()) llmProfile.api_key = el.llmApiKey.value.trim();
      embeddingProfile.binding = el.embeddingBinding.value.trim();
      embeddingModel.model = el.embeddingModel.value.trim();
      embeddingProfile.base_url = el.embeddingBaseUrl.value.trim();
      if (el.embeddingApiKey.value.trim()) embeddingProfile.api_key = el.embeddingApiKey.value.trim();
      rag.chunk_max_chars = Number(el.ragChunkMaxChars.value || 512);
      rag.chunk_overlap = Number(el.ragChunkOverlap.value || 0);
      rag.top_k_candidates = Number(el.ragTopK.value || 14);
      rag.per_query_limit = Number(el.ragPerQuery.value || 2);
      rag.mnemonic_limit = Number(el.ragMnemonicLimit.value || 6);
      searchProfile.provider = el.searchProvider.value;
      searchProfile.max_results = Number(el.searchMaxResults.value || 5);
      searchProfile.base_url = el.searchBaseUrl.value.trim();
      if (el.searchApiKey.value.trim()) searchProfile.api_key = el.searchApiKey.value.trim();
      parserProfiles.default_profile_id = el.defaultParserProfileId.value;
      parser.backend = el.parserBackend.value;
      parser.ocr = el.parserOcr.checked;
      parser.tables = el.parserTables.checked;
      parser.formulas = el.parserFormulas.checked;
      parser.mineru = parser.mineru || {};
      parser.mineru.mode = el.mineruMode.value;
      parser.mineru.api_base_url = el.mineruApiBaseUrl.value.trim();
      if (el.mineruApiToken.value.trim()) parser.mineru.api_token = el.mineruApiToken.value.trim();
      quality.enabled = el.qualityEnabled.checked;
      quality.visible_to_users = el.qualityVisibleToUsers.checked;
      settings.content_pack.default_scenario_id = el.defaultScenarioId.value;
      pack.name = el.packName.value.trim();
      pack.subject = el.packSubject.value.trim();
      pack.enabled = el.packEnabled.value === "true";
      pack.soul_path = el.packSoulPath.value.trim();
      pack.mnemonics_path = el.packMnemonicsPath.value.trim();
      pack.mnemonics_json_path = el.packMnemonicsJsonPath.value.trim();
      settings.mnemonics = JSON.parse(el.mnemonicsJson.value || "{\"version\":1,\"items\":[]}");
      return settings;
    }

    async function save() {
      setStatus("Saving...");
      const response = await fetch(apiPath("/api/admin/settings"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collect())
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
      settings = payload;
      render();
      setStatus("Saved");
    }

    async function runTest(service) {
      diagnostics.textContent = `Running ${service} diagnostics...`;
      const response = await fetch(apiPath(`/api/admin/settings/test/${service}`), { method: "POST" });
      const payload = await response.json();
      diagnostics.textContent = JSON.stringify(payload, null, 2);
    }

    document.getElementById("reloadBtn").addEventListener("click", () => load().catch(err => setStatus(err.message, true)));
    document.getElementById("saveBtn").addEventListener("click", () => save().catch(err => setStatus(err.message, true)));
    document.getElementById("createInviteBtn").addEventListener("click", () => createInviteCode().catch(err => setStatus(err.message, true)));
    document.getElementById("reloadInvitesBtn").addEventListener("click", () => loadInviteCodes().catch(err => setStatus(err.message, true)));
    inviteCodes.addEventListener("click", event => {
      const toggle = event.target.closest("[data-invite-toggle]");
      if (toggle) {
        setInviteEnabled(toggle.dataset.inviteToggle, toggle.dataset.nextEnabled === "true")
          .catch(err => setStatus(err.message, true));
        return;
      }
      const uses = event.target.closest("[data-invite-uses]");
      if (uses) {
        loadInviteUses(uses.dataset.inviteUses).catch(err => setStatus(err.message, true));
      }
    });
    document.querySelectorAll("[data-test]").forEach(button => {
      button.addEventListener("click", () => runTest(button.dataset.test).catch(err => {
        diagnostics.textContent = err.message;
      }));
    });
    load().catch(err => setStatus(err.message, true));
  </script>
</body>
</html>
"""
