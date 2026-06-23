# How to Run — Krucx WhatsApp AI Bot

## Prerequisites

- Python 3.8+ (the `.venv` will use Python 3.14 managed by uv)
- [uv](https://docs.astral.sh/uv/) installed — `pip install uv` or follow the installer below
- A DeepSeek API key (from [platform.deepseek.com](https://platform.deepseek.com))
- Twilio account (only needed for live WhatsApp sends — not required for CLI testing)

---

## Setup

1. **Install uv** (skip if already installed):
   ```bash
   # Windows
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   # macOS / Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   ```

3. **Create your `.env` file**:
   ```bash
   cp .env.example .env       # macOS/Linux
   copy .env.example .env     # Windows
   ```

4. **Fill in `.env`** — minimum required:
   ```env
   DEEPSEEK_API_KEY=sk-...
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
   DATABASE_URL=sqlite:///./krucx_leads.db
   ```

---

## Run the backend

```bash
uv run uvicorn app.main:app --reload
```

- API + dashboard: `http://localhost:8000/`
- Swagger docs: `http://localhost:8000/docs`
- The SQLite database (`krucx_leads.db`) is created automatically on first run

---

## View the dashboard

Open `http://localhost:8000/` in your browser while the server is running.

- Left panel lists all leads with last message preview and qualification score
- Click any lead to see the full conversation and extracted profile fields
- Refreshes automatically (leads: every 15s, active conversation: every 8s)

---

## Run the CLI test tool

Test bot logic without Twilio or a database — runs entirely in your terminal:

```bash
uv run python scripts/chat_cli.py
```

- Type messages as if you were a prospect on WhatsApp
- Commands: `/profile` (show extracted data), `/reset` (new conversation), `/quit`

---

## Connect real WhatsApp (Twilio sandbox)

1. Log in to [Twilio Console](https://console.twilio.com) → Messaging → Try it out → Send a WhatsApp message
2. Join the sandbox by sending the join phrase from your phone
3. Expose your local server:
   ```bash
   ngrok http 8000
   ```
4. Set the webhook URL in Twilio sandbox settings:
   ```
   https://YOUR_NGROK_ID.ngrok.io/webhook   (method: HTTP POST)
   ```
5. WhatsApp the sandbox number — messages appear in the dashboard, bot replies on WhatsApp

---

## Troubleshooting

- **`DEEPSEEK_API_KEY not set`** — check `.env` exists and the key is correct; run `uv run python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.environ.get('DEEPSEEK_API_KEY','NOT SET'))"`
- **Port 8000 already in use** — kill the other process or run on a different port: `uv run uvicorn app.main:app --reload --port 8001`
- **`ModuleNotFoundError: No module named 'app'`** — always run commands from the project root (`KrucxBot/`), not from inside a subfolder
- **Twilio not sending** — verify `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` are set; the server logs `[warn] Twilio credentials not set` if they are missing
- **Dashboard shows no leads** — send a message to the WhatsApp sandbox number first, or check `krucx_leads.db` exists
