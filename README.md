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
# ZYNX_OWNER_CODE = "..."   # to create the owner account
ZYNX_CLOUD = "1"            # hides the local-only Lite tier when hosted
```
