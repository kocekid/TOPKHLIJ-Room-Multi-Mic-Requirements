#!/usr/bin/env python3
import argparse
import base64
import binascii
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HOST = "127.0.0.1"
PORT = 8765
TOOL_PATH = "/Users/mac/bin/gh-doc-publish"
APP_TITLE = "GitHub 文档原型发布台"


def configure_stdio_utf8():
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


configure_stdio_utf8()


def utf8_subprocess_env(extra: dict | None = None):
    env = os.environ.copy()
    env.setdefault("LANG", "zh_CN.UTF-8")
    env.setdefault("LC_CTYPE", env.get("LANG", "zh_CN.UTF-8"))
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PATH", "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin")
    if extra:
        env.update(extra)
    return env

INDEX_HTML = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GitHub 文档原型发布台</title>
  <style>
    :root {
      --bg: #0a0d14;
      --panel: rgba(18, 24, 38, 0.92);
      --panel-2: rgba(11, 16, 28, 0.88);
      --line: rgba(139, 152, 178, 0.18);
      --line-strong: rgba(139, 152, 178, 0.34);
      --text: #eef3ff;
      --muted: #96a3c2;
      --accent: #63e6be;
      --accent-2: #7aa2ff;
      --danger: #ff7a90;
      --warning: #ffd36e;
      --shadow: 0 24px 80px rgba(0, 0, 0, 0.38);
      --radius: 18px;
      --radius-sm: 12px;
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      --sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }
    html, body { margin: 0; min-height: 100%; }
    body {
      font-family: var(--sans);
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(99, 230, 190, 0.14), transparent 24%),
        radial-gradient(circle at top right, rgba(122, 162, 255, 0.15), transparent 28%),
        linear-gradient(180deg, #0b0f18 0%, #090c12 100%);
    }

    .shell {
      width: min(1120px, calc(100vw - 32px));
      margin: 24px auto 48px;
      display: grid;
      gap: 16px;
    }

    .topbar, .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      backdrop-filter: blur(14px);
    }

    .topbar {
      padding: 18px 20px;
      display: grid;
      gap: 12px;
    }

    .eyebrow {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }

    .eyebrow strong {
      font-size: 18px;
      letter-spacing: 0.02em;
    }

    .subtitle {
      color: var(--muted);
      font-size: 14px;
      line-height: 1.6;
    }

    .status-row {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.03);
      color: var(--muted);
      font-size: 13px;
    }

    .badge.ok { color: var(--accent); border-color: rgba(99, 230, 190, 0.25); }
    .badge.warn { color: var(--warning); border-color: rgba(255, 211, 110, 0.25); }

    .grid {
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 16px;
    }

    .panel {
      padding: 18px;
    }

    .panel h2 {
      margin: 0 0 14px;
      font-size: 16px;
      letter-spacing: 0.02em;
    }

    .form-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }

    .full { grid-column: 1 / -1; }

    label {
      display: grid;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
    }

    input[type="text"], textarea {
      width: 100%;
      border: 1px solid var(--line);
      background: var(--panel-2);
      color: var(--text);
      border-radius: 14px;
      padding: 13px 14px;
      outline: none;
      font: inherit;
      transition: border-color .18s ease, transform .18s ease;
    }

    select {
      width: 100%;
      border: 1px solid var(--line);
      background: var(--panel-2);
      color: var(--text);
      border-radius: 14px;
      padding: 13px 14px;
      outline: none;
      font: inherit;
      transition: border-color .18s ease, transform .18s ease;
    }

    input[type="text"]:focus, textarea:focus, select:focus {
      border-color: rgba(122, 162, 255, 0.55);
      transform: translateY(-1px);
    }

    textarea {
      min-height: 88px;
      resize: vertical;
    }

    textarea[readonly] {
      opacity: 0.96;
    }

    .switch {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      color: var(--text);
      font-size: 14px;
      margin-top: 2px;
    }

    .switch input {
      width: 18px;
      height: 18px;
      accent-color: #7aa2ff;
    }

    .picker-box {
      display: grid;
      gap: 12px;
      padding: 14px;
      border-radius: 16px;
      border: 1px dashed var(--line-strong);
      background: rgba(255, 255, 255, 0.02);
    }

    .picker-actions {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }

    button {
      appearance: none;
      border: 0;
      border-radius: 14px;
      padding: 12px 16px;
      font: inherit;
      font-weight: 700;
      letter-spacing: 0.01em;
      cursor: pointer;
      transition: transform .16s ease, filter .16s ease, opacity .16s ease;
    }

    button:hover { transform: translateY(-1px); filter: brightness(1.04); }
    button:active { transform: translateY(0); }
    button:disabled { cursor: not-allowed; opacity: 0.56; transform: none; }

    .btn-accent { background: linear-gradient(135deg, #63e6be, #7aa2ff); color: #07111e; }
    .btn-soft { background: rgba(255, 255, 255, 0.06); color: var(--text); border: 1px solid var(--line); }
    .btn-danger { background: rgba(255, 122, 144, 0.12); color: var(--danger); border: 1px solid rgba(255, 122, 144, 0.22); }
    .active-mode { border: 1px solid rgba(99, 230, 190, 0.34) !important; color: var(--accent) !important; background: rgba(99, 230, 190, 0.08) !important; }

    .file-meta {
      display: grid;
      gap: 8px;
      color: var(--text);
    }

    .meta-row {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      font-size: 14px;
    }

    .meta-label { color: var(--muted); min-width: 88px; }
    .mono { font-family: var(--mono); font-size: 13px; word-break: break-all; }

    .summary-list {
      display: grid;
      gap: 12px;
    }

    .summary-card {
      padding: 14px;
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--line);
      display: grid;
      gap: 8px;
    }

    .summary-card strong { font-size: 14px; }
    .summary-card small { color: var(--muted); line-height: 1.6; }

    .result-box {
      display: grid;
      gap: 12px;
      min-height: 180px;
    }

    .result-shell {
      border-radius: 16px;
      background: rgba(8, 12, 20, 0.92);
      border: 1px solid var(--line);
      padding: 14px;
      overflow: auto;
      max-height: 560px;
      font-family: var(--mono);
      font-size: 12px;
      line-height: 1.65;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .result-ok { color: #dcfff1; }
    .result-error { color: #ffd8df; }

    .footer-note {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.7;
    }

    [hidden] { display: none !important; }

    @media (max-width: 920px) {
      .grid { grid-template-columns: 1fr; }
      .form-grid { grid-template-columns: 1fr; }
      .shell { width: min(100vw - 20px, 1120px); margin-top: 14px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="topbar">
      <div class="eyebrow">
        <strong>GitHub 文档原型发布台</strong>
        <div class="status-row">
          <span class="badge" id="authBadge">认证状态读取中</span>
          <span class="badge" id="serverBadge">本地服务启动中</span>
        </div>
      </div>
      <div class="subtitle">
        这是一个 Configure 面：干上传，不演戏。你可以新建仓库，也可以先拉取你现有的仓库列表，选一个已有仓库作为更新目标。选一个 Markdown 需求文档，再选一个原型图目录，点一下就替换同步过去。
      </div>
    </section>

    <section class="grid">
      <div class="panel">
        <h2>发布配置</h2>
        <div class="form-grid">
          <label class="full">
            目标模式
            <div class="picker-actions">
              <button class="btn-soft" id="modeCreateBtn" type="button">新建 / 直填仓库</button>
              <button class="btn-soft" id="modeUpdateBtn" type="button">更新已有仓库</button>
              <button class="btn-soft" id="refreshReposBtn" type="button">拉取仓库列表</button>
            </div>
          </label>
          <label class="full" id="repoSelectWrap" hidden>
            已有仓库
            <select id="repoSelect"></select>
          </label>
          <label>
            仓库名
            <input id="repoInput" type="text" placeholder="比如：BD2.0" autocomplete="off" />
          </label>
          <label>
            Owner（可空）
            <input id="ownerInput" type="text" placeholder="默认自动探测" autocomplete="off" />
          </label>
          <label class="full">
            仓库描述（可空）
            <input id="descriptionInput" type="text" placeholder="默认自动生成" autocomplete="off" />
          </label>
          <label class="full">
            提交信息（可空）
            <input id="messageInput" type="text" placeholder="默认自动生成" autocomplete="off" />
          </label>
          <label class="full" id="publicWrap">
            <span class="switch">
              <input id="publicInput" type="checkbox" />
              仓库不存在时按公开仓库创建（默认私有）
            </span>
          </label>
        </div>

        <div style="height:16px"></div>

        <div class="picker-box">
          <div class="picker-actions">
            <button class="btn-soft" id="saveTokenBtn" type="button">保存 GitHub Token</button>
            <button class="btn-soft" id="checkTokenBtn" type="button">检查认证状态</button>
            <button class="btn-soft" id="generateKeyBtn" type="button">生成 SSH 公钥</button>
          </div>
          <div class="form-grid">
            <label class="full">
              GitHub Token（可粘贴后保存到 macOS Keychain）
              <textarea id="tokenInput" placeholder="贴你的 GitHub PAT，至少要有 repo 权限。保存后不会回显。"></textarea>
            </label>
            <label class="full">
              当前 SSH 公钥（复制到 GitHub）
              <textarea id="sshKeyOutput" readonly placeholder="点“生成 SSH 公钥”后，这里会显示可复制的公钥。"></textarea>
            </label>
            <label class="full">
              GitHub Token 获取方法 / 配置公钥方法
              <textarea id="guideOutput" readonly></textarea>
            </label>
          </div>
        </div>

        <div style="height:16px"></div>

        <div class="picker-box">
          <div class="picker-actions">
            <button class="btn-soft" id="pickDocBtn" type="button">选择需求文档</button>
            <button class="btn-soft" id="clearDocBtn" type="button">清空文档</button>
          </div>
          <div class="file-meta" id="docMeta">
            <div class="meta-row"><span class="meta-label">当前文档</span><span>还没选</span></div>
          </div>
        </div>

        <div style="height:14px"></div>

        <div class="picker-box">
          <div class="picker-actions">
            <button class="btn-soft" id="pickAssetsBtn" type="button">选择原型图目录</button>
            <button class="btn-soft" id="clearAssetsBtn" type="button">清空目录</button>
          </div>
          <div class="file-meta" id="assetsMeta">
            <div class="meta-row"><span class="meta-label">当前目录</span><span>还没选</span></div>
          </div>
        </div>

        <div style="height:16px"></div>

        <div class="picker-actions">
          <button class="btn-accent" id="publishBtn" type="button">开始上传到 GitHub</button>
          <button class="btn-danger" id="resetBtn" type="button">清空整页</button>
        </div>

        <div style="height:12px"></div>
        <div class="footer-note">
          文档会先发到本机这个页面背后的本地服务，再由本地服务调用你已经做好的 gh-doc-publish 工具去同步 GitHub。更新已有仓库时，原型图目录可不重传，默认沿用仓库里现有目录。认证优先读 macOS Keychain 里的 token。
        </div>

        <input id="docFallback" type="file" accept=".md,text/markdown" hidden />
        <input id="assetsFallback" type="file" webkitdirectory directory multiple hidden />
      </div>

      <div class="panel">
        <h2>状态与结果</h2>
        <div class="summary-list">
          <div class="summary-card">
            <strong>上传习惯</strong>
            <small>只同步你指定的一个 md，原型图目录按需同步；更新已有仓库时可沿用现有原型图目录，避免把整个项目目录一锅端上传。</small>
          </div>
          <div class="summary-card">
            <strong>校验逻辑</strong>
            <small>后端会在推送前检查 Markdown 图片引用，发现缺图就直接报错，不让烂链接偷偷溜进仓库。</small>
          </div>
        </div>

        <div style="height:16px"></div>
        <div class="result-box">
          <div class="result-shell result-ok" id="resultBox">等你点上传。结果会显示在这。</div>
        </div>
      </div>
    </section>
  </div>

  <script>
    const storageKey = 'gh-doc-publish-h5:v1';
    const state = {
      docFile: null,
      assetsFiles: [],
      assetDirName: '原型图',
      mode: 'create',
      repoOptions: []
    };

    const repoInput = document.getElementById('repoInput');
    const ownerInput = document.getElementById('ownerInput');
    const descriptionInput = document.getElementById('descriptionInput');
    const messageInput = document.getElementById('messageInput');
    const publicInput = document.getElementById('publicInput');
    const authBadge = document.getElementById('authBadge');
    const serverBadge = document.getElementById('serverBadge');
    const docMeta = document.getElementById('docMeta');
    const assetsMeta = document.getElementById('assetsMeta');
    const resultBox = document.getElementById('resultBox');
    const publishBtn = document.getElementById('publishBtn');
    const docFallback = document.getElementById('docFallback');
    const assetsFallback = document.getElementById('assetsFallback');
    const repoSelectWrap = document.getElementById('repoSelectWrap');
    const repoSelect = document.getElementById('repoSelect');
    const publicWrap = document.getElementById('publicWrap');
    const modeCreateBtn = document.getElementById('modeCreateBtn');
    const modeUpdateBtn = document.getElementById('modeUpdateBtn');
    const refreshReposBtn = document.getElementById('refreshReposBtn');
    const tokenInput = document.getElementById('tokenInput');
    const sshKeyOutput = document.getElementById('sshKeyOutput');
    const guideOutput = document.getElementById('guideOutput');
    const saveTokenBtn = document.getElementById('saveTokenBtn');
    const checkTokenBtn = document.getElementById('checkTokenBtn');
    const generateKeyBtn = document.getElementById('generateKeyBtn');

    function saveDraft() {
      const payload = {
        repo: repoInput.value.trim(),
        owner: ownerInput.value.trim(),
        description: descriptionInput.value.trim(),
        message: messageInput.value.trim(),
        isPublic: publicInput.checked,
        mode: state.mode,
        selectedRepo: repoSelect.value || ''
      };
      localStorage.setItem(storageKey, JSON.stringify(payload));
    }

    function loadDraft() {
      try {
        const payload = JSON.parse(localStorage.getItem(storageKey) || '{}');
        repoInput.value = payload.repo || '';
        ownerInput.value = payload.owner || '';
        descriptionInput.value = payload.description || '';
        messageInput.value = payload.message || '';
        publicInput.checked = Boolean(payload.isPublic);
        state.mode = payload.mode || 'create';
        state.savedSelectedRepo = payload.selectedRepo || '';
      } catch (_) {}
    }

    function updateModeUI() {
      const updating = state.mode === 'update';
      repoSelectWrap.hidden = !updating;
      publicWrap.hidden = updating;
      modeCreateBtn.className = `btn-soft${updating ? '' : ' active-mode'}`;
      modeUpdateBtn.className = `btn-soft${updating ? ' active-mode' : ''}`;
      repoInput.readOnly = updating;
      ownerInput.readOnly = updating;
      if (updating) {
        repoInput.placeholder = '从下方已有仓库中选择';
        ownerInput.placeholder = '随仓库自动带出';
      } else {
        repoInput.placeholder = '比如：BD2.0';
        ownerInput.placeholder = '默认自动探测';
      }
      renderAssetsMeta();
    }

    function renderRepoOptions() {
      const current = repoSelect.value || state.savedSelectedRepo || '';
      if (!state.repoOptions.length) {
        repoSelect.innerHTML = '<option value="">还没拉到仓库，先点“拉取仓库列表”</option>';
        return;
      }
      repoSelect.innerHTML = state.repoOptions.map(repo => {
        const value = `${repo.owner}/${repo.name}`;
        const selected = value === current ? ' selected' : '';
        const visibility = repo.private ? '私有' : '公开';
        return `<option value="${escapeHtml(value)}"${selected}>${escapeHtml(value)} · ${visibility}</option>`;
      }).join('');
      if (current) {
        repoSelect.value = current;
      }
      syncSelectedRepo();
    }

    function syncSelectedRepo() {
      if (state.mode !== 'update') return;
      const value = repoSelect.value;
      if (!value) return;
      const found = state.repoOptions.find(item => `${item.owner}/${item.name}` === value);
      if (!found) return;
      repoInput.value = found.name;
      ownerInput.value = found.owner;
      state.savedSelectedRepo = value;
      saveDraft();
    }

    async function refreshRepos(auto=false) {
      try {
        if (!auto) setResult('正在拉取现有仓库列表……', true);
        const owner = ownerInput.value.trim();
        const query = owner ? `?owner=${encodeURIComponent(owner)}` : '';
        const resp = await fetch(`/api/repos${query}`);
        const data = await resp.json();
        if (!resp.ok || !data.ok) throw new Error(data.error || '仓库列表读取失败');
        state.repoOptions = data.repos || [];
        renderRepoOptions();
        if (!auto) setResult(`仓库列表已更新，共 ${state.repoOptions.length} 个。`, true);
      } catch (err) {
        if (!auto) setResult(`拉取仓库列表失败\n\n${err.message || err}`, false);
      }
    }

    async function saveToken() {
      const token = tokenInput.value.trim();
      if (!token) {
        setResult('先把 GitHub token 粘进来。', false);
        return;
      }
      try {
        const resp = await fetch('/api/auth/token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token })
        });
        const data = await resp.json();
        if (!resp.ok || !data.ok) throw new Error(data.error || '保存 token 失败');
        tokenInput.value = '';
        setResult('GitHub token 已保存到 macOS Keychain。', true);
        await refreshStatus();
      } catch (err) {
        setResult(`保存 token 失败\n\n${err.message || err}`, false);
      }
    }

    async function checkAuthStatus() {
      await refreshStatus();
      setResult(`当前认证状态：${authBadge.textContent}`, true);
    }

    async function generateSshKey() {
      try {
        const resp = await fetch('/api/auth/ssh-key', { method: 'POST' });
        const data = await resp.json();
        if (!resp.ok || !data.ok) throw new Error(data.error || '生成 SSH 公钥失败');
        sshKeyOutput.value = data.public_key || '';
        setResult(`SSH 公钥已准备好。私钥路径：${data.private_key_path}\n公钥路径：${data.public_key_path}`, true);
      } catch (err) {
        setResult(`生成 SSH 公钥失败\n\n${err.message || err}`, false);
      }
    }

    function setBadge(el, text, mode='ok') {
      el.textContent = text;
      el.className = `badge ${mode}`;
    }

    function fillGuide() {
      guideOutput.value = [
        'GitHub Token 获取方法：',
        '1. 打开 https://github.com/settings/tokens',
        '2. 选择 Fine-grained token 或 Classic token',
        '3. 如果只是上传/更新仓库，至少给 repo 权限',
        '4. 复制 token，粘到上面的输入框，点“保存 GitHub Token”',
        '',
        'SSH 公钥配置方法：',
        '1. 点“生成 SSH 公钥”',
        '2. 复制显示出来的公钥',
        '3. 打开 https://github.com/settings/keys',
        '4. 点 New SSH key，把公钥粘进去保存',
        '',
        '说明：',
        '- 这个页面上传 GitHub 主要依赖 token',
        '- 公钥主要用于你后续想走 SSH push / git@github.com 时用',
        '- token 会保存进 macOS Keychain，不会明文写在页面里'
      ].join('\n');
    }

    function renderDocMeta() {
      if (!state.docFile) {
        docMeta.innerHTML = '<div class="meta-row"><span class="meta-label">当前文档</span><span>还没选</span></div>';
        return;
      }
      docMeta.innerHTML = `
        <div class="meta-row"><span class="meta-label">文件名</span><span>${escapeHtml(state.docFile.name)}</span></div>
        <div class="meta-row"><span class="meta-label">大小</span><span>${formatBytes(state.docFile.size)}</span></div>
        <div class="meta-row"><span class="meta-label">类型</span><span>${escapeHtml(state.docFile.type || '未知')}</span></div>
      `;
    }

    function renderAssetsMeta() {
      if (!state.assetsFiles.length) {
        const optionalText = state.mode === 'update' ? '还没选（更新模式可留空，沿用仓库现有原型图目录）' : '还没选';
        assetsMeta.innerHTML = `<div class="meta-row"><span class="meta-label">当前目录</span><span>${escapeHtml(optionalText)}</span></div>`;
        return;
      }
      const preview = state.assetsFiles.slice(0, 4).map(item => `<div class="mono">${escapeHtml(item.relativePath)}</div>`).join('');
      assetsMeta.innerHTML = `
        <div class="meta-row"><span class="meta-label">目录名</span><span>${escapeHtml(state.assetDirName)}</span></div>
        <div class="meta-row"><span class="meta-label">文件数</span><span>${state.assetsFiles.length}</span></div>
        <div class="meta-row"><span class="meta-label">示例</span><span></span></div>
        ${preview}
      `;
    }

    function setResult(message, ok=true) {
      resultBox.className = `result-shell ${ok ? 'result-ok' : 'result-error'}`;
      resultBox.textContent = message;
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }

    function formatBytes(bytes) {
      const units = ['B', 'KB', 'MB', 'GB'];
      let value = bytes;
      let index = 0;
      while (value >= 1024 && index < units.length - 1) {
        value /= 1024;
        index += 1;
      }
      return `${value.toFixed(value >= 100 || index === 0 ? 0 : 1)} ${units[index]}`;
    }

    async function toBase64(file) {
      const buffer = await file.arrayBuffer();
      const bytes = new Uint8Array(buffer);
      const chunk = 0x8000;
      let binary = '';
      for (let i = 0; i < bytes.length; i += chunk) {
        binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
      }
      return btoa(binary);
    }

    async function pickDoc() {
      if (window.showOpenFilePicker) {
        try {
          const [handle] = await window.showOpenFilePicker({
            multiple: false,
            types: [{
              description: 'Markdown 文档',
              accept: { 'text/markdown': ['.md'], 'text/plain': ['.md'] }
            }]
          });
          const file = await handle.getFile();
          state.docFile = file;
          renderDocMeta();
          return;
        } catch (err) {
          if (err && err.name === 'AbortError') return;
        }
      }
      docFallback.click();
    }

    async function walkDirectory(dirHandle, prefix='') {
      const files = [];
      for await (const [name, handle] of dirHandle.entries()) {
        if (handle.kind === 'file') {
          const file = await handle.getFile();
          files.push({ file, relativePath: prefix ? `${prefix}/${name}` : name });
        } else if (handle.kind === 'directory') {
          const nested = await walkDirectory(handle, prefix ? `${prefix}/${name}` : name);
          files.push(...nested);
        }
      }
      return files;
    }

    async function pickAssets() {
      if (window.showDirectoryPicker) {
        try {
          const handle = await window.showDirectoryPicker();
          const files = await walkDirectory(handle);
          state.assetsFiles = files;
          state.assetDirName = handle.name || '原型图';
          renderAssetsMeta();
          return;
        } catch (err) {
          if (err && err.name === 'AbortError') return;
        }
      }
      assetsFallback.click();
    }

    async function refreshStatus() {
      try {
        const resp = await fetch('/api/status');
        const data = await resp.json();
        setBadge(serverBadge, `本地服务在线 · ${data.host}:${data.port}`, 'ok');
        if (data.auth_sources.length) {
          setBadge(authBadge, `认证可用 · ${data.auth_sources.join(' / ')}`, 'ok');
        } else {
          setBadge(authBadge, '没找到 GitHub token', 'warn');
        }
        if (!ownerInput.value.trim() && data.default_owner) {
          ownerInput.value = data.default_owner;
          saveDraft();
        }
      } catch (err) {
        setBadge(serverBadge, '本地服务异常', 'warn');
        setBadge(authBadge, '认证状态读取失败', 'warn');
      }
    }

    async function publish() {
      const repo = repoInput.value.trim();
      const owner = ownerInput.value.trim();
      const description = descriptionInput.value.trim();
      const message = messageInput.value.trim();
      const isPublic = publicInput.checked;
      const isUpdateMode = state.mode === 'update';

      if (!repo) {
        setResult('仓库名没填，搞毛啊。', false);
        return;
      }
      if (isUpdateMode && !repoSelect.value) {
        setResult('你现在是“更新已有仓库”模式，先选目标仓库。', false);
        return;
      }
      if (!state.docFile) {
        setResult('你还没选 Markdown 文档。', false);
        return;
      }
      if (!state.assetsFiles.length && !isUpdateMode) {
        setResult('你还没选原型图目录。', false);
        return;
      }

      publishBtn.disabled = true;
      const modeText = isUpdateMode ? '更新已有仓库' : '新建/直填仓库';
      setResult(`上传中……当前模式：${modeText}。先把文件打包成本地请求，再交给 gh-doc-publish 推 GitHub。`, true);
      saveDraft();

      try {
        const docBase64 = await toBase64(state.docFile);
        const assetsPayload = [];
        for (const item of state.assetsFiles) {
          assetsPayload.push({
            relative_path: item.relativePath,
            content_base64: await toBase64(item.file)
          });
        }

        const resp = await fetch('/api/publish', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            mode: state.mode,
            selected_repo: repoSelect.value || '',
            repo,
            owner,
            description,
            message,
            public: isPublic,
            doc: {
              name: state.docFile.name,
              content_base64: docBase64
            },
            assets: {
              dir_name: state.assetDirName || '原型图',
              files: assetsPayload
            }
          })
        });
        const data = await resp.json();
        if (!resp.ok || !data.ok) {
          throw new Error(data.error || '上传失败');
        }
        setResult(JSON.stringify(data.result, null, 2), true);
        refreshStatus();
      } catch (err) {
        setResult(`上传失败\n\n${err.message || err}`, false);
      } finally {
        publishBtn.disabled = false;
      }
    }

    function clearDoc() {
      state.docFile = null;
      docFallback.value = '';
      renderDocMeta();
    }

    function clearAssets() {
      state.assetsFiles = [];
      state.assetDirName = '原型图';
      assetsFallback.value = '';
      renderAssetsMeta();
    }

    function resetAll() {
      state.mode = 'create';
      repoInput.value = '';
      ownerInput.value = '';
      descriptionInput.value = '';
      messageInput.value = '';
      publicInput.checked = false;
      state.savedSelectedRepo = '';
      repoSelect.value = '';
      clearDoc();
      clearAssets();
      localStorage.removeItem(storageKey);
      updateModeUI();
      renderRepoOptions();
      setResult('已清空。重新选文件再传。', true);
    }

    function setMode(mode) {
      state.mode = mode;
      updateModeUI();
      if (mode === 'update') {
        renderRepoOptions();
        if (!state.repoOptions.length) {
          refreshRepos();
        } else {
          syncSelectedRepo();
        }
      }
      saveDraft();
    }

    docFallback.addEventListener('change', () => {
      state.docFile = docFallback.files[0] || null;
      renderDocMeta();
    });

    assetsFallback.addEventListener('change', () => {
      const files = Array.from(assetsFallback.files || []);
      state.assetsFiles = files.map(file => ({
        file,
        relativePath: file.webkitRelativePath ? file.webkitRelativePath.split('/').slice(1).join('/') : file.name
      }));
      if (files[0] && files[0].webkitRelativePath) {
        state.assetDirName = files[0].webkitRelativePath.split('/')[0] || '原型图';
      } else {
        state.assetDirName = '原型图';
      }
      renderAssetsMeta();
    });

    [repoInput, ownerInput, descriptionInput, messageInput, publicInput].forEach(el => {
      el.addEventListener('change', saveDraft);
      el.addEventListener('input', saveDraft);
    });

    document.getElementById('pickDocBtn').addEventListener('click', pickDoc);
    document.getElementById('pickAssetsBtn').addEventListener('click', pickAssets);
    document.getElementById('clearDocBtn').addEventListener('click', clearDoc);
    document.getElementById('clearAssetsBtn').addEventListener('click', clearAssets);
    document.getElementById('publishBtn').addEventListener('click', publish);
    document.getElementById('resetBtn').addEventListener('click', resetAll);
    modeCreateBtn.addEventListener('click', () => setMode('create'));
    modeUpdateBtn.addEventListener('click', () => setMode('update'));
    refreshReposBtn.addEventListener('click', () => refreshRepos());
    repoSelect.addEventListener('change', syncSelectedRepo);
    saveTokenBtn.addEventListener('click', saveToken);
    checkTokenBtn.addEventListener('click', checkAuthStatus);
    generateKeyBtn.addEventListener('click', generateSshKey);

    loadDraft();
    fillGuide();
    updateModeUI();
    renderRepoOptions();
    renderDocMeta();
    renderAssetsMeta();
    refreshStatus();
    if (state.mode === 'update') {
      refreshRepos(true);
    }
  </script>
</body>
</html>
'''


def json_response(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class AppHandler(BaseHTTPRequestHandler):
    server_version = "gh-doc-publish-web/1.0"

    def log_message(self, format, *args):
        return

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/health":
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/status":
            sources = auth_sources()
            return json_response(self, 200, {
                "ok": True,
                "host": self.server.server_address[0],
                "port": self.server.server_address[1],
                "auth_sources": sources,
                "tool_path": TOOL_PATH,
                "tool_exists": Path(TOOL_PATH).exists(),
                "default_owner": default_owner(),
            })
        if parsed.path == "/api/repos":
            try:
                qs = parse_qs(parsed.query)
                owner = (qs.get('owner') or [''])[0]
                repos = list_repos(owner)
                return json_response(self, 200, {"ok": True, "repos": repos})
            except Exception as exc:
                return json_response(self, 400, {"ok": False, "error": str(exc)})
        return json_response(self, 404, {"ok": False, "error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b'{}'
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception as exc:
            return json_response(self, 400, {"ok": False, "error": f"请求体解析失败: {exc}"})

        if parsed.path == "/api/publish":
            try:
                result = publish_from_payload(payload)
                return json_response(self, 200, {"ok": True, "result": result})
            except Exception as exc:
                return json_response(self, 400, {"ok": False, "error": str(exc)})

        if parsed.path == "/api/auth/token":
            try:
                token = str(payload.get('token', '')).strip()
                save_token_to_keychain(token)
                return json_response(self, 200, {"ok": True})
            except Exception as exc:
                return json_response(self, 400, {"ok": False, "error": str(exc)})

        if parsed.path == "/api/auth/ssh-key":
            try:
                result = generate_ssh_keypair()
                return json_response(self, 200, {"ok": True, **result})
            except Exception as exc:
                return json_response(self, 400, {"ok": False, "error": str(exc)})

        return json_response(self, 404, {"ok": False, "error": "not found"})


def decode_b64_to_file(encoded: str, target: Path):
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        decoded = base64.b64decode(encoded.encode("utf-8"))
        target.write_bytes(decoded)
    except (binascii.Error, ValueError) as exc:
        raise RuntimeError(f"base64 解码失败: {target.name} · {exc}") from exc


def normalize_uploaded_markdown_refs(doc_path: Path, asset_dir_name: str):
    text = doc_path.read_text(encoding='utf-8')

    def normalize_ref(ref: str) -> str:
        ref = ref.strip()
        if not ref or re.match(r'^(https?:)?//|data:|#', ref):
            return ref

        m = re.match(r'^(?P<path>[^?#]+)(?P<suffix>[?#].*)?$', ref)
        if not m:
            return ref

        path_part = m.group('path').replace('\\', '/').strip()
        suffix = m.group('suffix') or ''
        parts = [part for part in path_part.split('/') if part not in ('', '.')]
        while parts and parts[0] == '..':
            parts.pop(0)
        if not parts or parts[0] != asset_dir_name:
            return ref
        return '/'.join(parts) + suffix

    text = re.sub(
        r'(!\[[^\]]*\]\()([^)]+)(\))',
        lambda m: f"{m.group(1)}{normalize_ref(m.group(2))}{m.group(3)}",
        text,
    )
    text = re.sub(
        r'(<img[^>]+src=["\'])([^"\']+)(["\'])',
        lambda m: f"{m.group(1)}{normalize_ref(m.group(2))}{m.group(3)}",
        text,
    )
    doc_path.write_text(text, encoding='utf-8')


def tool_owner_and_token(timeout: int = 6, attempts: int = 3):
    helper_code = (
        "import json, pathlib; ns={}; p='/Users/mac/bin/gh-doc-publish'; "
        "code=pathlib.Path(p).read_text(encoding='utf-8'); "
        "exec(compile(code,p,'exec'), ns); "
        "token,src=ns['resolve_token'](); owner=ns['detect_owner'](token, None); "
        "print(json.dumps({'token': token, 'owner': owner}, ensure_ascii=False))"
    )
    for idx in range(attempts):
        try:
            proc = subprocess.run(
                ['python3', '-c', helper_code],
                text=True,
                encoding='utf-8',
                errors='replace',
                capture_output=True,
                timeout=timeout,
                env=utf8_subprocess_env(),
            )
            if proc.returncode == 0:
                data = json.loads(proc.stdout or '{}')
                return {
                    'token': str(data.get('token', '')).strip(),
                    'owner': str(data.get('owner', '')).strip(),
                }
        except Exception:
            pass
        if idx < attempts - 1:
            time.sleep(0.2)
    return {'token': '', 'owner': ''}


def resolve_token_and_owner():
    try:
        proc = subprocess.run(
            [TOOL_PATH, 'auth', 'status'],
            text=True,
            encoding='utf-8',
            errors='replace',
            capture_output=True,
            timeout=3,
            env=utf8_subprocess_env(),
        )
        sources = []
        if proc.returncode == 0:
            lines = [line.strip() for line in proc.stdout.splitlines() if line.strip().startswith('-')]
            sources = [line.lstrip('-').strip() for line in lines]
    except Exception:
        sources = []

    owner = ''
    if sources:
        owner = tool_owner_and_token(timeout=4).get('owner', '')

    return sources, owner


def auth_sources():
    sources, _ = resolve_token_and_owner()
    return sources


def default_owner():
    _, owner = resolve_token_and_owner()
    return owner


def list_repos(owner_hint: str = ''):
    ctx = tool_owner_and_token(timeout=8)
    owner_hint = owner_hint.strip()
    owner = owner_hint or ctx.get('owner', '')
    if not owner:
        raise RuntimeError('拿不到默认 owner，先确保 GitHub token 可用或手动填 owner')

    headers = {'User-Agent': 'gh-doc-publish-web'}
    token = ctx.get('token', '')
    if token:
        headers['Authorization'] = f'Bearer {token}'

    if token and (not owner_hint or owner_hint == ctx.get('owner', '')):
        url = 'https://api.github.com/user/repos?per_page=200&sort=updated'
    else:
        url = f'https://api.github.com/users/{owner}/repos?per_page=200&sort=updated'

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception as exc:
        raise RuntimeError(f'仓库列表拉取失败: {exc}') from exc

    repos = []
    for item in data:
        full_name = item.get('full_name', '')
        if '/' not in full_name:
            continue
        repo_owner, repo_name = full_name.split('/', 1)
        if owner_hint and repo_owner != owner_hint:
            continue
        repos.append({
            'owner': repo_owner,
            'name': repo_name,
            'private': bool(item.get('private', False)),
            'updated_at': item.get('updated_at', ''),
        })
    repos.sort(key=lambda x: x['updated_at'], reverse=True)
    return repos


def generate_ssh_keypair():
    ssh_dir = Path.home() / '.ssh'
    ssh_dir.mkdir(parents=True, exist_ok=True)
    private_key = ssh_dir / 'id_ed25519'
    public_key = ssh_dir / 'id_ed25519.pub'
    if not private_key.exists() or not public_key.exists():
        email = 'kocekid@users.noreply.github.com'
        subprocess.run(
            ['ssh-keygen', '-t', 'ed25519', '-C', email, '-N', '', '-f', str(private_key)],
            text=True,
            encoding='utf-8',
            errors='replace',
            capture_output=True,
            check=True,
            env=utf8_subprocess_env(),
        )
    return {
        'private_key_path': str(private_key),
        'public_key_path': str(public_key),
        'public_key': public_key.read_text(encoding='utf-8').strip(),
    }


def save_token_to_keychain(token: str):
    token = token.strip()
    if not token:
        raise RuntimeError('token 为空')
    proc = subprocess.run(
        [TOOL_PATH, 'auth', 'set', '--token', token],
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
        timeout=20,
        env=utf8_subprocess_env(),
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or '保存 token 失败')
    return True


def publish_from_payload(payload: dict):
    mode = str(payload.get('mode', 'create')).strip() or 'create'
    selected_repo = str(payload.get('selected_repo', '')).strip()
    repo = str(payload.get("repo", "")).strip()
    owner = str(payload.get("owner", "")).strip()
    description = str(payload.get("description", "")).strip()
    message = str(payload.get("message", "")).strip()
    is_public = bool(payload.get("public"))
    doc = payload.get("doc") or {}
    assets = payload.get("assets") or {}
    doc_name = str(doc.get("name", "")).strip()
    doc_base64 = doc.get("content_base64")
    dir_name = str(assets.get("dir_name", "")).strip() or "原型图"
    asset_files = assets.get("files") or []
    has_assets = bool(asset_files)

    if mode == 'update' and selected_repo:
        if '/' not in selected_repo:
            raise RuntimeError('已有仓库选择值不合法')
        owner, repo = selected_repo.split('/', 1)

    if not repo:
        raise RuntimeError("仓库名不能为空")
    if mode == 'update' and not owner:
        raise RuntimeError('更新已有仓库时 owner 不能为空')
    if not doc_name.endswith(".md"):
        raise RuntimeError("文档必须是 .md")
    if not doc_base64:
        raise RuntimeError("文档内容为空")
    if not has_assets and mode != 'update':
        raise RuntimeError("原型图目录为空")

    with tempfile.TemporaryDirectory(prefix="gh-doc-publish-web-") as tmp:
        root = Path(tmp)
        doc_path = root / doc_name
        asset_root = root / dir_name
        decode_b64_to_file(doc_base64, doc_path)

        if has_assets:
            for item in asset_files:
                rel = str(item.get("relative_path", "")).strip().lstrip("/")
                blob = item.get("content_base64")
                if not rel or not blob:
                    raise RuntimeError("原型图目录里有无效文件项")
                target = (asset_root / rel).resolve()
                if asset_root.resolve() not in target.parents and target != asset_root.resolve():
                    raise RuntimeError(f"非法相对路径: {rel}")
                decode_b64_to_file(blob, target)

            normalize_uploaded_markdown_refs(doc_path, dir_name)

        cmd = [TOOL_PATH, "publish", repo, str(doc_path)]
        if has_assets:
            cmd.append(str(asset_root))
        if owner:
            cmd += ["--owner", owner]
        if description:
            cmd += ["--description", description]
        if message:
            cmd += ["--message", message]
        if is_public and mode != 'update':
            cmd += ["--public"]

        proc = subprocess.run(
            cmd,
            text=True,
            encoding='utf-8',
            errors='replace',
            capture_output=True,
            env=utf8_subprocess_env(),
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "gh-doc-publish 执行失败")
        try:
            result = json.loads(proc.stdout)
            result['mode'] = mode
            result['selected_repo'] = selected_repo
            return result
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"工具返回的不是合法 JSON:\n{proc.stdout}") from exc


def start_server(host: str, port: int, should_open: bool):
    url = f"http://{host}:{port}"
    try:
        httpd = ThreadingHTTPServer((host, port), AppHandler)
    except OSError as exc:
        if should_open:
            webbrowser.open(url)
            print(f"服务可能已经在跑了，直接给你打开：{url}")
            return 0
        raise exc

    if should_open:
        threading.Timer(0.35, lambda: webbrowser.open(url)).start()
    print(f"{APP_TITLE} 已启动：{url}")
    print("按 Ctrl+C 停止服务")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
    finally:
        httpd.server_close()
    return 0


def main():
    parser = argparse.ArgumentParser(description="本地 H5 页面：上传 md + 原型图目录到 GitHub 仓库")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    args = parser.parse_args()
    return start_server(args.host, args.port, args.open)


if __name__ == "__main__":
    raise SystemExit(main())
