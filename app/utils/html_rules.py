"""HTML 规则提取与 AI 挂件注入。"""

from __future__ import annotations

import os
from html.parser import HTMLParser
from typing import Optional


class LabeledTextExtractor(HTMLParser):
    """从 HTML 中提取带 data-label 标记的文本内容。"""

    def __init__(self, target_labels: list[str]) -> None:
        super().__init__(convert_charrefs=True)
        self._target_labels = {label.strip().lower() for label in target_labels}
        self._capturing_depth: Optional[int] = None
        self._depth = 0
        self._texts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        self._depth += 1
        if self._capturing_depth is not None:
            return
        for k, v in attrs:
            if k == "data-label" and (v or "").strip().lower() in self._target_labels:
                self._capturing_depth = self._depth
                return

    def handle_endtag(self, tag: str) -> None:
        if self._capturing_depth is not None and self._depth == self._capturing_depth:
            self._capturing_depth = None
        self._depth = max(0, self._depth - 1)

    def handle_data(self, data: str) -> None:
        if self._capturing_depth is None:
            return
        text = data.strip()
        if text:
            self._texts.append(text)

    def get_text(self) -> str:
        """返回提取到的文本。"""

        return "\n".join(self._texts).strip()


def extract_rule_text_from_html(html_content: str, labels: list[str] | str = "jiao_hu_gui_ze") -> str:
    """从 HTML 中提取交互规则文本。"""

    if isinstance(labels, str):
        labels = [labels]

    extractor = LabeledTextExtractor(labels)
    try:
        extractor.feed(html_content)
        extractor.close()
    except Exception:
        return ""
    return extractor.get_text()


def iter_html_files(root_dir: str) -> list[str]:
    """遍历目录下所有 HTML 文件路径。"""

    html_files: list[str] = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            if fn.lower().endswith(".html"):
                html_files.append(os.path.join(dirpath, fn))
    return html_files


def inject_ai_widget_into_html(html_content: str) -> str:
    """向 HTML 注入 AI 对话挂件。"""

    widget = r"""
<script src="/static/marked.min.js"></script>
<script src="/static/mermaid.min.js"></script>
<script src="/static/markdown.js"></script>
<div id="axure-share-ai-root" style="display:none;position:fixed;top:0;left:0;z-index:2147483647;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,'Noto Sans','Liberation Sans',sans-serif;display:flex;align-items:center;gap:6px;">
  <button id="axure-share-proto-info-open" type="button" style="display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:6px;border:0;background:transparent;color:#111827;cursor:pointer;padding:0;line-height:1; margin-right: 12px;">ℹ️</button>
  <button id="axure-share-ai-open" type="button" style="display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:6px;border:0;background:transparent;color:#111827;cursor:pointer;padding:0;line-height:1;">🤖</button>
</div>
<div id="axure-share-proto-info-modal" style="display:none;position:fixed;inset:0;z-index:2147483646;background:rgba(15,23,42,0.4);align-items:center;justify-content:center;">
  <div style="width:min(520px,calc(100vw - 32px));max-height:min(640px,calc(100vh - 32px));background:#fff;border-radius:12px;box-shadow:0 12px 40px rgba(0,0,0,0.25);overflow:hidden;display:flex;flex-direction:column;">
    <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid #e5e7eb;">
      <div style="font-weight:600;color:#111827;">原型说明</div>
      <button id="axure-share-proto-info-close" type="button" style="border:0;background:transparent;font-size:20px;line-height:20px;cursor:pointer;color:#6b7280;">×</button>
    </div>
    <div id="axure-share-proto-info-body" style="padding:14px 16px;overflow:auto;display:flex;flex-direction:column;gap:10px;color:#111827;font-size:14px;"></div>
  </div>
</div>
<div id="axure-share-ai-panel" style="display:none;position:fixed;top:56px;right:12px;width:min(520px,calc(100vw - 24px));height:min(640px,calc(100vh - 88px));background:#fff;border-radius:12px;box-shadow:0 10px 40px rgba(0,0,0,0.25);overflow:hidden;">
  <div style="height:100%;display:flex;flex-direction:column;">
    <div id="axure-share-ai-titlebar" style="display:flex;align-items:center;justify-content:space-between;padding:12px 12px;border-bottom:1px solid #e5e7eb;cursor:move;user-select:none;">
      <div style="font-weight:600;color:#111827;">AI·需求答疑</div>
      <button id="axure-share-ai-close" type="button" style="border:0;background:transparent;font-size:20px;line-height:20px;cursor:pointer;color:#6b7280;">×</button>
    </div>
    <div id="axure-share-ai-messages" style="flex:1;overflow:auto;padding:12px;display:flex;flex-direction:column;gap:10px;background:#f9fafb;"></div>
    <div style="padding:12px;border-top:1px solid #e5e7eb;display:flex;gap:8px;align-items:flex-end;background:#fff;">
      <textarea id="axure-share-ai-input" rows="2" style="flex:1;resize:vertical;min-height:42px;max-height:160px;padding:10px 10px;border:1px solid #d1d5db;border-radius:10px;font-size:14px;outline:none;"></textarea>
      <button id="axure-share-ai-send" type="button" style="padding:10px 14px;border-radius:10px;border:1px solid #111827;background:#111827;color:#fff;cursor:pointer;">发送</button>
    </div>
  </div>
</div>
<script>
(function () {
  function qs(id) { return document.getElementById(id); }
  var openBtn = qs('axure-share-ai-open');
  var infoBtn = qs('axure-share-proto-info-open');
  var infoModal = qs('axure-share-proto-info-modal');
  var infoClose = qs('axure-share-proto-info-close');
  var infoBody = qs('axure-share-proto-info-body');
  var root = qs('axure-share-ai-root');
  var panel = qs('axure-share-ai-panel');
  var closeBtn = qs('axure-share-ai-close');
  var sendBtn = qs('axure-share-ai-send');
  var input = qs('axure-share-ai-input');
  var box = qs('axure-share-ai-messages');

  if (window.top !== window.self) {
    var roots = document.querySelectorAll('#axure-share-ai-root');
    for (var i = 0; i < roots.length; i++) {
      roots[i].remove();
    }
    return;
  }

  var roots = document.querySelectorAll('#axure-share-ai-root');
  if (roots && roots.length > 1) {
    for (var i = 1; i < roots.length; i++) {
      roots[i].remove();
    }
    root = qs('axure-share-ai-root');
  }
  if (root) {
    root.style.display = 'none';
  }

  function escapeHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function sanitizeUrl(url) {
    try {
      var u = new URL(String(url || ''), location.href);
      var p = (u.protocol || '').toLowerCase();
      if (p === 'http:' || p === 'https:' || p === 'mailto:') return u.href;
      return '';
    } catch (e) {
      return '';
    }
  }

  function inlineFormat(escapedText) {
    var t = String(escapedText || '');
    t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function (_, label, href) {
      var safe = sanitizeUrl(href);
      if (!safe) return label;
      return '<a href="' + escapeHtml(safe) + '" target="_blank" rel="noopener noreferrer" style="color:#2563eb;text-decoration:underline;">' + label + '</a>';
    });
    t = t.replace(/`([^`]+)`/g, function (_, code) {
      return '<code style="padding:1px 4px;border-radius:6px;background:#f3f4f6;border:1px solid #e5e7eb;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,\'Liberation Mono\',\'Courier New\',monospace;">' + code + '</code>';
    });
    t = t.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    t = t.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    return t;
  }

  function renderMarkdown(md) {
    var src = String(md || '').replace(/\r\n/g, '\n');
    var blocks = [];
    src = src.replace(/```([a-zA-Z0-9_-]+)?\n([\s\S]*?)```/g, function (_, lang, code) {
      blocks.push({ lang: String(lang || ''), code: String(code || '') });
      return '%%CODEBLOCK_' + (blocks.length - 1) + '%%';
    });

    var lines = src.split('\n');
    var html = '';
    var inUl = false;
    var inOl = false;

    function closeLists() {
      if (inUl) { html += '</ul>'; inUl = false; }
      if (inOl) { html += '</ol>'; inOl = false; }
    }

    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      var trimmed = String(line || '').trim();

      var m = trimmed.match(/^%%CODEBLOCK_(\d+)%%$/);
      if (m) {
        closeLists();
        var idx = parseInt(m[1], 10);
        var b = blocks[idx] || { lang: '', code: '' };
        var codeEsc = escapeHtml(b.code);
        html += '<pre style="margin:8px 0;padding:10px 12px;border-radius:10px;background:#0b1020;color:#e5e7eb;overflow:auto;border:1px solid rgba(255,255,255,0.08);"><code>' + codeEsc + '</code></pre>';
        continue;
      }

      if (!trimmed) {
        closeLists();
        continue;
      }

      var h = trimmed.match(/^(#{1,6})\s+(.+)$/);
      if (h) {
        closeLists();
        var level = h[1].length;
        var textEsc = escapeHtml(h[2]);
        html += '<h' + level + ' style="margin:10px 0 6px 0;font-size:' + (18 - level) + 'px;line-height:1.3;color:#111827;">' + inlineFormat(textEsc) + '</h' + level + '>';
        continue;
      }

      var ul = trimmed.match(/^[-*]\s+(.+)$/);
      if (ul) {
        if (inOl) { html += '</ol>'; inOl = false; }
        if (!inUl) { html += '<ul style="margin:6px 0 6px 18px;padding:0;">'; inUl = true; }
        var liEsc = escapeHtml(ul[1]);
        html += '<li style="margin:4px 0;">' + inlineFormat(liEsc) + '</li>';
        continue;
      }

      var ol = trimmed.match(/^\d+\.\s+(.+)$/);
      if (ol) {
        if (inUl) { html += '</ul>'; inUl = false; }
        if (!inOl) { html += '<ol style="margin:6px 0 6px 18px;padding:0;">'; inOl = true; }
        var oliEsc = escapeHtml(ol[1]);
        html += '<li style="margin:4px 0;">' + inlineFormat(oliEsc) + '</li>';
        continue;
      }

      closeLists();
      var pEsc = escapeHtml(trimmed);
      html += '<p style="margin:6px 0;line-height:1.6;color:#111827;">' + inlineFormat(pEsc) + '</p>';
    }

    closeLists();
    return html || '';
  }

  function setInfoOpen(open) {
    if (!infoModal) return;
    infoModal.style.display = open ? 'flex' : 'none';
  }

  function buildInfoRow(label, value) {
    return '<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;border:1px solid #e5e7eb;border-radius:10px;padding:10px 12px;background:#f9fafb;">'
      + '<div style="color:#6b7280;font-size:12px;">' + label + '</div>'
      + '<div style="font-weight:600;color:#111827;text-align:right;word-break:break-all;">' + value + '</div>'
      + '</div>';
  }

  function buildFileItem(file) {
    var name = escapeHtml(file.name || '');
    var sizeText = escapeHtml(file.size_text || '');
    var downloadUrl = escapeHtml(file.download_url || '');
    var previewUrl = escapeHtml(file.preview_url || '');
    var actions = '';
    if (downloadUrl) {
      actions += '<a href="' + downloadUrl + '" target="_blank" rel="noopener noreferrer" style="display:inline-flex;align-items:center;justify-content:center;padding:6px 10px;border-radius:8px;background:#111827;color:#fff;text-decoration:none;font-size:12px;">下载</a>';
    }
    if (previewUrl) {
      actions += '<a href="' + previewUrl + '" target="_blank" rel="noopener noreferrer" style="display:inline-flex;align-items:center;justify-content:center;padding:6px 10px;border-radius:8px;background:#f3f4f6;color:#111827;text-decoration:none;font-size:12px;margin-left:8px;">在线预览</a>';
    }
    return '<div style="border:1px solid #e5e7eb;border-radius:10px;padding:10px 12px;display:flex;flex-direction:column;gap:6px;">'
      + '<div style="font-weight:600;color:#111827;word-break:break-all;">' + name + '</div>'
      + '<div style="font-size:12px;color:#6b7280;">大小：' + sizeText + '</div>'
      + '<div style="display:flex;align-items:center;gap:8px;">' + actions + '</div>'
      + '</div>';
  }

  function buildFileList(label, files) {
    if (!files || !files.length) {
      return '<div style="border:1px dashed #e5e7eb;border-radius:10px;padding:10px 12px;color:#9ca3af;">' + label + '：暂无</div>';
    }
    var items = files.map(function (file) {
      return buildFileItem(file || {});
    }).join('');
    return '<div style="display:flex;flex-direction:column;gap:8px;">'
      + '<div style="font-size:12px;color:#6b7280;">' + label + '</div>'
      + items
      + '</div>';
  }

  function buildFileBlock(label, file) {
    if (!file) {
      return '<div style="border:1px dashed #e5e7eb;border-radius:10px;padding:10px 12px;color:#9ca3af;">' + label + '：暂无</div>';
    }
    return '<div style="display:flex;flex-direction:column;gap:8px;">'
      + '<div style="font-size:12px;color:#6b7280;">' + label + '</div>'
      + buildFileItem(file)
      + '</div>';
  }

  async function loadPrototypeInfo() {
    if (!infoBody) return;
    infoBody.innerHTML = '<div style="color:#6b7280;">加载中...</div>';
    var ctx = getCtx();
    if (!ctx.short_id) {
      infoBody.innerHTML = '<div style="color:#ef4444;">无法识别原型信息</div>';
      return;
    }
    try {
      var resp = await fetch('/api/prototype_info/' + encodeURIComponent(ctx.short_id));
      if (!resp.ok) {
        infoBody.innerHTML = '<div style="color:#ef4444;">无法获取原型信息</div>';
        return;
      }
      var data = await resp.json();
      var name = escapeHtml(data.name || '');
      var sizeText = escapeHtml(data.size_text || '');
      var prototypeUrl = escapeHtml(data.prototype_url || '');
      var currentProtocol = window.location.protocol; // 获取当前页面协议
      var prototypeValue = prototypeUrl
        ? '<input type="text" readonly value="' + prototypeUrl.replace(/^https?:/i, currentProtocol) + '" style="width:260px;max-width:60vw;border:1px solid #e5e7eb;border-radius:8px;padding:6px 8px;background:#ffffff;color:#111827;font-weight:500;font-size:12px;text-align:left;" onclick="this.select()">'
        : '-';
      var updatedAtText = escapeHtml(data.updated_at_text || '');
      var updaterName = escapeHtml(data.updater_name || '-');
      var recentUpdateStr = updaterName + ' ' + updatedAtText;
      var attachments = Array.isArray(data.attachments) ? data.attachments : (data.attachment ? [data.attachment] : []);
      var html = '';
      html += buildInfoRow('原型名称', name || '-');
      html += buildInfoRow('原型地址', prototypeValue);
      html += buildInfoRow('原型大小', sizeText || '-');
      html += buildInfoRow('最近更新', recentUpdateStr);
      html += buildFileList('附件', attachments);
      html += buildFileBlock('原型源文件', data.source);
      infoBody.innerHTML = html;
    } catch (e) {
      infoBody.innerHTML = '<div style="color:#ef4444;">获取失败，请稍后再试</div>';
    }
  }

  function getCtx() {
    var parts = (location.pathname || '').split('/').filter(Boolean);
    var shortId = '';
    var pagePath = '';
    var vIdx = parts.indexOf('v');
    if (vIdx >= 0 && parts.length > vIdx + 1) {
      shortId = parts[vIdx + 1];
      pagePath = parts.slice(vIdx + 2).join('/');
    }
    if (!pagePath) {
      pagePath = (location.pathname || '').split('/').slice(-1)[0] || 'index.html';
    }
    var hash = location.hash || '';
    return { short_id: shortId, page_path: pagePath + hash };
  }

  function getStorageKey(suffix) {
    var ctx = getCtx();
    var base = (ctx.short_id || 'unknown') + '::ai_chat::' + (suffix || 'state');
    return base;
  }

  function loadMessages() {
    try {
      var raw = sessionStorage.getItem(getStorageKey('messages'));
      if (!raw) return [];
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function saveMessages(msgs) {
    try {
      var limited = msgs.slice(-60);
      sessionStorage.setItem(getStorageKey('messages'), JSON.stringify(limited));
    } catch (e) {}
  }

  function append(role, text) {
    var row = document.createElement('div');
    row.style.display = 'flex';
    row.style.justifyContent = role === 'user' ? 'flex-end' : 'flex-start';
    var bubble = document.createElement('div');
    bubble.style.maxWidth = '86%';
    bubble.style.whiteSpace = 'normal';
    bubble.style.wordBreak = 'break-word';
    bubble.style.padding = '10px 12px';
    bubble.style.borderRadius = '12px';
    bubble.style.fontSize = '14px';
    bubble.style.lineHeight = '1.4';
    bubble.style.border = '1px solid rgba(0,0,0,0.08)';
    bubble.style.background = role === 'user' ? '#111827' : '#ffffff';
    bubble.style.color = role === 'user' ? '#ffffff' : '#111827';
    if (role === 'assistant') {
      bubble.innerHTML = renderMarkdown(String(text || ''));
    } else {
      bubble.textContent = String(text || '');
    }
    row.appendChild(bubble);
    box.appendChild(row);
    box.scrollTop = box.scrollHeight;
    var msgs = loadMessages();
    msgs.push({ role: role, text: String(text || '') });
    saveMessages(msgs);
  }

  function setOpen(open) {
    panel.style.display = open ? 'block' : 'none';
    try { sessionStorage.setItem(getStorageKey('open'), open ? '1' : '0'); } catch (e) {}
    if (open) {
      applySavedPanelPos();
    }
  }

  function clamp(n, min, max) {
    return Math.min(max, Math.max(min, n));
  }

  function loadPanelPos() {
    try {
      var raw = sessionStorage.getItem(getStorageKey('panel_pos'));
      if (!raw) return null;
      var obj = JSON.parse(raw);
      if (!obj) return null;
      var left = Number(obj.left);
      var top = Number(obj.top);
      if (!isFinite(left) || !isFinite(top)) return null;
      return { left: left, top: top };
    } catch (e) {
      return null;
    }
  }

  function savePanelPos(left, top) {
    try {
      sessionStorage.setItem(getStorageKey('panel_pos'), JSON.stringify({ left: left, top: top }));
    } catch (e) {}
  }

  function applySavedPanelPos() {
    if (!panel) return;
    var pos = loadPanelPos();
    if (!pos) return;
    panel.style.right = '';
    panel.style.bottom = '';
    panel.style.left = Math.max(0, pos.left) + 'px';
    panel.style.top = Math.max(0, pos.top) + 'px';
  }

  (function bindDrag() {
    var bar = qs('axure-share-ai-titlebar');
    if (!bar || !panel) return;
    var dragging = false;
    var startX = 0;
    var startY = 0;
    var startLeft = 0;
    var startTop = 0;

    function onDown(e) {
      if (!panel || !bar) return;
      if (e && e.target && (e.target === closeBtn || (e.target.id === 'axure-share-ai-close'))) return;
      dragging = true;
      try { bar.setPointerCapture && bar.setPointerCapture(e.pointerId); } catch (err) {}
      var rect = panel.getBoundingClientRect();
      panel.style.right = '';
      panel.style.bottom = '';
      panel.style.left = rect.left + 'px';
      panel.style.top = rect.top + 'px';
      startX = e.clientX;
      startY = e.clientY;
      startLeft = rect.left;
      startTop = rect.top;
      document.addEventListener('pointermove', onMove);
      document.addEventListener('pointerup', onUp);
      e.preventDefault && e.preventDefault();
    }

    function onMove(e) {
      if (!dragging || !panel) return;
      var dx = e.clientX - startX;
      var dy = e.clientY - startY;
      var left = startLeft + dx;
      var top = startTop + dy;
      var maxLeft = Math.max(0, window.innerWidth - panel.offsetWidth);
      var maxTop = Math.max(0, window.innerHeight - panel.offsetHeight);
      left = clamp(left, 0, maxLeft);
      top = clamp(top, 0, maxTop);
      panel.style.left = left + 'px';
      panel.style.top = top + 'px';
    }

    function onUp() {
      if (!dragging || !panel) return;
      dragging = false;
      document.removeEventListener('pointermove', onMove);
      document.removeEventListener('pointerup', onUp);
      var rect = panel.getBoundingClientRect();
      savePanelPos(rect.left, rect.top);
    }

    bar.addEventListener('pointerdown', onDown);
  })();

  function appendAssistantStreaming() {
    var row = document.createElement('div');
    row.style.display = 'flex';
    row.style.justifyContent = 'flex-start';
    var bubble = document.createElement('div');
    bubble.style.maxWidth = '86%';
    bubble.style.whiteSpace = 'normal';
    bubble.style.wordBreak = 'break-word';
    bubble.style.padding = '10px 12px';
    bubble.style.borderRadius = '12px';
    bubble.style.fontSize = '14px';
    bubble.style.lineHeight = '1.4';
    bubble.style.border = '1px solid rgba(0,0,0,0.08)';
    bubble.style.background = '#ffffff';
    bubble.style.color = '#111827';
    bubble.innerHTML = '<p style="margin:0;line-height:1.6;color:#6b7280;">…</p>';
    row.appendChild(bubble);
    box.appendChild(row);
    box.scrollTop = box.scrollHeight;
    return bubble;
  }

  function updateAssistantBubble(bubble, fullText) {
    if (!bubble) return;
    bubble.innerHTML = renderMarkdown(fullText);
    box.scrollTop = box.scrollHeight;
  }

  async function readSse(resp, onJson) {
    var reader = resp.body.getReader();
    var decoder = new TextDecoder('utf-8');
    var buf = '';
    while (true) {
      var r = await reader.read();
      if (r.done) break;
      buf += decoder.decode(r.value, { stream: true });
      buf = buf.replace(/\r\n/g, '\n');
      var parts = buf.split('\n\n');
      buf = parts.pop() || '';
      for (var i = 0; i < parts.length; i++) {
        var chunk = parts[i];
        var lines = chunk.split('\n');
        var dataLines = [];
        for (var j = 0; j < lines.length; j++) {
          var ln = lines[j];
          if (ln.indexOf('data:') === 0) {
            dataLines.push(ln.slice(5).trim());
          }
        }
        if (dataLines.length === 0) continue;
        var dataStr = dataLines.join('');
        try {
          var obj = JSON.parse(dataStr);
          onJson && onJson(obj);
        } catch (e) {}
      }
    }
  }

  async function send() {
    var question = (input.value || '').trim();
    if (!question) return;
    input.value = '';
    append('user', question);
    var ctx = getCtx();
    var bubble = appendAssistantStreaming();
    var full = '';
    try {
      var resp = await fetch('/api/ai/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ short_id: ctx.short_id, page_path: ctx.page_path, question: question })
      });
      if (!resp.ok || !resp.body) {
        throw new Error('stream not available');
      }
      await readSse(resp, function (obj) {
        if (obj && obj.delta) {
          full += String(obj.delta || '');
          updateAssistantBubble(bubble, full);
        }
        if (obj && obj.done) {
          var msgs = loadMessages();
          msgs.push({ role: 'assistant', text: String(full || '') });
          saveMessages(msgs);
        }
      });
    } catch (e) {
      try {
        var resp2 = await fetch('/api/ai/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ short_id: ctx.short_id, page_path: ctx.page_path, question: question })
        });
        var data2 = await resp2.json();
        var ans = (data2 && data2.answer) ? String(data2.answer) : '关于这个问题，知识库中没有相关记录，请直接咨询（产品负责人）以获取准确信息。';
        full = ans;
        updateAssistantBubble(bubble, full);
        var msgs2 = loadMessages();
        msgs2.push({ role: 'assistant', text: String(full || '') });
        saveMessages(msgs2);
      } catch (e2) {
        full = '关于这个问题，知识库中没有相关记录，请直接咨询（产品负责人）以获取准确信息。';
        updateAssistantBubble(bubble, full);
        var msgs3 = loadMessages();
        msgs3.push({ role: 'assistant', text: String(full || '') });
        saveMessages(msgs3);
      }
    }
  }

  function mountButtonIntoAxureHeader() {
    if (!root || !openBtn) return false;
    var ul = document.getElementById('inspectControlFrameHeader');
    if (ul) {
      var li = document.getElementById('axure-share-ai-li');
      if (!li) {
        li = document.createElement('li');
        li.id = 'axure-share-ai-li';
        li.style.display = 'flex';
        li.style.alignItems = 'center';
        li.style.marginRight = '32px';
      }
      if (ul.firstChild) {
        ul.insertBefore(li, ul.firstChild);
      } else {
        ul.appendChild(li);
      }
      root.style.position = 'static';
      root.style.top = '';
      root.style.left = '';
      root.style.zIndex = '';
      root.style.marginLeft = '0';
      root.style.display = 'flex';
      root.style.alignItems = 'center';
      li.appendChild(root);
      return true;
    }

    var target = document.getElementById('interfaceControlFrameRight');
    if (!target) {
      if (root) {
        root.style.display = 'none';
      }
      return false;
    }
    root.style.position = 'static';
    root.style.top = '';
    root.style.left = '';
    root.style.zIndex = '';
    root.style.marginLeft = '10px';
    root.style.display = 'flex';
    root.style.alignItems = 'center';
    if (target.firstChild) {
      target.insertBefore(root, target.firstChild);
    } else {
      target.appendChild(root);
    }
    return true;
  }

  function restoreState() {
    var msgs = loadMessages();
    if (msgs.length === 0) {
      append('assistant', '你好，我可以基于当前原型与页面规则回答需求问题。');
    } else {
      box.innerHTML = '';
      msgs.forEach(function (m) {
        var role = m && m.role ? m.role : 'assistant';
        var text = m && m.text ? m.text : '';
        var row = document.createElement('div');
        row.style.display = 'flex';
        row.style.justifyContent = role === 'user' ? 'flex-end' : 'flex-start';
        var bubble = document.createElement('div');
        bubble.style.maxWidth = '86%';
        bubble.style.whiteSpace = 'pre-wrap';
        bubble.style.wordBreak = 'break-word';
        bubble.style.padding = '10px 12px';
        bubble.style.borderRadius = '12px';
        bubble.style.fontSize = '14px';
        bubble.style.lineHeight = '1.4';
        bubble.style.border = '1px solid rgba(0,0,0,0.08)';
        bubble.style.background = role === 'user' ? '#111827' : '#ffffff';
        bubble.style.color = role === 'user' ? '#ffffff' : '#111827';
        if (role === 'assistant') {
          bubble.innerHTML = renderMarkdown(String(text || ''));
        } else {
          bubble.textContent = String(text || '');
        }
        row.appendChild(bubble);
        box.appendChild(row);
      });
      box.scrollTop = box.scrollHeight;
    }
    var open = '0';
    try { open = sessionStorage.getItem(getStorageKey('open')) || '0'; } catch (e) {}
    setOpen(open === '1');
  }

  openBtn && openBtn.addEventListener('click', function () {
    var isOpen = panel && panel.style.display !== 'none';
    setOpen(!isOpen);
  });
  infoBtn && infoBtn.addEventListener('click', function () {
    loadPrototypeInfo();
    setInfoOpen(true);
  });
  infoClose && infoClose.addEventListener('click', function () { setInfoOpen(false); });
  infoModal && infoModal.addEventListener('click', function (e) { if (e.target === infoModal) { setInfoOpen(false); } });
  closeBtn && closeBtn.addEventListener('click', function () { setOpen(false); });
  sendBtn && sendBtn.addEventListener('click', send);
  input && input.addEventListener('keydown', function (e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } });

  var mounted = false;
  function tryMount() {
    if (mounted) return;
    mounted = mountButtonIntoAxureHeader();
  }
  tryMount();
  var attempts = 0;
  (function retryMount() {
    if (mounted) return;
    if (attempts >= 20) return;
    attempts += 1;
    tryMount();
    if (!mounted) {
      setTimeout(retryMount, 300);
    }
  })();
  if (document.body && window.MutationObserver) {
    var observer = new MutationObserver(function () {
      if (mounted) return;
      tryMount();
      if (mounted) observer.disconnect();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }
  restoreState();
})();
</script>
"""

    if 'id="axure-share-ai-root"' in html_content:
        start = html_content.find('<div id="axure-share-ai-root"')
        if start != -1:
            end = html_content.find("</script>", start)
            if end != -1:
                end = end + len("</script>")
                return html_content[:start] + widget + html_content[end:]
        return html_content

    lower = html_content.lower()
    close_body_idx = lower.rfind("</body>")
    if close_body_idx != -1:
        return html_content[:close_body_idx] + widget + html_content[close_body_idx:]
    return html_content + widget


def remove_ai_widget_from_html(html_content: str) -> str:
    """从 HTML 中移除 AI 对话挂件。"""

    cleaned = html_content
    patterns = [
        r'<script\s+src="/static/marked\.min\.js"></script>\s*',
        r'<script\s+src="/static/mermaid\.min\.js"></script>\s*',
        r'<script\s+src="/static/markdown\.js"></script>\s*',
        r'<div id="axure-share-ai-root"[\s\S]*?</script>\s*',
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    return cleaned


def inject_base_tag_into_html(html_content: str, base_href: str) -> str:
    """向 HTML 注入 <base> 标签。"""

    if "<base" in html_content.lower():
        return html_content

    tag = f'\n<base href="{base_href}">\n'
    lower = html_content.lower()
    head_idx = lower.find("<head>")
    if head_idx != -1:
        return html_content[: head_idx + 6] + tag + html_content[head_idx + 6 :]
    
    html_idx = lower.find("<html>")
    if html_idx != -1:
        return html_content[: html_idx + 6] + tag + html_content[html_idx + 6 :]
        
    return tag + html_content
