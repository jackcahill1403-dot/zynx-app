# Zynx.AI

A multi-model AI chat app built with Streamlit.

Tiers:
- **GLM-4.5 Air** - fast, strong instruction following, solid all-around work.
- **Kimi K2** - strong at coding, reasoning, and longer conversations.
- **Mistral Nemo** - quick chat and creative writing with lower latency.

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
# Optional fallback key
OPENROUTER_API_KEY = "..."

# Preferred: three keys per model
OPENROUTER_GLM_AIR_API_KEY_1 = "..."
OPENROUTER_GLM_AIR_API_KEY_2 = "..."
OPENROUTER_GLM_AIR_API_KEY_3 = "..."
OPENROUTER_KIMI_K2_API_KEY_1 = "..."
OPENROUTER_KIMI_K2_API_KEY_2 = "..."
OPENROUTER_KIMI_K2_API_KEY_3 = "..."
OPENROUTER_MISTRAL_NEMO_API_KEY_1 = "..."
OPENROUTER_MISTRAL_NEMO_API_KEY_2 = "..."
OPENROUTER_MISTRAL_NEMO_API_KEY_3 = "..."
TURSO_DATABASE_URL = "libsql://<db>-<org>.turso.io"   # persistent storage (cloud)
TURSO_AUTH_TOKEN = "..."
# ZYNX_OWNER_CODE = "..."   # to create the owner account
ZYNX_CLOUD = "1"            # hides the local-only Lite tier when hosted
```

> **Storage:** with `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN` set, all data
> persists in Turso/libSQL and survives restarts. Without them, the app uses a
> local SQLite file (`zynx_v2.db`) for development. Host Python must be **<= 3.13**
> (libSQL wheel availability).
