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
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Zynx</title>
  <style>
    :root {
      --charcoal: #0d0d0d;
      --charcoal-2: #181818;
      --charcoal-3: #252525;
      --white: #ffffff;
      --paper: #f6f6f1;
      --paper-2: #edede8;
      --ink: #171717;
      --muted: #686862;
      --line: rgba(13,13,13,.13);
      --shadow: rgba(0,0,0,.18);
      --radius: 8px;
      --font: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      --mono: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
    }
    * { box-sizing: border-box; }
    html, body { min-height: 100%; }
    body {
      margin: 0;
      color: var(--ink);
      font-family: var(--font);
      background-color: #0d0d0d;
      background-image:
        linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px);
      background-size: 32px 32px;
    }
    button, textarea { font: inherit; }
    .shell { min-height: 100vh; display: grid; grid-template-columns: 286px minmax(0, 1fr); }
    .sidebar {
      background: rgba(255,255,255,.94); border-right: 1px solid var(--line);
      padding: 22px 16px; display: flex; flex-direction: column; gap: 18px;
      box-shadow: 10px 0 30px rgba(0,0,0,.12);
    }
    .brand { display: flex; align-items: center; gap: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--line); }
    .mark { width: 34px; height: 34px; border-radius: 8px; background: var(--charcoal); color: var(--white); display: grid; place-items: center; font-weight: 800; letter-spacing: 0; }
    .brand strong { display: block; font-size: 1.05rem; letter-spacing: 0; }
    .brand span { display: block; font-family: var(--mono); color: var(--muted); font-size: .68rem; text-transform: uppercase; letter-spacing: .14em; }
    .model-list { display: grid; gap: 10px; }
    .model-card {
      width: 100%; border: 1px solid var(--line); background: var(--white); color: var(--ink);
      border-radius: var(--radius); padding: 11px; display: grid; grid-template-columns: 42px 1fr;
      gap: 11px; text-align: left; cursor: pointer; transition: border-color .14s ease, background .14s ease, transform .14s ease;
    }
    .model-card:hover { transform: translateY(-1px); border-color: rgba(13,13,13,.32); }
    .model-card.active { background: var(--charcoal); color: var(--white); border-color: var(--charcoal); }
    .model-card img { width: 42px; height: 42px; object-fit: contain; border-radius: 7px; background: var(--paper); }
    .model-card .name { font-weight: 750; line-height: 1.1; }
    .model-card .desc { margin-top: 4px; color: var(--muted); font-size: .78rem; line-height: 1.32; }
    .model-card.active .desc { color: rgba(255,255,255,.68); }
    .side-note { margin-top: auto; border-top: 1px solid var(--line); padding-top: 14px; color: var(--muted); font-size: .8rem; line-height: 1.45; }
    .main { min-width: 0; display: grid; grid-template-rows: auto 1fr auto; background: rgba(246,246,241,.94); }
    .topbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px clamp(18px, 4vw, 52px); border-bottom: 1px solid var(--line); background: rgba(255,255,255,.72); backdrop-filter: blur(8px); }
    .topbar h1 { margin: 0; font-size: clamp(1.4rem, 2.4vw, 2.15rem); letter-spacing: 0; }
    .status { font-family: var(--mono); color: var(--muted); font-size: .72rem; text-transform: uppercase; letter-spacing: .12em; }
    .messages { overflow-y: auto; padding: 30px clamp(18px, 4vw, 52px) 22px; display: flex; flex-direction: column; gap: 16px; }
    .empty { margin: auto; max-width: 700px; text-align: center; color: var(--muted); }
    .empty .logo { color: var(--ink); font-weight: 850; font-size: clamp(2.4rem, 6vw, 5rem); letter-spacing: 0; }
    .empty p { line-height: 1.6; }
    .msg { max-width: min(760px, 92%); border: 1px solid var(--line); border-radius: var(--radius); padding: 14px 16px; line-height: 1.68; white-space: pre-wrap; box-shadow: 0 10px 28px rgba(0,0,0,.04); }
    .msg.user { align-self: flex-end; background: var(--charcoal); color: var(--white); border-color: var(--charcoal); }
    .msg.assistant { align-self: flex-start; background: var(--white); color: var(--ink); }
    .msg.error { align-self: center; color: #8a1f1f; background: #fff1f1; border-color: rgba(138,31,31,.22); }
    .composer-wrap { padding: 14px clamp(18px, 4vw, 52px) 22px; background: linear-gradient(180deg, rgba(246,246,241,0), rgba(246,246,241,.98) 26%); }
    .composer { max-width: 940px; margin: 0 auto; background: var(--white); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: 0 18px 40px rgba(0,0,0,.12); display: grid; grid-template-columns: 1fr auto; gap: 10px; padding: 10px; }
    textarea { min-height: 54px; max-height: 180px; resize: vertical; border: 0; outline: 0; padding: 12px; background: transparent; color: var(--ink); }
    .send { align-self: end; border: 0; border-radius: 7px; background: var(--charcoal); color: var(--white); padding: 12px 17px; cursor: pointer; font-weight: 750; }
    .send:disabled { opacity: .45; cursor: wait; }
    @media (max-width: 840px) { .shell { grid-template-columns: 1fr; } .sidebar { border-right: 0; border-bottom: 1px solid var(--line); } .model-list { grid-template-columns: repeat(3, minmax(0, 1fr)); } .model-card { grid-template-columns: 1fr; } .model-card img { width: 34px; height: 34px; } }
    @media (max-width: 560px) { .model-list { grid-template-columns: 1fr; } .composer { grid-template-columns: 1fr; } .send { width: 100%; } }
  </style>
</head>
<body>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand"><div class="mark">Z</div><div><strong>Zynx</strong><span>AI Console</span></div></div>
      <div class="model-list" id="models"></div>
      <div class="side-note">White-first interface, charcoal controls, OpenRouter models, no Streamlit runtime.</div>
    </aside>
    <main class="main">
      <header class="topbar"><h1 id="chatTitle">New chat</h1><div class="status" id="status">Ready</div></header>
      <section class="messages" id="messages">
        <div class="empty" id="empty"><div class="logo">Zynx</div><p>Pick a model and start typing. Your chat stays in this browser while the server handles model calls.</p></div>
      </section>
      <div class="composer-wrap"><form class="composer" id="form"><textarea id="prompt" placeholder="Message Zynx..." autocomplete="off"></textarea><button class="send" id="send" type="submit">Send</button></form></div>
    </main>
  </div>
<script>
  const state = { models: {}, modelKey: 'glm_air', messages: [] };
  const els = { models: document.getElementById('models'), messages: document.getElementById('messages'), empty: document.getElementById('empty'), form: document.getElementById('form'), prompt: document.getElementById('prompt'), send: document.getElementById('send'), status: document.getElementById('status'), title: document.getElementById('chatTitle') };
  function setStatus(text) { els.status.textContent = text; }
  function escapeHtml(s) { return s.replace(/[&<>"']/g, function(c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]; }); }
  function renderModels() {
    els.models.innerHTML = Object.entries(state.models).map(function(entry) {
      const key = entry[0]; const model = entry[1]; const active = key === state.modelKey ? ' active' : '';
      return '<button class="model-card' + active + '" data-model="' + key + '"><img src="' + model.logo + '" alt="' + model.label + ' logo" onerror="this.style.display=\'none\'"><span><span class="name">' + model.label + '</span><span class="desc">' + model.desc + '</span></span></button>';
    }).join('');
    els.models.querySelectorAll('button').forEach(function(btn) { btn.addEventListener('click', function() { state.modelKey = btn.dataset.model; renderModels(); }); });
  }
  function addMessage(role, content) {
    if (els.empty) els.empty.remove();
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    div.innerHTML = escapeHtml(content);
    els.messages.appendChild(div);
    els.messages.scrollTop = els.messages.scrollHeight;
  }
  async function loadModels() {
    const res = await fetch('/api/models');
    const data = await res.json();
    state.models = data.models;
    state.modelKey = data.default || state.modelKey;
    renderModels();
  }
  els.form.addEventListener('submit', async function(e) {
    e.preventDefault();
    const text = els.prompt.value.trim();
    if (!text) return;
    els.prompt.value = '';
    state.messages.push({ role: 'user', content: text });
    addMessage('user', text);
    setStatus('Thinking');
    els.send.disabled = true;
    try {
      const res = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model_key: state.modelKey, messages: state.messages }) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Request failed');
      state.messages.push({ role: 'assistant', content: data.reply });
      addMessage('assistant', data.reply);
      els.title.textContent = (state.messages[0] && state.messages[0].content ? state.messages[0].content.slice(0, 42) : 'New chat');
      setStatus('Ready');
    } catch (err) {
      addMessage('error', String(err.message || err));
      setStatus('Error');
    } finally {
      els.send.disabled = false;
      els.prompt.focus();
    }
  });
  els.prompt.addEventListener('keydown', function(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); els.form.requestSubmit(); } });
  loadModels().catch(function(err) { setStatus('Error'); addMessage('error', String(err)); });
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML
