# Krucx WhatsApp AI Bot

AI-powered WhatsApp lead qualification bot for Krucx Technologies. Prospects message a WhatsApp number, the bot qualifies them through a natural conversation, and leads appear in an admin dashboard.

---

## Stack

| Layer | Technology |
|-------|-----------|
| AI model | DeepSeek (`deepseek-chat`) via OpenAI-compatible SDK |
| Web framework | FastAPI + Uvicorn |
| WhatsApp API | Twilio (sandbox for dev, provisioned number for prod) |
| Database | SQLite (dev) → PostgreSQL (prod) via SQLAlchemy |
| Package manager | [uv](https://docs.astral.sh/uv/) |

---

## Project Structure

```
KrucxBot/
├── app.py                  # FastAPI server — webhook + admin API routes
├── bot_handler.py          # Orchestration: DB ↔ AI ↔ Twilio
├── conversation_engine.py  # DeepSeek calls: reply generation + field extraction
├── kb_retriever.py         # Knowledge base lookup helpers
├── lead_profile.py         # LeadProfile dataclass (in-memory per conversation)
├── database.py             # SQLAlchemy models (Lead, Message) + session factory
├── knowledge_base.json     # Company info, services, FAQ, pricing, industries
├── chat_cli.py             # Local CLI test harness (no infra needed)
├── pyproject.toml          # Dependencies managed by uv
├── uv.lock                 # Locked dependency tree (commit this)
├── .env                    # Secrets — never commit
├── .env.example            # Template for .env
└── templates/
    └── dashboard.html      # Admin dashboard (Tailwind + vanilla JS)
```

---

## Setup

### 1. Install uv (if not already installed)

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install dependencies

```bash
uv sync
```

This creates a `.venv` folder and installs everything from `uv.lock`. Run this once after cloning, and again after pulling changes.

### 3. Configure environment

```bash
copy .env.example .env   # Windows
cp .env.example .env     # macOS/Linux
```

Then fill in `.env`:

```env
DEEPSEEK_API_KEY=sk-...           # from platform.deepseek.com
TWILIO_ACCOUNT_SID=ACxxxxxx       # from console.twilio.com
TWILIO_AUTH_TOKEN=xxxxxxxx
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
DATABASE_URL=sqlite:///./krucx_leads.db
```

---

## Running

### Development server

```bash
uv run uvicorn app:app --reload
```

- Server: `http://localhost:8000`
- Admin dashboard: `http://localhost:8000/`
- API docs: `http://localhost:8000/docs`

### CLI conversation test (no Twilio or DB needed)

```bash
uv run python chat_cli.py
```

Simulates a WhatsApp conversation in your terminal. Useful for testing bot behaviour before wiring up live infrastructure.

Commands during the chat:
- `/profile` — show what the bot has extracted so far (JSON)
- `/reset` — start a fresh conversation
- `/quit` — exit

---

## Connecting WhatsApp (Twilio Sandbox)

1. Go to [Twilio Console](https://console.twilio.com) → Messaging → Try it out → Send a WhatsApp message
2. Follow the sandbox join instructions (send a message from your phone)
3. Expose your local server with ngrok:
   ```bash
   ngrok http 8000
   ```
4. In Twilio sandbox settings, set the webhook URL:
   ```
   https://xxxx.ngrok.io/webhook
   ```
   Method: **HTTP POST**
5. WhatsApp the sandbox number — messages will appear in the dashboard and the bot will reply

For production, provision a real Twilio WhatsApp number and update `TWILIO_WHATSAPP_NUMBER` in `.env`.

---

## Managing Dependencies (uv)

```bash
# Add a new package
uv add requests

# Add a dev-only package
uv add --group dev pytest

# Remove a package
uv remove requests

# Upgrade all packages to latest allowed versions
uv lock --upgrade

# Sync venv after any pyproject.toml change
uv sync
```

`pyproject.toml` is the source of truth for dependencies. `uv.lock` pins exact versions — commit both files.

---

## Admin Dashboard

Open `http://localhost:8000/` while the server is running.

- **Left panel**: all leads sorted by last activity, with qualification score badges
- **Right panel**: click any lead to see the full conversation thread
- Refreshes automatically every 30 seconds
- Score: 0–1 = gray, 2–3 = yellow, 4 = green

---

## How the Bot Works

Each incoming WhatsApp message triggers two DeepSeek API calls:

1. **Field extraction** (`extract_profile_updates`) — pulls structured data (name, industry, problem, budget, etc.) from the message using JSON mode. Temperature 0 — deterministic.
2. **Reply generation** (`generate_reply`) — generates a WhatsApp-style reply using the current lead profile + knowledge base as context. Temperature 0.7.

The `LeadProfile` object tracks everything known about the lead so the bot never asks the same question twice. Qualification score (0–4) determines when to offer escalation links.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DEEPSEEK_API_KEY` | Yes | DeepSeek API key |
| `TWILIO_ACCOUNT_SID` | Yes (live) | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Yes (live) | Twilio auth token |
| `TWILIO_WHATSAPP_NUMBER` | Yes (live) | `whatsapp:+14155238886` (sandbox) |
| `DATABASE_URL` | No | Defaults to `sqlite:///./krucx_leads.db` |
| `META_VERIFY_TOKEN` | No | Only needed if switching to Meta Cloud API |
