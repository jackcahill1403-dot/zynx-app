import json
import os
import random
import urllib.error
import urllib.request
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


APP_NAME = "Zynx"
COMPANY_NAME = "Zynx.AI"

MODELS: Dict[str, Dict[str, str]] = {
    "glm_air": {
        "label": "Vexa",
        "desc": "A balanced reasoning model for everyday questions, explanations, planning, and heavier prompts.",
        "logo": "/assets/model_logos/Vexa.png",
        "model_id": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "key_prefix": "OPENROUTER_GLM_AIR",
    },
    "kimi_k2": {
        "label": "Nyro",
        "desc": "A coding-focused model for debugging, implementation help, and structured technical work.",
        "logo": "/assets/model_logos/Nyro.png",
        "model_id": "cohere/north-mini-code:free",
        "key_prefix": "OPENROUTER_KIMI_K2",
    },
    "mistral_nemo": {
        "label": "Kiro",
        "desc": "A quick instruction model for chat, brainstorming, and lightweight creative writing.",
        "logo": "/assets/model_logos/Kiro.png",
        "model_id": "liquid/lfm-2.5-1.2b-instruct:free",
        "key_prefix": "OPENROUTER_MISTRAL_NEMO",
    },
}

DEFAULT_MODEL_KEY = "glm_air"


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(system|user|assistant)$")
    content: str = Field(min_length=1, max_length=20000)


class ChatRequest(BaseModel):
    model_key: str = DEFAULT_MODEL_KEY
    messages: List[ChatMessage] = Field(default_factory=list, max_length=60)


app = FastAPI(title="Zynx", version="2.0-fastapi")

if os.path.isdir("assets"):
    app.mount("/assets", StaticFiles(directory="assets"), name="assets")


def _clean_model_id(model_id: str) -> str:
    return model_id.removeprefix("openrouter/")


def _key_candidates(prefix: str) -> List[str]:
    names = []
    for idx in range(1, 4):
        names.extend([
            f"{prefix}_{idx}",
            f"{prefix}_API_KEY_{idx}",
        ])
    names.extend([prefix, f"{prefix}_API_KEY", "OPENROUTER_API_KEY"])

    keys: List[str] = []
    seen = set()
    for name in names:
        value = os.getenv(name, "").strip()
        if value and value not in seen:
            seen.add(value)
            keys.append(value)
    return keys


def _system_prompt() -> str:
    return f"""You are {APP_NAME}, a general-purpose AI assistant made by {COMPANY_NAME}.

Be useful, clear, and natural. Help with coding, school work, writing, ideas, tech help, game development, debugging, planning, and learning.
If asked who made you, who created you, who built you, who owns you, or who your creator is, answer exactly: I was made by {COMPANY_NAME}.
If you do not know something, say so.
If the user asks for code, give complete working code when possible."""


def _openrouter_chat(model_key: str, messages: List[ChatMessage]) -> str:
    spec = MODELS.get(model_key) or MODELS[DEFAULT_MODEL_KEY]
    keys = _key_candidates(spec["key_prefix"])
    if not keys:
        raise HTTPException(
            status_code=503,
            detail=f"No OpenRouter key configured for {spec['label']}. Add {spec['key_prefix']}_API_KEY_1, _2, and _3 in Render.",
        )

    payload_messages: List[Dict[str, str]] = [{"role": "system", "content": _system_prompt()}]
    for msg in messages[-40:]:
        if msg.role != "system":
            payload_messages.append({"role": msg.role, "content": msg.content})

    payload = {
        "model": _clean_model_id(spec["model_id"]),
        "messages": payload_messages,
        "temperature": 0.7,
    }

    last_error = ""
    random.shuffle(keys)
    for key in keys:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": os.getenv("ZYNX_SITE_URL", "https://zynx.ai"),
                "X-Title": "Zynx",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content.strip():
                return content.strip()
            last_error = "OpenRouter returned an empty response."
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", errors="replace")
            last_error = f"OpenRouter HTTP {err.code}: {body[:600]}"
            if err.code not in (401, 403, 404, 408, 409, 429, 500, 502, 503, 504):
                break
        except Exception as err:
            last_error = str(err)

    raise HTTPException(status_code=502, detail=last_error or "OpenRouter request failed.")


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "runtime": "fastapi", "models": list(MODELS)}


@app.get("/api/models")
def models() -> Dict[str, Any]:
    return {"models": MODELS, "default": DEFAULT_MODEL_KEY}


@app.post("/api/chat")
def chat(req: ChatRequest) -> Dict[str, str]:
    if not req.messages:
        raise HTTPException(status_code=400, detail="No messages supplied.")
    if req.model_key not in MODELS:
        raise HTTPException(status_code=400, detail="Unknown model.")
    return {"reply": _openrouter_chat(req.model_key, req.messages)}


INDEX_HTML = r"""
<!doctype html>
<html lang="en" data-theme="light">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Zynx</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
  <style>
    /* ============ TOKENS ============ */
    :root, [data-theme="light"] {
      --bg: #fafafa;
      --bg-soft: #f2f4f8;
      --card: #ffffff;
      --border: #e3e6ec;
      --code-bg: #0a0a0a;
      --code-fg: #e8e8e8;
      --text: #1a1a1a;
      --muted: #7a7f87;
      --accent: #1a1a1a;
      --accent-soft: rgba(0,0,0,0.06);
      --grid-line: rgba(0,0,0,0.04);
      --shadow-soft: 0 8px 24px rgba(0,0,0,0.07);
      --shadow-deep: 0 18px 44px rgba(0,0,0,0.14);
      --ring: rgba(0,0,0,0.14);
    }
    [data-theme="dark"] {
      --bg: #0d0d0d;
      --bg-soft: #141414;
      --card: #181818;
      --border: #272727;
      --code-bg: #0a0a0a;
      --code-fg: #e8e8e8;
      --text: #ffffff;
      --muted: #888888;
      --accent: #ffffff;
      --accent-soft: rgba(255,255,255,0.08);
      --grid-line: rgba(255,255,255,0.028);
      --shadow-soft: 0 8px 24px rgba(0,0,0,0.40);
      --shadow-deep: 0 18px 44px rgba(0,0,0,0.62);
      --ring: rgba(255,255,255,0.18);
    }
    /* the one signal colour, identical in both themes */
    :root { --blue: #2563eb; --blue-hover: #3b82f6; }

    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      color: var(--text);
      background: var(--bg);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
      font-size: 15px;
      line-height: 24px; /* aligns text rows to the grid cadence */
      -webkit-font-smoothing: antialiased;
    }
    button, textarea, input { font: inherit; color: inherit; }
    .mono { font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Consolas, monospace; }
    .label {
      font-family: "JetBrains Mono", ui-monospace, monospace;
      text-transform: uppercase; letter-spacing: .18em; font-size: .64rem;
      color: var(--muted); font-weight: 500;
    }

    /* ============ SHELL ============ */
    .shell { height: 100vh; display: grid; grid-template-columns: 300px minmax(0,1fr); }

    /* ---- Sidebar ---- */
    .sidebar {
      background: var(--bg-soft);
      border-right: 1px solid var(--border);
      padding: 20px 16px; display: flex; flex-direction: column; gap: 20px;
      min-height: 0;
    }
    .brand { display: flex; align-items: center; gap: 11px; }
    .mark {
      width: 34px; height: 34px; border-radius: 9px; display: grid; place-items: center;
      background: var(--accent); color: var(--bg); font-weight: 700; font-size: 1.05rem;
    }
    .brand .name { font-weight: 700; font-size: 1.06rem; letter-spacing: -.01em; line-height: 1.1; }
    .brand .sub { display: block; }

    .section-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
    .icon-btn {
      border: 1px solid var(--border); background: var(--card); color: var(--text);
      width: 28px; height: 28px; border-radius: 7px; cursor: pointer; display: grid; place-items: center;
      font-size: 1rem; line-height: 1; position: relative; overflow: hidden;
    }

    .model-list { display: grid; gap: 9px; }
    .model-card {
      width: 100%; text-align: left; cursor: pointer; position: relative;
      border: 1px solid var(--border); background: var(--card); color: var(--text);
      border-radius: 10px; padding: 10px; display: grid; grid-template-columns: 38px 1fr; gap: 10px;
    }
    .model-card .mono-monogram {
      width: 38px; height: 38px; border-radius: 8px; display: grid; place-items: center;
      background: var(--accent-soft); color: var(--accent); font-weight: 600;
      font-family: "JetBrains Mono", monospace; font-size: 1rem;
    }
    .model-card .m-name { display: block; font-weight: 600; line-height: 1.15; }
    .model-card .m-desc { display: block; margin-top: 3px; color: var(--muted); font-size: .76rem; line-height: 1.45; }
    .model-card.active { border-color: var(--accent); background: var(--accent-soft); }
    .model-card.active .mono-monogram { background: var(--accent); color: var(--bg); }

    .convo-wrap { flex: 1; min-height: 0; display: flex; flex-direction: column; }
    .convo-list { overflow-y: auto; display: grid; gap: 6px; padding-right: 2px; align-content: start; }
    .convo {
      display: flex; align-items: center; gap: 8px; cursor: pointer;
      border: 1px solid transparent; background: transparent; color: var(--text);
      border-radius: 8px; padding: 8px 9px; text-align: left; width: 100%;
    }
    .convo .c-title { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: .85rem; }
    .convo .c-del { opacity: 0; border: 0; background: transparent; color: var(--muted); cursor: pointer; font-size: .9rem; padding: 2px 4px; border-radius: 5px; }
    .convo:hover { background: var(--accent-soft); }
    .convo:hover .c-del { opacity: 1; }
    .convo.active { background: var(--accent-soft); border-color: var(--accent); }
    .convo-empty { color: var(--muted); font-size: .8rem; padding: 8px 9px; }

    .side-foot { border-top: 1px solid var(--border); padding-top: 14px; display: flex; align-items: center; justify-content: space-between; gap: 10px; }
    .theme-toggle {
      border: 1px solid var(--border); background: var(--card); color: var(--text);
      border-radius: 8px; padding: 8px 12px; cursor: pointer; position: relative; overflow: hidden;
      display: inline-flex; align-items: center; gap: 8px;
    }

    /* ---- Main ---- */
    .main { min-width: 0; display: grid; grid-template-rows: auto 1fr auto; background: var(--bg); }
    .topbar {
      display: flex; align-items: center; justify-content: space-between; gap: 16px;
      padding: 16px clamp(18px,4vw,46px); border-bottom: 1px solid var(--border); background: var(--bg-soft);
    }
    .topbar h1 { margin: 0; font-size: 1.02rem; font-weight: 600; letter-spacing: -.01em; max-width: 60ch; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .status { display: inline-flex; align-items: center; gap: 7px; }
    .status .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--muted); }
    .status[data-state="streaming"] .dot, .status[data-state="thinking"] .dot { background: var(--blue); }
    .status[data-state="error"] .dot { background: #c2410c; }

    /* ---- Canvas (grid lives ONLY here) ---- */
    .canvas {
      position: relative; overflow-y: auto; min-height: 0;
      padding: 28px clamp(18px,4vw,46px);
      background-color: var(--bg);
      background-image:
        linear-gradient(var(--grid-line) 1px, transparent 1px),
        linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
      background-size: 32px 32px;
    }
    .spotlight {
      position: absolute; inset: 0; pointer-events: none; z-index: 0; opacity: 0;
      background: radial-gradient(600px circle at var(--cursor-x, -999px) var(--cursor-y, -999px),
        rgba(37,99,235,0.10), transparent 60%);
    }
    .stream { position: relative; z-index: 1; display: flex; flex-direction: column; gap: 14px; max-width: 880px; margin: 0 auto; }

    .msg { max-width: 86%; border: 1px solid var(--border); border-radius: 12px; padding: 12px 16px; background: var(--card); box-shadow: var(--shadow-soft); }
    .msg.user { align-self: flex-end; background: var(--accent); color: var(--bg); border-color: var(--accent); }
    .msg.assistant { align-self: flex-start; }
    .msg.error { align-self: center; max-width: 620px; color: #9a3412; background: rgba(194,65,12,.07); border-color: rgba(194,65,12,.28); }
    .msg .role { margin-bottom: 6px; }
    .msg.user .role { color: rgba(255,255,255,.7); }
    .msg .body { white-space: pre-wrap; word-wrap: break-word; }
    .msg .body p { margin: 0 0 8px; }
    .msg .body p:last-child { margin-bottom: 0; }
    .msg .body strong { font-weight: 600; }
    .msg .body a { color: inherit; text-underline-offset: 2px; }
    .msg.assistant.streaming { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent-soft), var(--shadow-soft); }

    code.inline { font-family: "JetBrains Mono", monospace; font-size: .85em; background: var(--accent-soft); padding: 1px 5px; border-radius: 5px; }
    .codeblock { position: relative; margin: 8px 0; }
    pre.code { margin: 0; background: var(--code-bg); color: var(--code-fg); border-radius: 9px; padding: 13px 14px; overflow-x: auto; font-family: "JetBrains Mono", monospace; font-size: .82rem; line-height: 1.6; }
    .copy-code { position: absolute; top: 8px; right: 8px; border: 1px solid rgba(255,255,255,.16); background: rgba(255,255,255,.06); color: #d4d4d4; border-radius: 6px; padding: 3px 9px; cursor: pointer; font-family: "JetBrains Mono", monospace; font-size: .6rem; text-transform: uppercase; letter-spacing: .12em; }

    .empty { position: relative; z-index: 1; height: 100%; display: grid; place-content: center; justify-items: center; text-align: center; gap: 18px; color: var(--muted); }
    .orb { width: 76px; height: 76px; border-radius: 50%; background: var(--blue); box-shadow: 0 0 0 10px rgba(37,99,235,.10), 0 0 46px 6px rgba(37,99,235,.45); }
    .empty h2 { margin: 0; color: var(--text); font-size: 1.5rem; font-weight: 700; letter-spacing: -.02em; }
    .empty p { margin: 0; max-width: 42ch; line-height: 1.55; }

    /* ---- Composer ---- */
    .composer-wrap { padding: 14px clamp(18px,4vw,46px) 20px; background: var(--bg); border-top: 1px solid var(--border); }
    .composer { max-width: 880px; margin: 0 auto; background: var(--card); border: 1px solid var(--border); border-radius: 14px; display: grid; grid-template-columns: 1fr auto; gap: 10px; padding: 10px; box-shadow: var(--shadow-soft); }
    .composer textarea { min-height: 52px; max-height: 200px; resize: none; border: 0; outline: 0; padding: 10px 12px; background: transparent; }
    .send {
      align-self: end; border: 0; border-radius: 10px; cursor: pointer; position: relative; overflow: hidden;
      background: var(--blue); color: #fff; padding: 12px 20px; font-weight: 600;
      box-shadow: 0 6px 18px rgba(37,99,235,.40);
    }
    .send:disabled { opacity: .5; cursor: wait; }

    /* ============ MOTION (felt, not seen) ============ */
    @media (prefers-reduced-motion: no-preference) {
      .icon-btn, .theme-toggle, .model-card, .convo, .send, .composer { transition: transform .16s ease, border-color .16s ease, background .16s ease, box-shadow .2s ease, color .16s ease; }
      .canvas .spotlight { opacity: 1; }
      .model-card:hover, .convo:hover, .theme-toggle:hover, .icon-btn:hover { transform: translateY(-2px); box-shadow: var(--shadow-soft); }
      .send:hover { background: var(--blue-hover); transform: scale(1.05); box-shadow: 0 10px 26px rgba(37,99,235,.55); }
      .send:active { transform: scale(.95); }
      .composer:focus-within { transform: translateY(-2px); box-shadow: 0 0 0 1px var(--ring), var(--shadow-deep); animation: glowpulse 2.6s ease-in-out infinite; }

      .msg.user { animation: slidein-r .34s cubic-bezier(.2,.7,.2,1) both; }
      .msg.assistant { animation: slidein-l .34s cubic-bezier(.2,.7,.2,1) both; }
      .orb { animation: float 4.5s ease-in-out infinite, orbglow 3.2s ease-in-out infinite; }
      .model-card, .convo { animation: slidein-l .3s ease both; }
      .ripple { position: absolute; border-radius: 50%; transform: scale(0); background: rgba(0,0,0,.18); pointer-events: none; animation: ripple .5s ease-out; }
      .send .ripple { background: rgba(255,255,255,.5); }
    }
    @keyframes slidein-r { from { opacity: 0; transform: translateX(22px); } to { opacity: 1; transform: translateX(0); } }
    @keyframes slidein-l { from { opacity: 0; transform: translateX(-22px); } to { opacity: 1; transform: translateX(0); } }
    @keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-9px); } }
    @keyframes orbglow { 0%,100% { box-shadow: 0 0 0 10px rgba(37,99,235,.08), 0 0 40px 4px rgba(37,99,235,.35); } 50% { box-shadow: 0 0 0 14px rgba(37,99,235,.12), 0 0 58px 10px rgba(37,99,235,.55); } }
    @keyframes glowpulse { 0%,100% { box-shadow: 0 0 0 1px var(--ring), var(--shadow-deep); } 50% { box-shadow: 0 0 0 3px var(--accent-soft), var(--shadow-deep); } }
    @keyframes ripple { to { transform: scale(2.6); opacity: 0; } }

    @media (max-width: 860px) {
      .shell { grid-template-columns: 1fr; grid-template-rows: auto 1fr; }
      .sidebar { flex-direction: row; flex-wrap: wrap; align-items: center; gap: 12px; }
      .convo-wrap { display: none; }
      .model-list { grid-template-columns: repeat(3, 1fr); flex: 1; }
      .model-card .m-desc { display: none; }
      .model-card { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="mark">Z</div>
        <div>
          <span class="name">Zynx</span>
          <span class="label sub">AI Console</span>
        </div>
      </div>

      <div>
        <div class="section-head"><span class="label">Model</span></div>
        <div class="model-list" id="models"></div>
      </div>

      <div class="convo-wrap">
        <div class="section-head">
          <span class="label">Chats</span>
          <button class="icon-btn" id="newChat" title="New chat" aria-label="New chat">+</button>
        </div>
        <div class="convo-list" id="convos"></div>
      </div>

      <div class="side-foot">
        <span class="label">Zynx.AI</span>
        <button class="theme-toggle" id="theme" aria-label="Toggle theme">
          <span class="label" id="themeLabel">Dark</span>
        </button>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <h1 id="title">New chat</h1>
        <div class="status label" id="status" data-state="ready"><span class="dot"></span><span id="statusText">Ready</span></div>
      </header>

      <section class="canvas" id="canvas">
        <div class="spotlight" id="spotlight"></div>
        <div class="stream" id="stream"></div>
        <div class="empty" id="empty">
          <div class="orb"></div>
          <div>
            <h2>Start a conversation</h2>
            <p>Pick a model and type below. Chats stay in this browser; the server only handles model calls.</p>
          </div>
        </div>
      </section>

      <div class="composer-wrap">
        <form class="composer" id="form">
          <textarea id="prompt" placeholder="Message Zynx..." rows="1" autocomplete="off"></textarea>
          <button class="send" id="send" type="submit">Send</button>
        </form>
      </div>
    </main>
  </div>

<script>
  const LS = { theme: 'zynx-theme', convos: 'zynx-convos', current: 'zynx-current' };
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const state = { models: {}, modelKey: 'glm_air', convos: [], currentId: null };
  const $ = (id) => document.getElementById(id);
  const els = {
    models: $('models'), convos: $('convos'), stream: $('stream'), empty: $('empty'),
    form: $('form'), prompt: $('prompt'), send: $('send'),
    status: $('status'), statusText: $('statusText'), title: $('title'),
    canvas: $('canvas'), spotlight: $('spotlight'), newChat: $('newChat'),
    theme: $('theme'), themeLabel: $('themeLabel')
  };

  /* ---------- helpers ---------- */
  function escapeHtml(s) { return s.replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c])); }
  function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }

  // safe markdown-lite: escape first, then inject only known-safe tags.
  // code blocks are stashed by index so inline rules never touch their contents.
  function renderMarkdown(src) {
    const blocks = [];
    let s = escapeHtml(src);
    s = s.replace(/```([\s\S]*?)```/g, (m, code) => {
      blocks.push(code.replace(/^\n/, '').replace(/\n$/, ''));
      return '@@ZCB' + (blocks.length - 1) + '@@';
    });
    s = s.replace(/`([^`\n]+)`/g, '<code class="inline">$1</code>');
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    s = s.replace(/@@ZCB(\d+)@@/g, (m, i) =>
      '<div class="codeblock"><button class="copy-code" type="button">Copy</button><pre class="code"><code>' + blocks[+i] + '</code></pre></div>');
    return s;
  }

  function setStatus(stateName, text) { els.status.dataset.state = stateName; els.statusText.textContent = text; }
  function currentConvo() { return state.convos.find((c) => c.id === state.currentId) || null; }
  function persist() { localStorage.setItem(LS.convos, JSON.stringify(state.convos)); localStorage.setItem(LS.current, state.currentId || ''); }

  function ripple(btn, evt) {
    if (reduce) return;
    const r = btn.getBoundingClientRect();
    const span = document.createElement('span');
    span.className = 'ripple';
    const size = Math.max(r.width, r.height);
    span.style.width = span.style.height = size + 'px';
    span.style.left = (evt.clientX - r.left - size / 2) + 'px';
    span.style.top = (evt.clientY - r.top - size / 2) + 'px';
    btn.appendChild(span);
    setTimeout(() => span.remove(), 520);
  }
  function bindRipple(btn) { btn.addEventListener('click', (e) => ripple(btn, e)); }

  /* ---------- theme ---------- */
  function applyTheme(t) {
    document.documentElement.dataset.theme = t;
    els.themeLabel.textContent = t === 'dark' ? 'Light' : 'Dark';
    localStorage.setItem(LS.theme, t);
  }
  els.theme.addEventListener('click', () => applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
  bindRipple(els.theme);

  /* ---------- models ---------- */
  function renderModels() {
    els.models.innerHTML = Object.entries(state.models).map(([key, m]) => {
      const active = key === state.modelKey ? ' active' : '';
      const mg = (m.label || '?').slice(0, 1).toUpperCase();
      return '<button class="model-card' + active + '" data-model="' + key + '">' +
        '<span class="mono-monogram">' + mg + '</span>' +
        '<span><span class="m-name">' + escapeHtml(m.label) + '</span>' +
        '<span class="m-desc">' + escapeHtml(m.desc) + '</span></span></button>';
    }).join('');
    els.models.querySelectorAll('.model-card').forEach((btn) => {
      bindRipple(btn);
      btn.addEventListener('click', () => {
        state.modelKey = btn.dataset.model;
        const c = currentConvo(); if (c) { c.modelKey = state.modelKey; persist(); }
        renderModels();
      });
    });
  }

  /* ---------- conversations ---------- */
  function renderConvos() {
    if (!state.convos.length) { els.convos.innerHTML = '<div class="convo-empty">No chats yet.</div>'; return; }
    els.convos.innerHTML = state.convos.map((c) => {
      const active = c.id === state.currentId ? ' active' : '';
      return '<button class="convo' + active + '" data-id="' + c.id + '">' +
        '<span class="c-title">' + escapeHtml(c.title || 'New chat') + '</span>' +
        '<span class="c-del" data-del="' + c.id + '" title="Delete">×</span></button>';
    }).join('');
    els.convos.querySelectorAll('.convo').forEach((btn) => {
      bindRipple(btn);
      btn.addEventListener('click', (e) => {
        if (e.target.dataset.del) { deleteConvo(e.target.dataset.del); return; }
        selectConvo(btn.dataset.id);
      });
    });
  }

  function newConvo() {
    const c = { id: uid(), title: 'New chat', modelKey: state.modelKey, messages: [] };
    state.convos.unshift(c);
    state.currentId = c.id;
    persist(); renderConvos(); renderConversation();
    els.prompt.focus();
  }
  function selectConvo(id) {
    state.currentId = id;
    const c = currentConvo();
    if (c) state.modelKey = c.modelKey || state.modelKey;
    persist(); renderModels(); renderConvos(); renderConversation();
  }
  function deleteConvo(id) {
    state.convos = state.convos.filter((c) => c.id !== id);
    if (state.currentId === id) state.currentId = state.convos[0] ? state.convos[0].id : null;
    if (!state.convos.length) { newConvo(); return; }
    persist(); renderConvos(); renderConversation();
  }

  /* ---------- rendering messages ---------- */
  function messageEl(role, html) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    const roleLabel = role === 'user' ? 'You' : role === 'assistant' ? 'Zynx' : 'Error';
    div.innerHTML = '<div class="role label">' + roleLabel + '</div><div class="body">' + html + '</div>';
    div.querySelectorAll('.copy-code').forEach(bindCopy);
    return div;
  }
  function bindCopy(btn) {
    btn.addEventListener('click', () => {
      const code = btn.parentElement.querySelector('code').innerText;
      navigator.clipboard.writeText(code).then(() => { btn.textContent = 'Copied'; setTimeout(() => btn.textContent = 'Copy', 1400); });
    });
  }
  function scrollDown() { els.canvas.scrollTop = els.canvas.scrollHeight; }

  function renderConversation() {
    const c = currentConvo();
    els.stream.innerHTML = '';
    if (!c || !c.messages.length) {
      els.empty.style.display = '';
      els.title.textContent = c ? (c.title || 'New chat') : 'New chat';
      return;
    }
    els.empty.style.display = 'none';
    els.title.textContent = c.title || 'New chat';
    c.messages.forEach((m) => {
      const html = m.role === 'assistant' ? renderMarkdown(m.content) : escapeHtml(m.content);
      els.stream.appendChild(messageEl(m.role, html));
    });
    scrollDown();
  }

  /* ---------- streaming reveal ---------- */
  function revealAssistant(el, full) {
    return new Promise((resolve) => {
      const body = el.querySelector('.body');
      if (reduce) { body.innerHTML = renderMarkdown(full); el.classList.remove('streaming'); resolve(); return; }
      el.classList.add('streaming');
      let i = 0;
      const step = Math.max(2, Math.round(full.length / 90));
      const tick = () => {
        i = Math.min(full.length, i + step);
        body.textContent = full.slice(0, i);
        scrollDown();
        if (i < full.length) { setTimeout(tick, 16); }
        else { body.innerHTML = renderMarkdown(full); body.querySelectorAll('.copy-code').forEach(bindCopy); el.classList.remove('streaming'); resolve(); }
      };
      tick();
    });
  }

  /* ---------- send ---------- */
  bindRipple(els.send);
  els.form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = els.prompt.value.trim();
    if (!text) return;
    let c = currentConvo();
    if (!c) { newConvo(); c = currentConvo(); }
    els.prompt.value = '';
    els.prompt.style.height = 'auto';

    c.messages.push({ role: 'user', content: text });
    if (c.messages.length === 1) c.title = text.slice(0, 46);
    persist(); renderConvos();
    els.empty.style.display = 'none';
    els.title.textContent = c.title;
    els.stream.appendChild(messageEl('user', escapeHtml(text)));
    scrollDown();

    setStatus('thinking', 'Thinking');
    els.send.disabled = true;
    try {
      const res = await fetch('/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_key: c.modelKey || state.modelKey, messages: c.messages })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Request failed');
      setStatus('streaming', 'Streaming');
      const aEl = messageEl('assistant', '');
      els.stream.appendChild(aEl);
      await revealAssistant(aEl, data.reply);
      c.messages.push({ role: 'assistant', content: data.reply });
      persist();
      setStatus('ready', 'Ready');
    } catch (err) {
      els.stream.appendChild(messageEl('error', escapeHtml(String(err.message || err))));
      scrollDown();
      setStatus('error', 'Error');
    } finally {
      els.send.disabled = false;
      els.prompt.focus();
    }
  });

  // textarea auto-grow + enter-to-send
  els.prompt.addEventListener('input', () => { els.prompt.style.height = 'auto'; els.prompt.style.height = Math.min(200, els.prompt.scrollHeight) + 'px'; });
  els.prompt.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); els.form.requestSubmit(); } });
  els.newChat.addEventListener('click', newConvo);
  bindRipple(els.newChat);

  /* ---------- cursor spotlight ---------- */
  if (!reduce) {
    els.canvas.addEventListener('mousemove', (e) => {
      const r = els.canvas.getBoundingClientRect();
      els.spotlight.style.setProperty('--cursor-x', (e.clientX - r.left) + 'px');
      els.spotlight.style.setProperty('--cursor-y', (e.clientY - r.top) + 'px');
    });
  }

  /* ---------- boot ---------- */
  applyTheme(localStorage.getItem(LS.theme) || 'light');
  try { state.convos = JSON.parse(localStorage.getItem(LS.convos) || '[]') || []; } catch (e) { state.convos = []; }
  state.currentId = localStorage.getItem(LS.current) || (state.convos[0] ? state.convos[0].id : null);

  fetch('/api/models').then((r) => r.json()).then((data) => {
    state.models = data.models || {};
    const c = currentConvo();
    state.modelKey = (c && c.modelKey) || data.default || state.modelKey;
    if (!state.convos.length) newConvo(); else { renderModels(); renderConvos(); renderConversation(); }
    renderModels();
  }).catch((err) => {
    setStatus('error', 'Error');
    els.empty.style.display = 'none';
    els.stream.appendChild(messageEl('error', 'Could not load models: ' + escapeHtml(String(err))));
  });
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML
