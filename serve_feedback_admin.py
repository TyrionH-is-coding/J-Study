from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

PROJECT_ROOT = Path(__file__).resolve().parent
FEEDBACK_DIR = PROJECT_ROOT / "web_jobs" / "feedback"
JOBS_ROOT = PROJECT_ROOT / "web_jobs"
JOBS_JSON = JOBS_ROOT / "jobs.json"
ADMIN_TOKEN_ENV = "JSTUDY_ADMIN_TOKEN"

# ── helpers ──────────────────────────────────────────────────────────────────

def require_token(request: Request) -> None:
    expected = os.getenv(ADMIN_TOKEN_ENV, "").strip()
    if not expected:
        return
    auth = request.headers.get("authorization", "").strip()
    bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    query = request.query_params.get("admin_token", "").strip()
    if expected not in {bearer, query}:
        raise HTTPException(status_code=401, detail="Admin token required")


def read_json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def list_feedback_for_job(job_id: str) -> list[dict]:
    entries: list[dict] = []
    for f in sorted(FEEDBACK_DIR.glob(f"feedback_{job_id}_*.json"),
                    key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            entries.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return entries


def list_all_jobs() -> list[dict]:
    """Read jobs.json, enrich with trace quality and feedback."""
    payload = read_json(JOBS_JSON)
    if not payload or not isinstance(payload, dict):
        return []
    raw_jobs: list[dict] = payload.get("jobs", [])
    enriched: list[dict] = []
    for job in raw_jobs:
        job_id = job.get("job_id", "")
        output_dir = JOBS_ROOT / job_id / "output"

        trace = read_json(output_dir / "result-retrieval_trace.json") or {}
        quality = read_json(output_dir / "result-quality.json") or {}
        feedback = list_feedback_for_job(job_id)

        created = job.get("created_at", "")
        updated = job.get("updated_at", "")
        duration = ""
        if created and updated:
            try:
                c = datetime.fromisoformat(created)
                u = datetime.fromisoformat(updated)
                secs = int((u - c).total_seconds())
                if secs < 60:
                    duration = f"{secs}s"
                elif secs < 3600:
                    duration = f"{secs // 60}m{secs % 60}s"
                else:
                    duration = f"{secs // 3600}h{(secs % 3600) // 60}m"
            except (ValueError, TypeError):
                pass

        enriched.append({
            "job_id": job_id,
            "status": job.get("status", ""),
            "created_at": created,
            "updated_at": updated,
            "duration": duration,
            "error": job.get("error", ""),
            "scenario_id": job.get("metadata", {}).get("scenario", {}).get("resolved_scenario_id", ""),
            "mode": job.get("metadata", {}).get("mode", ""),
            "domain": trace.get("domain", ""),
            "generation_path": trace.get("generation_path", "unknown"),
            "sections": trace.get("sections", []),
            "chat_model": trace.get("chat_model", ""),
            "embed_model": trace.get("embed_model", ""),
            "parser_backend": trace.get("parser", {}).get("backend", ""),
            "quality_status": quality.get("status", ""),
            "quality_metrics": quality.get("metrics", {}),
            "quality_issues": quality.get("issues", []),
            "feedback_count": len(feedback),
            "feedback_up": sum(1 for f in feedback if f.get("rating") == "up"),
            "feedback_down": sum(1 for f in feedback if f.get("rating") == "down"),
        })
    enriched.sort(key=lambda j: j.get("created_at", ""), reverse=True)
    return enriched

# ── HTML ─────────────────────────────────────────────────────────────────────

ADMIN_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>J-Study 管理面板</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #f5f6f7; --surface: #fff; --border: #d0d6e0; --border-light: #e6e6e6;
  --text: #171717; --text-secondary: #6b7280; --text-muted: #9ca3af;
  --accent: #5e6ad2; --success: #10b981; --warn: #dc2626; --warn-bg: #fef2f2;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;padding:24px 28px}
h1{font-size:20px;font-weight:600;letter-spacing:-.3px;margin-bottom:4px}
.sub{font-size:13px;color:var(--text-secondary);margin-bottom:20px}

/* Tabs */
.tabs{display:flex;gap:0;margin-bottom:0;border-bottom:2px solid var(--border-light)}
.tab{padding:10px 20px;font-size:13px;font-weight:500;cursor:pointer;border:1px solid transparent;border-bottom:none;border-radius:8px 8px 0 0;color:var(--text-secondary);background:transparent;font-family:inherit;transition:all .15s}
.tab:hover{color:var(--text);background:#f0f1f3}
.tab.active{color:var(--accent);background:var(--surface);border-color:var(--border-light);margin-bottom:-2px;font-weight:600}
.tab-count{display:inline-block;margin-left:6px;padding:0 8px;border-radius:10px;background:var(--border-light);font-size:11px;line-height:18px;color:var(--text-secondary)}
.tab.active .tab-count{background:#eef0ff;color:var(--accent)}

/* Panels */
.panel{display:none;background:var(--surface);border:1px solid var(--border-light);border-top:none;border-radius:0 0 8px 8px;padding:16px}
.panel.active{display:block}

/* Filters */
.filters{display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap}
.filters select,.filters input{padding:7px 10px;border:1px solid var(--border);border-radius:6px;font-size:13px;font-family:inherit;background:var(--surface)}
.filters select:focus,.filters input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px #eef0ff}
.btn{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border:1px solid var(--accent);border-radius:6px;background:var(--accent);color:#fff;font-size:13px;font-weight:500;cursor:pointer;font-family:inherit}
.btn:hover{opacity:.9}
.btn-outline{background:transparent;color:var(--accent)}
.flex-row{display:flex;align-items:center;gap:16px;margin-bottom:14px}

/* Stats bar */
.stats{display:flex;gap:12px;margin-bottom:16px}
.stat{background:var(--surface);border:1px solid var(--border-light);border-radius:8px;padding:12px 18px;flex:1}
.stat-num{font-size:22px;font-weight:700;line-height:1.2}
.stat-label{font-size:12px;color:var(--text-secondary);margin-top:2px}

/* Tables */
.wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:9px 10px;background:#f0f1f3;font-weight:600;color:var(--text-secondary);font-size:12px;white-space:nowrap;border-bottom:1px solid var(--border-light)}
td{padding:8px 10px;border-top:1px solid var(--border-light);vertical-align:top;line-height:1.5}
tr{cursor:pointer}
tr:hover td{background:#fafbfc}
tr.expanded td{background:#f8f9ff}
tr.detail-row td{padding:0;border-top:none}

/* Status badges */
.badge{padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;white-space:nowrap}
.badge-ok{background:#ecfdf5;color:#059669}
.badge-fail{background:var(--warn-bg);color:var(--warn)}
.badge-warn{background:#fffbeb;color:#b45309}
.badge-queued{background:#eef2ff;color:#4f46e5}
.badge-running{background:#e0f2fe;color:#0369a1}
.badge-completed{background:#ecfdf5;color:#059669}
.badge-failed{background:var(--warn-bg);color:var(--warn)}
.badge-path{background:#f0f1f3;color:var(--text-secondary)}

/* Job detail expand */
.detail{padding:14px 18px;background:#f8f9ff;border-top:1px solid var(--border-light)}
.detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
.detail-item{background:var(--surface);border:1px solid var(--border-light);border-radius:6px;padding:10px 14px}
.detail-item h4{font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:4px}
.detail-item .val{font-size:13px;font-weight:500;word-break:break-all}
.detail-item .val.mono{font-family:'JetBrains Mono',monospace;font-size:12px}
.detail-section{background:var(--surface);border:1px solid var(--border-light);border-radius:6px;padding:10px 14px;margin-bottom:8px}
.detail-section h4{font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px}
.issue{font-size:12px;padding:4px 0;border-bottom:1px solid var(--border-light)}
.issue:last-child{border-bottom:none}
.issue-err{color:var(--warn)}
.issue-warn{color:#b45309}
.section-list{display:flex;flex-wrap:wrap;gap:4px}
.section-tag{padding:2px 8px;border-radius:4px;background:#eef2ff;color:var(--accent);font-size:11px;font-weight:500;font-family:'JetBrains Mono',monospace}
.feedback-item{padding:8px 0;border-bottom:1px solid var(--border-light);font-size:13px}
.feedback-item:last-child{border-bottom:none}
.feedback-meta{font-size:11px;color:var(--text-muted);margin-top:2px}

/* Misc */
.empty{text-align:center;padding:40px;color:var(--text-muted)}
.job-id{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-muted)}
</style>
</head>
<body>
<h1>📊 J-Study 管理面板</h1>
<div class="sub">管理员视图 — 作业详情 &amp; 用户反馈</div>

<div class="tabs" id="tabs">
  <div class="tab active" data-tab="jobs">📋 作业<span class="tab-count" id="jobCount">-</span></div>
  <div class="tab" data-tab="feedback">💬 反馈<span class="tab-count" id="feedbackCount">-</span></div>
</div>

<div class="panel active" id="panel-jobs">
  <div class="stats" id="jobStats">
    <div class="stat"><div class="stat-num" id="jTotal">-</div><div class="stat-label">总作业</div></div>
    <div class="stat"><div class="stat-num" style="color:var(--success)" id="jCompleted">-</div><div class="stat-label">已完成</div></div>
    <div class="stat"><div class="stat-num" style="color:var(--warn)" id="jFailed">-</div><div class="stat-label">失败</div></div>
    <div class="stat"><div class="stat-num" style="color:var(--accent)" id="jSectional">-</div><div class="stat-label">多轮生成</div></div>
  </div>
  <div class="flex-row">
    <div class="filters">
      <select id="jFilterStatus"><option value="all">状态: 全部</option></select>
      <select id="jFilterPath"><option value="all">路径: 全部</option><option value="single-pass">single-pass</option><option value="sectional-outline">sectional-outline</option><option value="sectional-inferred">sectional-inferred</option></select>
      <select id="jFilterScenario"><option value="all">学科: 全部</option></select>
    </div>
    <button class="btn" id="jRefreshBtn">🔄 刷新</button>
  </div>
  <div class="wrap">
    <table>
      <thead><tr>
        <th>Job</th><th>状态</th><th>路径</th><th>章节</th><th>学科</th><th>耗时</th><th>质量</th><th>反馈</th><th>创建时间</th>
      </tr></thead>
      <tbody id="jTableBody"><tr><td class="empty" colspan="9">加载中...</td></tr></tbody>
    </table>
  </div>
</div>

<div class="panel" id="panel-feedback">
  <div class="stats" id="feedbackStats">
    <div class="stat"><div class="stat-num" id="fTotal">-</div><div class="stat-label">总反馈</div></div>
    <div class="stat"><div class="stat-num" style="color:var(--success)" id="fUp">-</div><div class="stat-label">👍 有帮助</div></div>
    <div class="stat"><div class="stat-num" style="color:var(--warn)" id="fDown">-</div><div class="stat-label">👎 不太行</div></div>
    <div class="stat"><div class="stat-num" id="fScenarios">-</div><div class="stat-label">学科分布</div></div>
  </div>
  <div class="flex-row">
    <div class="filters">
      <select id="fFilterRating"><option value="all">评分: 全部</option><option value="up">👍 有帮助</option><option value="down">👎 不太行</option></select>
      <select id="fFilterScenario"><option value="all">学科: 全部</option></select>
      <input id="fSearch" type="text" placeholder="搜索评论..." style="width:200px">
    </div>
    <button class="btn" id="fRefreshBtn">🔄 刷新</button>
  </div>
  <div class="wrap">
    <table>
      <thead><tr>
        <th>时间</th><th>用户</th><th>学科</th><th>模式</th><th>评分</th><th>评论</th><th>Job</th>
      </tr></thead>
      <tbody id="fTableBody"><tr><td class="empty" colspan="7">加载中...</td></tr></tbody>
    </table>
  </div>
</div>

<script>
// ── helpers ──
function esc(s) { const d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }
function toBeijing(iso) {
  try { const d=new Date(iso); return d.toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}).replace(/\//g,'-'); }
  catch { return iso?iso.replace('T',' ').slice(0,16):'-'; }
}
function qs(p) { return '?admin_token='+tok()+'&'+p; }
function tok() { const m=window.location.search.match(/[?&]admin_token=([^&]+)/); return m?m[1]:''; }
function el(id) { return document.getElementById(id); }

// ── tabs ──
document.querySelectorAll('.tab').forEach(tab => {
  tab.onclick = () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    el('panel-'+tab.dataset.tab).classList.add('active');
  };
});

// ── JOBS ──
let allJobs = [];
async function loadJobs() {
  try {
    const res = await fetch('/api/admin/jobs?'+qs(''));
    if (!res.ok) { el('jTableBody').innerHTML='<tr><td class="empty" colspan="9">认证失败</td></tr>'; return; }
    const data = await res.json();
    allJobs = data.jobs || [];

    // Stats
    const total = allJobs.length;
    const completed = allJobs.filter(j=>j.status==='completed').length;
    const failed = allJobs.filter(j=>j.status==='failed').length;
    const sectional = allJobs.filter(j=>j.generation_path && j.generation_path !== 'single-pass' && j.generation_path !== 'unknown').length;
    el('jTotal').textContent = total;
    el('jCompleted').textContent = completed;
    el('jFailed').textContent = failed;
    el('jSectional').textContent = sectional;
    el('jobCount').textContent = total;

    // Populate status filter
    const statuses = [...new Set(allJobs.map(j=>j.status))].sort();
    const sf = el('jFilterStatus');
    const curSf = sf.value;
    sf.innerHTML = '<option value="all">状态: 全部</option>'+statuses.map(s=>`<option value="${s}">${s}</option>`).join('');
    sf.value = curSf;

    // Populate scenario filter
    const scenarios = [...new Set(allJobs.map(j=>j.scenario_id).filter(Boolean))].sort();
    const scf = el('jFilterScenario');
    const curScf = scf.value;
    scf.innerHTML = '<option value="all">学科: 全部</option>'+scenarios.map(s=>`<option value="${s}">${s}</option>`).join('');
    scf.value = curScf;

    renderJobs();
  } catch(e) { el('jTableBody').innerHTML='<tr><td class="empty" colspan="9">请求失败: '+esc(e.message)+'</td></tr>'; }
}

function renderJobs() {
  const statusF = el('jFilterStatus').value;
  const pathF = el('jFilterPath').value;
  const scenarioF = el('jFilterScenario').value;

  let filtered = allJobs;
  if (statusF !== 'all') filtered = filtered.filter(j=>j.status===statusF);
  if (pathF !== 'all') filtered = filtered.filter(j=>j.generation_path===pathF);
  if (scenarioF !== 'all') filtered = filtered.filter(j=>j.scenario_id===scenarioF);

  el('jTableBody').innerHTML = filtered.map(j => {
    const statusBadge = statusClass(j.status);
    const pathBadge = j.generation_path && j.generation_path !== 'unknown'
      ? `<span class="badge badge-path">${esc(j.generation_path)}</span>` : '-';
    const sections = (j.sections||[]);
    const sectionsDisplay = sections.length
      ? `<span class="badge badge-ok" title="${esc(sections.join(', '))}">${sections.length}节</span>`
      : '-';
    const qualityBadge = j.quality_status === 'pass'
      ? `<span class="badge badge-ok">pass</span>`
      : j.quality_status === 'fail'
        ? `<span class="badge badge-fail">fail</span>`
        : '-';
    const feedbackCount = j.feedback_count || 0;
    const fbDisplay = feedbackCount
      ? (j.feedback_up ? '👍'+j.feedback_up : '')+(j.feedback_down ? ' 👎'+j.feedback_down : '')
      : '-';
    const errorHint = j.status === 'failed' ? ` title="${esc(j.error)}"` : '';

    return `<tr onclick="toggleJob('${j.job_id}')" data-jid="${j.job_id}">
      <td><span class="job-id">${esc(j.job_id).slice(0,12)}</span></td>
      <td><span class="badge badge-${statusClass(j.status)}"${errorHint}>${esc(j.status)}</span></td>
      <td>${pathBadge}</td>
      <td>${sectionsDisplay}</td>
      <td>${esc(j.scenario_id||'-')}</td>
      <td>${esc(j.duration||'-')}</td>
      <td>${qualityBadge}</td>
      <td>${fbDisplay}</td>
      <td style="white-space:nowrap;font-size:12px;color:var(--text-muted)">${toBeijing(j.created_at)}</td>
    </tr><tr class="detail-row" id="detail-${j.job_id}" style="display:none"><td colspan="9"><div class="detail" id="detailContent-${j.job_id}">加载中...</div></td></tr>`;
  }).join('') || '<tr><td class="empty" colspan="9">暂无作业</td></tr>';
}

function statusClass(s) {
  if (s==='completed') return 'completed';
  if (s==='failed') return 'failed';
  if (s==='running') return 'running';
  if (s==='queued') return 'queued';
  return 'warn';
}

let openDetail = null;
async function toggleJob(jobId) {
  const row = document.getElementById('detail-'+jobId);
  if (openDetail && openDetail !== jobId) {
    const prev = document.getElementById('detail-'+openDetail);
    if (prev) prev.style.display = 'none';
  }
  if (row.style.display === 'table-row') {
    row.style.display = 'none';
    openDetail = null;
    return;
  }
  row.style.display = 'table-row';
  openDetail = jobId;
  const content = document.getElementById('detailContent-'+jobId);

  try {
    const res = await fetch('/api/admin/jobs/'+jobId+'?'+qs(''));
    if (!res.ok) { content.innerHTML = '<div class="empty">加载失败</div>'; return; }
    const j = await res.json();
    const sections = (j.sections||[]);
    const issues = (j.quality_issues||[]);
    const feedback = (j.feedback||[]);
    const metrics = j.quality_metrics||{};

    content.innerHTML = `
    <div class="detail-grid">
      <div class="detail-item">
        <h4>Job ID</h4>
        <div class="val mono">${esc(j.job_id)}</div>
      </div>
      <div class="detail-item">
        <h4>状态</h4>
        <div class="val"><span class="badge badge-${statusClass(j.status)}">${esc(j.status)}</span></div>
      </div>
      <div class="detail-item">
        <h4>生成路径</h4>
        <div class="val"><span class="badge badge-path">${esc(j.generation_path)}</span></div>
      </div>
      <div class="detail-item">
        <h4>学科 / 模式</h4>
        <div class="val">${esc(j.scenario_id||'-')} / ${esc(j.mode||'-')}</div>
      </div>
      <div class="detail-item">
        <h4>模型</h4>
        <div class="val mono" style="font-size:12px">chat: ${esc(j.chat_model||'-')}<br>embed: ${esc(j.embed_model||'-')}</div>
      </div>
      <div class="detail-item">
        <h4>解析器</h4>
        <div class="val mono">${esc(j.parser_backend||'-')}</div>
      </div>
      <div class="detail-item">
        <h4>创建 / 耗时</h4>
        <div class="val" style="font-size:12px">${toBeijing(j.created_at)}<br>${esc(j.duration||'-')}</div>
      </div>
      <div class="detail-item">
        <h4>错误</h4>
        <div class="val mono" style="font-size:12px;color:var(--warn)">${esc(j.error||'-')}</div>
      </div>
    </div>

    <div class="detail-section">
      <h4>📑 章节 (${sections.length})</h4>
      ${sections.length
        ? `<div class="section-list">${sections.map(s=>`<span class="section-tag">${esc(s)}</span>`).join('')}</div>`
        : '<span style="font-size:13px;color:var(--text-muted)">单次生成，无章节划分</span>'}
    </div>

    <div class="detail-section">
      <h4>✅ 质量审计</h4>
      <div style="display:flex;gap:16px;margin-bottom:6px">
        <span style="font-size:13px">状态: <span class="badge badge-${metrics.evidence_count ? (j.quality_status==='pass'?'ok':'fail') : 'warn'}">${esc(j.quality_status||'N/A')}</span></span>
        <span style="font-size:13px;color:var(--text-secondary)">证据: ${metrics.evidence_count||0} 引用: ${metrics.referenced_evidence_count||0}</span>
        <span style="font-size:13px;color:var(--text-secondary)">章节覆盖率: ${Math.round((metrics.section_citation_coverage||0)*100)}%</span>
        <span style="font-size:13px;color:var(--text-secondary)">问题: ${metrics.issue_count||0}</span>
      </div>
      ${issues.length ? `<div style="margin-top:4px">${issues.map(i => `<div class="issue issue-${i.severity==='error'?'err':'warn'}">⚠ ${esc(i.message)}${i.sections ? ' ('+esc(i.sections.join(', '))+')' : ''}${i.ids ? ' IDs: '+esc(i.ids.join(', ')) : ''}</div>`).join('')}</div>` : ''}
    </div>

    ${feedback.length ? `<div class="detail-section">
      <h4>💬 反馈 (${feedback.length})</h4>
      ${feedback.map(f => `
        <div class="feedback-item">
          <div>${f.rating === 'up' ? '👍' : '👎'} ${esc(f.comment||'(无评论)')}</div>
          <div class="feedback-meta">${esc(f.user_email||f.user_id||'')} · ${toBeijing(f.created_at)}</div>
        </div>
      `).join('')}
    </div>` : ''}
    `;
  } catch(e) { content.innerHTML = '<div class="empty">加载失败: '+esc(e.message)+'</div>'; }
}

// ── FEEDBACK ──
let allFeedbacks = [];
async function loadFeedback() {
  try {
    const params = new URLSearchParams({ limit: '500', rating: el('fFilterRating').value, scenario: el('fFilterScenario').value });
    const res = await fetch('/api/feedback?'+params+'&'+qs(''));
    if (!res.ok) { el('fTableBody').innerHTML='<tr><td class="empty" colspan="7">认证失败</td></tr>'; return; }
    const data = await res.json();
    allFeedbacks = data.entries || [];
    el('fTotal').textContent = data.total;
    el('fUp').textContent = data.up_count;
    el('fDown').textContent = data.down_count;
    el('fScenarios').textContent = (data.scenarios||[]).join(', ') || '-';
    el('feedbackCount').textContent = data.total;

    const sel = el('fFilterScenario');
    const curVal = sel.value;
    sel.innerHTML = '<option value="all">学科: 全部</option>' + (data.scenarios||[]).map(s => `<option value="${s}">${s}</option>`).join('');
    sel.value = curVal;

    renderFeedback();
  } catch(e) { el('fTableBody').innerHTML='<tr><td class="empty" colspan="7">请求失败</td></tr>'; }
}

function renderFeedback() {
  const search = el('fSearch').value.toLowerCase();
  const filtered = allFeedbacks.filter(e => !search || (e.comment||'').toLowerCase().includes(search));
  el('fTableBody').innerHTML = filtered.map(e => {
    const rating = e.rating === 'up' ? '<span style="font-weight:600;color:var(--success)">👍 有帮助</span>' : '<span style="font-weight:600;color:var(--warn)">👎 不太行</span>';
    return `<tr onclick="document.querySelector('[data-tab=jobs]').click();el('jFilterPath').value='all';loadJobs();setTimeout(()=>toggleJob('${esc(e.job_id||'')}'),200)">
      <td style="white-space:nowrap">${toBeijing(e.created_at)}</td>
      <td>${esc(e.user_email||e.user_id||'-')}</td>
      <td>${esc(e.scenario_id||'-')}</td>
      <td>${esc(e.mode||'-')}</td>
      <td>${rating}</td>
      <td style="max-width:340px;word-break:break-word;color:var(--text-secondary)">${esc(e.comment||'')}</td>
      <td><span class="job-id">${esc(e.job_id||'').slice(0,12)}</span></td>
    </tr>`;
  }).join('') || '<tr><td class="empty" colspan="7">暂无反馈</td></tr>';
}

// ── init ──
el('jFilterStatus').onchange = renderJobs;
el('jFilterPath').onchange = renderJobs;
el('jFilterScenario').onchange = renderJobs;
el('jRefreshBtn').onclick = loadJobs;
el('fFilterRating').onchange = loadFeedback;
el('fFilterScenario').onchange = loadFeedback;
el('fSearch').oninput = renderFeedback;
el('fRefreshBtn').onclick = loadFeedback;

loadJobs();
loadFeedback();
</script>
</body>
</html>
"""

# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(title="J-Study Admin Panel")


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> str:
    require_token(request)
    return ADMIN_HTML


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


@app.get("/api/admin/jobs")
def list_jobs(request: Request) -> dict:
    require_token(request)
    jobs = list_all_jobs()
    return {"total": len(jobs), "jobs": jobs}


@app.get("/api/admin/jobs/{job_id}")
def get_job_detail(job_id: str, request: Request) -> dict:
    require_token(request)
    jobs = list_all_jobs()
    for j in jobs:
        if j["job_id"] == job_id:
            output_dir = JOBS_ROOT / job_id / "output"
            trace = read_json(output_dir / "result-retrieval_trace.json") or {}
            quality = read_json(output_dir / "result-quality.json") or {}
            feedback = list_feedback_for_job(job_id)
            j["feedback"] = feedback
            j["trace_detail"] = {
                "study_queries": trace.get("study_queries", []),
                "selected_chunks": len(trace.get("selected_chunks", [])),
                "mnemonic_hits": len(trace.get("mnemonic_hits", [])),
            }
            return j
    raise HTTPException(status_code=404, detail="Job not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8888)
