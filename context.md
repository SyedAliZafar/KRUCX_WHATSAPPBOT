# Project Context — Krucx WhatsApp AI Bot

This document is the full business and product context for anyone (human or AI) working on this project. Read this to understand the *why* behind every design decision.

---

## The Company

**Krucx Technologies LTD**
- Founded: 2016
- HQ: Germany + UK (clients worldwide)
- Clients served: 1,200+
- Positioning: AI-powered digital agency — websites, business automation, marketing, mobile apps, ERP

**What Krucx actually sells:**
- Custom websites and ecommerce stores (Shopify, WordPress, Magento)
- AI chatbots and workflow automation
- Odoo ERP implementations
- Mobile apps (Android, iOS, Flutter)
- Digital marketing (SEO, Google Ads, Meta Ads)
- Branding and UI/UX design

**Team:**
- Ali Zafar — General Manager
- Umair Ajmal — Web Head
- M. Irtaza — Digital Marketing Head
- Muhammad Usman Ghani — Business Development
- Jazib Munir — Design Head
- Hamza Butt — Senior Project Manager

**Contact:**
- hello@krucx.de
- Germany: +49 163 625 2297
- UK: +44 742 552 9752

---

## The Problem This Bot Solves

Krucx gets inbound leads via WhatsApp. Before this bot, someone had to manually respond to every prospect, ask basic qualification questions, figure out what they needed, and then hand them off to sales. This was slow, inconsistent, and didn't scale.

The bot replaces the first 5–10 messages of that conversation: it qualifies the lead, demonstrates Krucx's expertise for their specific industry, builds trust, and — only when appropriate — sends them a link to start a project or request a quote.

---

## The Bot's Job

**Not a chatbot. A junior solutions consultant.**

The bot is explicitly instructed NOT to be a generic FAQ responder. Its job is:

1. **Understand the prospect's business** — what they do, their industry, company size
2. **Identify their biggest problem** — not pitch yet, just listen and understand
3. **Demonstrate expertise** — speak knowledgeably about their industry's typical pain points (logistics, ecommerce, healthcare, manufacturing, restaurants)
4. **Build trust** — give useful observations for free before pitching anything
5. **Qualify the lead** — score them 0–4 based on: industry known, problem known, size/budget signal, name given
6. **Escalate at the right moment** — only offer a link or next step when score ≥ 3 and the prospect seems ready

**What the bot must never do:**
- Ask for contact email early (trust must come first)
- Re-ask a question it already knows the answer to
- Send walls of text (2–4 lines max per message, WhatsApp style)
- Be salesy or pushy
- Fabricate industry knowledge it doesn't have

---

## Lead Qualification Framework

The bot tracks these fields for every prospect:

| Field | Why it matters |
|-------|---------------|
| `name` | Personalisation, basic trust signal |
| `company_type` | Contextualises their needs |
| `industry` | Unlocks industry expert mode |
| `company_size` | Affects solution complexity and budget |
| `main_problem` | The core of the pitch — what exactly are we solving? |
| `current_tools` | Reveals integration requirements |
| `budget` | Filters out window shoppers |
| `timeline` | Urgency signal |

**Qualification score (0–4):**
- +1 if industry is known
- +1 if main problem is known
- +1 if company size OR budget is known
- +1 if name is known

Score ≥ 3 + industry + problem = **qualified** → bot may offer escalation link.

The score and known fields are tracked in the `LeadProfile` dataclass and persisted to the `leads` DB table. This means the bot will never ask the same question twice even if the conversation spans multiple sessions.

---

## Conversation Flow (Sales Sequence)

The bot follows this sequence, in order. It does not skip ahead:

```
1. Greet + open question
   "Hi! Thanks for reaching out to Krucx. What's your business, and what's
   the main thing you're hoping to improve?"

2. Understand the problem
   Ask naturally, one question at a time. Never interrogate.

3. Demonstrate industry expertise
   Once industry is known: mention specific workflows, common bottlenecks,
   realistic solutions — WITHOUT pitching yet. Show you understand their world.

4. Give value
   Offer a useful observation or quick suggestion for free.

5. Suggest a relevant Krucx solution
   Match their problem to a specific service.

6. Offer a next step
   Only when ready: "Want me to get our team to put together a quick proposal?
   Here's how to kick things off: [link]"
```

---

## Industry Expert Mode

When the bot detects a known industry, it switches into expert mode and speaks knowledgeably about that industry's typical pain points. The knowledge base (`knowledge_base.json`) contains:

- **Logistics**: manual order entry, email-to-SAP data entry, dispatch bottlenecks, POD management, customer tracking
- **Healthcare**: missed appointments, manual booking, patient communication overhead
- **Restaurants**: no-shows, reservation management, customer retention
- **Manufacturing**: production tracking, inventory issues, ERP inefficiencies, quality management
- **Ecommerce**: cart abandonment, customer support volume, inventory sync, conversion rates

For industries NOT in this list, the bot asks one open question about their workflow instead of guessing.

---

## Escalation Links

The bot has three escalation paths depending on where the prospect is:

| Link | When to use |
|------|------------|
| `https://krucx.de/start-a-project/` | Ready to start, knows what they want |
| `https://krucx.de/get-a-free-quote/` | Interested, wants to know cost first |
| `https://krucx.de/portfolio/` | Curious but not yet convinced — show proof |

The bot only sends ONE link per conversation, chosen based on context. Never sends all three.

---

## Technical Decisions and Why

**DeepSeek, not OpenAI/Claude**
DeepSeek's `deepseek-chat` model is used because it's cost-effective and capable for this task. The OpenAI SDK is used to talk to it (DeepSeek's API is OpenAI-compatible). The model can be swapped by changing two constants in `conversation_engine.py`.

**Two API calls per turn (extraction + generation)**
The profile extraction call (`temperature=0`, JSON mode) pulls structured data from each message — this is what enforces "never re-ask" at the *code* level rather than relying on the LLM to remember. The generation call (`temperature=0.7`) produces the actual reply. They run sequentially today; parallelising them is the main performance win available.

**Twilio, not Meta Cloud API**
Meta Cloud API requires a verified Facebook Business Account and Meta app review for the `messages` permission — weeks of process. Twilio sandbox is operational in 2 minutes with zero verification. Same codebase works for prod by swapping credentials.

**SQLite → PostgreSQL via DATABASE_URL**
SQLite requires zero configuration and is enough for a single-server deployment serving <100 concurrent conversations. The `DATABASE_URL` env var makes PostgreSQL a one-line switch for higher scale.

**No TwiML response — Twilio REST API for sends**
Twilio allows two patterns for sending replies: TwiML (return XML in the webhook response) or REST API (call `client.messages.create()` separately). TwiML couples the reply to the HTTP response timeout (~15s). Since DeepSeek can take 4–10s, using the REST API decouples them — the webhook returns 200 immediately and the reply is sent asynchronously.

**Single-file dashboard, no frontend framework**
The admin dashboard is one HTML file with Tailwind (CDN) and vanilla JS. No build step, no node_modules, no deployment pipeline for the frontend. It's an internal tool — simplicity beats sophistication here.

---

## What Success Looks Like

A qualified lead is someone the bot has learned:
- Who they are (name, company type)
- What industry they're in
- What their main problem is
- Enough signal (size or budget) to know they're a real prospect

At that point the bot offers a relevant next step, the lead clicks through, and a human from Krucx takes over. The bot's job is done.

**The bot should feel like texting a knowledgeable colleague at Krucx — not a support bot.**
