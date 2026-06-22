# Zynx.AI

A multi-model AI chat app built with Streamlit.

Tiers:
- ⚡ **Zynx Supreme** — Gemini 2.5 Flash
- ☀️ **Zynx Everyday** — OpenRouter (free models)
- 💡 **Zynx Lite** — local model via Ollama (local runs only)

## Run locally
```bash
pip install -r requirements.txt
streamlit run ai_app.py
```

## Configuration
Set API keys in `.streamlit/secrets.toml` (local) or the Streamlit Cloud
**Secrets** box (deployed):
```toml
GEMINI_API_KEY = "..."
OPENROUTER_API_KEY = "..."
OPENROUTER_MODEL = "openrouter/free"
TURSO_DATABASE_URL = "libsql://<db>-<org>.turso.io"   # persistent storage (cloud)
TURSO_AUTH_TOKEN = "..."
# ZYNX_OWNER_CODE = "..."   # to create the owner account
ZYNX_CLOUD = "1"            # hides the local-only Lite tier when hosted
```

> **Storage:** with `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN` set, all data
> persists in Turso/libSQL and survives restarts. Without them, the app uses a
> local SQLite file (`zynx_v2.db`) for development. Host Python must be **<= 3.13**
> (libSQL wheel availability).
