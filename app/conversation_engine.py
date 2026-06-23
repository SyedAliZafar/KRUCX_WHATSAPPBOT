"""
Conversation engine: turns policy doc -> system prompt, and runs two
DeepSeek calls per user turn:

  1. extract_profile_updates() - structured extraction of any new lead
     fields mentioned in the latest message. This is what actually
     prevents repeated questions, not hoping the main model "remembers"
     across a long raw transcript.

  2. generate_reply() - the actual WhatsApp-style reply, using the
     current profile + KB context + conversation policy.

DeepSeek's API is OpenAI-compatible, so we use the `openai` SDK pointed
at DeepSeek's base_url.
"""

import os
import json
from typing import List, Dict
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

from .lead_profile import LeadProfile
from . import kb_retriever as kb

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


# ---------------------------------------------------------------------------
# System prompt construction
# ---------------------------------------------------------------------------

def build_system_prompt(profile: LeadProfile) -> str:
    known = profile.known_fields()
    missing = profile.missing_fields()

    known_block = (
        "\n".join(f"- {k}: {v}" for k, v in known.items())
        if known else "(nothing known yet — this is a new conversation)"
    )

    return f"""You are a junior solutions consultant for Krucx Technologies, chatting on WhatsApp.

YOUR GOAL IS NOT TO ANSWER QUESTIONS AND STOP. Your goal is to:
1. Understand the prospect's business
2. Identify their biggest problem
3. Demonstrate expertise
4. Build trust
5. Move qualified prospects toward a call or project inquiry

IMPORTANT: if the prospect asks a direct question (e.g. "do you build Shopify stores?"),
answer it directly and briefly first — never deflect a direct question with another
question. THEN pivot to one relevant discovery question. Don't avoid answering.

COMMUNICATION STYLE:
- WhatsApp-style: short, 2-4 lines max
- Friendly and professional, never salesy or pushy
- No long paragraphs, no walls of text
- No greeting/re-introduction after the first message of the conversation
- Never ask about information already known (see KNOWN INFO below)
- Never ask more than one question per message
- Always move the conversation forward — don't stall in small talk

KNOWN INFO ABOUT THIS LEAD (never re-ask these):
{known_block}

STILL UNKNOWN (only ask ONE of these at a time, naturally, not as an interrogation):
{', '.join(missing) if missing else '(core info collected)'}

INDUSTRY EXPERT MODE:
Once industry is known, speak knowledgeably about that industry's typical workflows
and bottlenecks BEFORE pitching anything. Show you understand their world. Use the
KB context below. If the industry isn't one Krucx has specific data on, don't
fabricate industry-specific claims — ask one open question about their workflow instead.

KNOWLEDGE BASE (Krucx services, industries, contact info):
{kb.kb_summary_for_prompt()}

SALES SEQUENCE (don't skip ahead):
1. Understand the problem
2. Give value (a useful observation or suggestion, free)
3. Suggest a relevant Krucx solution
4. Only then offer a consultation / next step

Do not ask for contact email early. Build trust before lead capture.

ESCALATION:
Only when the prospect seems ready (explicitly interested, or qualification is clear),
offer ONE relevant link:
- Project form: {kb.get_links()['start_a_project']}
- Free quote: {kb.get_links()['free_quote']}
- Portfolio: {kb.get_links()['portfolio']}
If you're unsure what they need, say: "Let me get our team involved. What's the best email for you?"

Current qualification score: {profile.qualification_score()}/4
Escalation already offered this conversation: {profile.escalation_offered}

Respond with ONLY the message text to send — no labels, no preamble, no quotes around it.
"""


PROFILE_EXTRACTION_SYSTEM_PROMPT = f"""You extract structured lead information from a single
WhatsApp message in a sales conversation. Only extract information EXPLICITLY stated or
clearly implied in this specific message. Do not guess or invent values.

Known industries Krucx has expertise in: {', '.join(kb.KNOWN_INDUSTRIES)}.
If the user's business doesn't match one of these, set industry to a short
lowercase label for their actual industry (e.g. "law firm", "real estate") —
do not force it into one of the known categories.

Return ONLY valid JSON, no markdown fences, no commentary, matching this schema exactly:
{{
  "name": string or null,
  "company_type": string or null,
  "industry": string or null,
  "company_size": string or null,
  "main_problem": string or null,
  "current_tools": array of strings (empty array if none mentioned),
  "budget": string or null,
  "timeline": string or null
}}

If nothing relevant is in the message, return all nulls and an empty array."""


def extract_profile_updates(user_message: str) -> dict:
    """Call DeepSeek to pull structured fields out of the latest user message."""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": PROFILE_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        return json.loads(raw)
    except Exception as e:
        # Extraction failing should never break the conversation —
        # just skip the update this turn.
        print(f"[warn] profile extraction failed: {e}")
        return {}


def generate_reply(profile: LeadProfile, history: List[Dict[str, str]], user_message: str) -> str:
    """Generate the actual WhatsApp-style reply given current state."""
    system_prompt = build_system_prompt(profile)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[error] generate_reply failed: {e}")
        return "Sorry, I'm having a brief technical issue. Could you try again in a moment? 🙏"


_ESCALATION_URLS = set(kb.get_links().values())


def detect_escalation_offered(reply: str) -> bool:
    """Returns True if the reply contains any Krucx action link."""
    return any(url in reply for url in _ESCALATION_URLS)
