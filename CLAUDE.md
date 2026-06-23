# CLAUDE.md — Krucx WhatsApp AI Bot

This file gives Claude Code the context it needs to work on this project without asking redundant questions.

---

## What this project is

A WhatsApp AI chatbot that qualifies leads for Krucx Technologies (AI/web/automation agency, founded 2016, Germany + UK). Prospects message a WhatsApp number, the bot converses naturally, extracts structured profile info, and sends qualified leads to an admin dashboard.

---

## Package manager

**Always use `uv`**, never `pip` directly.

```bash
uv sync                        # install / update venv
uv add <package>               # add dependency → updates pyproject.toml + uv.lock
uv add --group dev <package>   # add dev dependency
uv remove <package>            # remove dependency
uv run <command>               # run a command inside the venv
```

The venv is at `.venv/`. Source of truth is `pyproject.toml` + `uv.lock` (both committed). There is no `requirements.txt`.

---

## How to run

```bash
uv run uvicorn app.main:app --reload      # web server (port 8000)
uv run python scripts/chat_cli.py         # CLI test — no DB or Twilio needed
```

---

## Architecture

```
WhatsApp → Twilio → POST /webhook (app/main.py)
                        ↓
              bot_handler.handle_incoming_message()
               ├── database.py         (load/save Lead + Message rows)
               ├── conversation_engine.py  (2 DeepSeek calls per turn)
               │     ├── extract_profile_updates()  — JSON field extraction
               │     └── generate_reply()           — WhatsApp reply text
               └── kb_retriever.py     (lookup from data/knowledge_base.json)
```

Admin dashboard at `GET /` reads from `GET /admin/leads` and `GET /admin/leads/{id}/conversation`.

---

## Key files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI routes: webhook, admin API |
| `app/bot_handler.py` | One turn: DB ↔ profile ↔ AI ↔ Twilio |
| `app/conversation_engine.py` | DeepSeek calls + system prompt builder |
| `app/lead_profile.py` | `LeadProfile` dataclass — never re-ask known fields |
| `app/kb_retriever.py` | Read from `data/knowledge_base.json` |
| `app/database.py` | SQLAlchemy `Lead` + `Message` models, `get_db()`, `init_db()` |
| `data/knowledge_base.json` | Company info, services, FAQ, pricing, industries |
| `scripts/chat_cli.py` | Terminal test harness — tests bot logic without infra |
| `frontend/` | Static admin dashboard (HTML + CSS + JS, no build step) |

---

## Database

SQLite in dev (`krucx_leads.db`, auto-created at server startup). Switch to PostgreSQL by setting `DATABASE_URL` in `.env`.

Two tables:
- `leads` — one row per phone number, stores all profile fields + scores
- `messages` — append-only log, one row per conversation turn

No migrations tool configured. `init_db()` calls `Base.metadata.create_all()` at startup — safe to run repeatedly.

---

## AI / DeepSeek

- Model: `deepseek-chat` via OpenAI-compatible SDK pointed at `https://api.deepseek.com`
- Two calls per turn: field extraction (temp=0, JSON mode) + reply generation (temp=0.7, max 300 tokens)
- `generate_reply()` has a try/except — API errors return a graceful fallback string, never crash
- System prompt is rebuilt every turn from current `LeadProfile` state + KB summary
- Bot never re-asks a field already in the profile (enforced in code, not just the prompt)

---

## WhatsApp / Twilio

- Incoming: `POST /webhook` receives `From` (phone) and `Body` (text) as form fields
- Outgoing: `twilio_client.messages.create()` — NOT a TwiML response (decouples latency)
- Sandbox number for dev: `whatsapp:+14155238886`
- Media-only messages (empty `Body`) are silently ignored with 200 OK

---

## Conventions

- Python 3.8+ compatible (no `tuple[x, y]` — use `Tuple[x, y]` from `typing`)
- No comments unless the WHY is non-obvious
- No print-based logging in production paths — use `print(f"[warn] ...")` or `print(f"[error] ...")` for now (no logging framework yet)
- `load_dotenv()` is called at the top of every module that reads env vars
- `.env` is never committed — `.env.example` is the template
- All intra-package imports use relative form: `from .database import ...`, `from . import kb_retriever as kb`

---

## Environment variables

| Variable | Required | Default |
|----------|----------|---------|
| `DEEPSEEK_API_KEY` | Yes | — |
| `TWILIO_ACCOUNT_SID` | For live sends | — |
| `TWILIO_AUTH_TOKEN` | For live sends | — |
| `TWILIO_WHATSAPP_NUMBER` | For live sends | `whatsapp:+14155238886` |
| `DATABASE_URL` | No | `sqlite:///./krucx_leads.db` |
| `META_VERIFY_TOKEN` | No (future) | — |

---

## Known performance issue

Each conversation turn makes **two sequential DeepSeek API calls** (~2–5s each), so visible latency is 4–10s per reply. When fixing: parallelize with `asyncio.gather()` in `bot_handler.handle_incoming_message()` and cache `kb_summary_for_prompt()` output in `kb_retriever.py` rather than rebuilding it every turn.

---

## What NOT to do

- Don't add a migration framework (Alembic) unless the schema needs to change on a live DB
- Don't switch to Meta Cloud API without checking business verification requirements
- Don't cache the KB in memory across hot reloads — `kb_retriever.py` loads JSON at import time, which is fine
- Don't add frontend frameworks (React/Vue) to the dashboard — the static `frontend/` folder is intentional
- Don't use `pip` — always use `uv add` / `uv remove` / `uv sync`
- The venv Python is 3.14 (managed by uv), not the system 3.8 — don't assume system Python
- Don't use absolute imports for intra-package modules (e.g. `import app.database`) — use relative imports (`from .database import ...`)
