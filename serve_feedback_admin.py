from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse

PROJECT_ROOT = Path(__file__).resolve().parent
FEEDBACK_DIR = PROJECT_ROOT / "web_jobs" / "feedback"
ADMIN_TOKEN_ENV = "JSTUDY_ADMIN_TOKEN"

ADMIN_FEEDBACK_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>J-Study 反馈日志</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root { --bg: #f5f6f7; --surface: #fff; --border: #d0d6e0; --border-light: #e6e6e6; --text: #171717; --text-secondary: #6b7280; --text-muted: #9ca3af; --accent: #5e6ad2; --success: #10b981; --warn: #dc2626; }
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;padding:28px 32px}
h1{font-size:20px;font-weight:600;letter-spacing:-.3px;margin-bottom:4px}
.sub{font-size:13px;color:var(--text-secondary);margin-bottom:20px}
.stats{display:flex;gap:16px;margin-bottom:20px}
.stat{background:var(--surface);border:1px solid var(--border-light);border-radius:8px;padding:14px 20px;flex:1}
.stat-num{font-size:26px;font-weight:700;line-height:1.2}
.stat-label{font-size:12px;color:var(--text-secondary);margin-top:2px}
.filters{display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap}
.filters select,.filters input{padding:7px 10px;border:1px solid var(--border);border-radius:6px;font-size:13px;font-family:inherit;background:var(--surface)}
.filters select:focus,.filters input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px #eef0ff}
table{width:100%;border-collapse:collapse;background:var(--surface);border:1px solid var(--border-light);border-radius:8px;overflow:hidden;font-size:13px}
th{text-align:left;padding:10px 12px;background:#f0f1f3;font-weight:600;color:var(--text-secondary);font-size:12px;white-space:nowrap;border-bottom:1px solid var(--border-light)}
td{padding:9px 12px;border-top:1px solid var(--border-light);vertical-align:top;line-height:1.5}
tr:hover td{background:#fafbfc}
.rating-up{font-weight:600;color:var(--success)}
.rating-down{font-weight:600;color:var(--warn)}
.comment{color:var(--text-secondary);max-width:340px;word-break:break-word}
.empty{text-align:center;padding:40px;color:var(--text-muted)}
.refresh{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border:1px solid var(--accent);border-radius:6px;background:var(--accent);color:#fff;font-size:13px;font-weight:500;cursor:pointer;font-family:inherit;margin-left:auto}
.refresh:hover{opacity:.9}
.flex-row{display:flex;align-items:center;gap:16px;margin-bottom:16px}
.job-id{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-muted)}
</style>
</head>
<body>
<h1>📋 J-Study 反馈日志</h1>
<div class="sub">管理员查看用户反馈</div>
<div class="stats" id="stats">
  <div class="stat"><div class="stat-num" id="totalCount">-</div><div class="stat-label">总反馈</div></div>
  <div class="stat"><div class="stat-num" style="color:var(--success)" id="upCount">-</div><div class="stat-label">👍 有帮助</div></div>
  <div class="stat"><div class="stat-num" style="color:var(--warn)" id="downCount">-</div><div class="stat-label">👎 不太行</div></div>
  <div class="stat"><div class="stat-num" id="scenarioBreakdown">-</div><div class="stat-label">学科分布</div></div>
</div>
<div class="flex-row">
  <div class="filters">
    <select id="filterRating"><option value="all">评分: 全部</option><option value="up">👍 有帮助</option><option value="down">👎 不太行</option></select>
    <select id="filterScenario"><option value="all">学科: 全部</option></select>
    <input id="filterSearch" type="text" placeholder="搜索评论..." style="width:200px">
  </div>
  <button class="refresh" id="refreshBtn">🔄 刷新</button>
</div>
<table>
<thead><tr>
  <th>时间</th><th>用户</th><th>学科</th><th>模式</th><th>评分</th><th>评论</th><th>Job</th>
</tr></thead>
<tbody id="tableBody"><tr><td class="empty" colspan="7">加载中...</td></tr></tbody>
</table>

<script>
let allEntries = [];
async function load() {
  const params = new URLSearchParams({ limit: '500', rating: document.getElementById('filterRating').value, scenario: document.getElementById('filterScenario').value });
  const tok = window.location.search.match(/[?&]admin_token=([^&]+)/);
  const url = '/api/feedback?' + (tok ? 'admin_token=' + tok[1] + '&' : '') + params;
  try {
    const res = await fetch(url);
    if (!res.ok) { document.getElementById('tableBody').innerHTML = '<tr><td class="empty" colspan="7">认证失败 — 需要 admin_token</td></tr>'; return; }
    const data = await res.json();
    allEntries = data.entries || [];
    document.getElementById('totalCount').textContent = data.total;
    document.getElementById('upCount').textContent = data.up_count;
    document.getElementById('downCount').textContent = data.down_count;
    document.getElementById('scenarioBreakdown').textContent = (data.scenarios || []).join(', ') || '-';
    // populate scenario filter
    const sel = document.getElementById('filterScenario');
    const currentVal = sel.value;
    sel.innerHTML = '<option value="all">学科: 全部</option>' + (data.scenarios || []).map(s => `<option value="${s}">${s}</option>`).join('');
    sel.value = currentVal;
    // render rows
    const search = document.getElementById('filterSearch').value.toLowerCase();
    const rows = allEntries.filter(e => !search || (e.comment || '').toLowerCase().includes(search)).map(e => {
      const time = e.created_at ? e.created_at.replace('T',' ').slice(0,16) : '-';
      const rating = e.rating === 'up' ? '<span class="rating-up">👍 有帮助</span>' : '<span class="rating-down">👎 不太行</span>';
      return `<tr>
        <td style="white-space:nowrap">${time}</td>
        <td>${esc(e.user_email || e.user_id || '-')}</td>
        <td>${esc(e.scenario_id || '-')}</td>
        <td>${esc(e.mode || '-')}</td>
        <td>${rating}</td>
        <td class="comment">${esc(e.comment || '')}</td>
        <td><span class="job-id">${esc(e.job_id || '').slice(0,12)}</span></td>
      </tr>`;
    }).join('');
    document.getElementById('tableBody').innerHTML = rows || '<tr><td class="empty" colspan="7">暂无反馈</td></tr>';
  } catch(e) { document.getElementById('tableBody').innerHTML = '<tr><td class="empty" colspan="7">请求失败: ' + esc(e.message) + '</td></tr>'; }
}
function esc(s) { const d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }
document.getElementById('filterRating').onchange = load;
document.getElementById('filterScenario').onchange = load;
document.getElementById('filterSearch').oninput = load;
document.getElementById('refreshBtn').onclick = load;
load();
</script>
</body>
</html>
"""

app = FastAPI(title="J-Study Feedback Admin")


def require_token(request: Request) -> None:
    expected = os.getenv(ADMIN_TOKEN_ENV, "").strip()
    if not expected:
        return
    auth = request.headers.get("authorization", "").strip()
    bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    query = request.query_params.get("admin_token", "").strip()
    if expected not in {bearer, query}:
        raise HTTPException(status_code=401, detail="Admin token required")


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> str:
    require_token(request)
    return ADMIN_FEEDBACK_HTML


@app.get("/api/feedback")
def list_feedback(
    request: Request,
    limit: int = 200,
    rating: str = "all",
    scenario: str = "all",
) -> dict:
    require_token(request)
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

    entries = []
    for f in sorted(FEEDBACK_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            entry = json.loads(f.read_text())
            entry["_filename"] = f.name
            entries.append(entry)
        except (json.JSONDecodeError, OSError):
            continue

    if rating != "all":
        entries = [e for e in entries if e.get("rating") == rating]
    if scenario != "all":
        entries = [e for e in entries if (e.get("scenario_id") or "").startswith(scenario)]

    up_count = sum(1 for e in entries if e.get("rating") == "up")
    down_count = sum(1 for e in entries if e.get("rating") == "down")
    scenarios = sorted({e.get("scenario_id", "") for e in entries if e.get("scenario_id")})

    return {
        "total": len(entries),
        "up_count": up_count,
        "down_count": down_count,
        "scenarios": scenarios,
        "entries": entries[:limit],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8888)
