"""
bot_handler.py — Orchestrates one full conversation turn.

Flow for every incoming WhatsApp message:
  1. Load (or create) the Lead row for this phone number
  2. Reconstruct in-memory LeadProfile from DB fields
  3. Load full conversation history from Message rows
  4. Extract profile updates from user message and merge
  5. Generate bot reply via DeepSeek
  6. Detect whether escalation was offered in the reply
  7. Persist updated profile fields back to Lead row
  8. Save user message + bot reply as two new Message rows
  9. Send reply via Twilio REST API
 10. Return reply text (for logging / tests)

Important: the reply is sent via twilio_client.messages.create() rather
than a TwiML response body. This decouples the ~2-3s DeepSeek latency
from the Twilio webhook HTTP response, avoiding timeout retries.
"""

import json
import os
from typing import Optional, Tuple

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from twilio.rest import Client as TwilioClient

from .database import Lead, Message
from .lead_profile import LeadProfile
from . import conversation_engine as engine

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

OPENING_MESSAGE = (
    "Hi! 👋 Thanks for reaching out to Krucx. "
    "What's your business, and what's the main thing you're hoping to improve?"
)


# ---------------------------------------------------------------------------
# DB ↔ LeadProfile conversion
# ---------------------------------------------------------------------------

def _db_lead_to_profile(lead: Lead) -> LeadProfile:
    """Reconstruct an in-memory LeadProfile from a Lead ORM row."""
    tools = json.loads(lead.current_tools) if lead.current_tools else []
    return LeadProfile(
        phone_number=lead.phone_number,
        db_id=lead.id,
        name=lead.name,
        company_type=lead.company_type,
        industry=lead.industry,
        company_size=lead.company_size,
        main_problem=lead.main_problem,
        current_tools=tools,
        budget=lead.budget,
        timeline=lead.timeline,
        turns_count=lead.turns_count,
        escalation_offered=lead.escalation_offered,
    )


def _apply_profile_to_lead(lead: Lead, profile: LeadProfile) -> None:
    """Write profile fields back to the ORM Lead object (does not commit)."""
    lead.name = profile.name
    lead.company_type = profile.company_type
    lead.industry = profile.industry
    lead.company_size = profile.company_size
    lead.main_problem = profile.main_problem
    lead.current_tools = json.dumps(profile.current_tools)
    lead.budget = profile.budget
    lead.timeline = profile.timeline
    lead.qualification_score = profile.qualification_score()
    lead.escalation_offered = profile.escalation_offered
    lead.turns_count = profile.turns_count


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_or_create_lead(db: Session, phone_number: str) -> Tuple[Lead, bool]:
    """
    Look up Lead by phone_number.

    Returns (lead, is_new). If new, persists the opening greeting as the
    first assistant Message and sends it via Twilio.
    Handles the race-condition case where two concurrent requests try to
    create the same lead simultaneously by catching IntegrityError.
    """
    lead = db.query(Lead).filter(Lead.phone_number == phone_number).first()
    if lead is not None:
        return lead, False

    try:
        lead = Lead(phone_number=phone_number)
        db.add(lead)
        db.flush()   # populate lead.id without committing
        opening_msg = Message(
            lead_id=lead.id,
            role="assistant",
            content=OPENING_MESSAGE,
        )
        db.add(opening_msg)
        db.commit()
        db.refresh(lead)
        _send_whatsapp(phone_number, OPENING_MESSAGE)
        return lead, True
    except IntegrityError:
        db.rollback()
        lead = db.query(Lead).filter(Lead.phone_number == phone_number).first()
        return lead, False


def _load_history(db: Session, lead_id: int) -> list:
    """Return conversation history as list of {role, content} dicts."""
    rows = (
        db.query(Message)
        .filter(Message.lead_id == lead_id)
        .order_by(Message.timestamp)
        .all()
    )
    return [{"role": row.role, "content": row.content} for row in rows]


# ---------------------------------------------------------------------------
# Twilio
# ---------------------------------------------------------------------------

def _send_whatsapp(to: str, body: str) -> Optional[str]:
    """
    Send a WhatsApp message via Twilio REST API.
    Returns the message SID on success, None on failure.
    A Twilio failure should never crash the webhook handler.
    """
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        print("[warn] Twilio credentials not set — skipping send")
        return None
    try:
        msg = twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=to,
            body=body,
        )
        return msg.sid
    except Exception as e:
        print(f"[error] Twilio send failed to {to}: {e}")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def handle_incoming_message(db: Session, from_number: str, user_text: str) -> str:
    """
    Full turn handler. Called by main.py for every POST /webhook.

    Args:
        db:          SQLAlchemy session (injected by FastAPI Depends)
        from_number: e.g. "whatsapp:+49163625xxxx"
        user_text:   raw message body from Twilio

    Returns:
        The reply text that was sent.
    """
    # Steps 1–2: get/create Lead row, reconstruct in-memory profile
    lead, is_new = _get_or_create_lead(db, from_number)
    if is_new:
        return OPENING_MESSAGE
    profile = _db_lead_to_profile(lead)

    # Step 3: load prior history (chronological)
    history = _load_history(db, lead.id)

    # Step 4: extract new fields from this message and merge
    updates = engine.extract_profile_updates(user_text)
    profile.merge_updates(updates)
    profile.turns_count += 1

    # Step 5: generate reply (history does not yet include current user msg)
    reply = engine.generate_reply(profile, history, user_text)

    # Step 6: detect escalation
    if engine.detect_escalation_offered(reply):
        profile.escalation_offered = True

    # Step 7: persist profile changes back to Lead row
    _apply_profile_to_lead(lead, profile)

    # Step 8: append both messages to the log
    db.add(Message(lead_id=lead.id, role="user", content=user_text))
    db.add(Message(lead_id=lead.id, role="assistant", content=reply))
    db.commit()

    # Step 9: send via Twilio
    _send_whatsapp(from_number, reply)

    return reply
