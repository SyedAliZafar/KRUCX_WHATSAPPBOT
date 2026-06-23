"""
main.py — FastAPI application for the Krucx WhatsApp AI Bot.

Routes:
  POST /webhook                         Twilio incoming message webhook
  GET  /webhook                         Meta Cloud API verification (future)
  GET  /admin/leads                     All leads as JSON
  GET  /admin/leads/{id}/conversation   Full conversation for one lead
  GET  /*                               Served from frontend/ static directory
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI, Form, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import Lead, Message, get_db, init_db
from .bot_handler import handle_incoming_message


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables once at startup if they don't exist yet."""
    init_db()
    yield


app = FastAPI(title="Krucx WhatsApp Bot", version="1.0.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# WhatsApp webhook (Twilio)
# ---------------------------------------------------------------------------

@app.post("/webhook", response_class=PlainTextResponse)
async def whatsapp_webhook(
    From: str = Form(...),
    Body: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """
    Twilio POSTs form-encoded fields for each incoming WhatsApp message.
    Returns empty 200 immediately — reply is sent via Twilio REST API inside
    bot_handler so DeepSeek latency doesn't affect the webhook timeout.
    """
    if not Body.strip():
        return ""
    try:
        handle_incoming_message(db=db, from_number=From, user_text=Body.strip())
    except Exception as e:
        print(f"[error] webhook handler failed for {From}: {e}")
    return ""


@app.get("/webhook", response_class=PlainTextResponse)
async def whatsapp_webhook_verify(
    hub_challenge: str = "",
    hub_verify_token: str = "",
):
    """Meta Cloud API verification challenge — not used by Twilio, kept for easy migration."""
    expected = os.environ.get("META_VERIFY_TOKEN", "")
    if expected and hub_verify_token != expected:
        raise HTTPException(status_code=403, detail="Invalid verify token")
    return hub_challenge


# ---------------------------------------------------------------------------
# Admin API
# ---------------------------------------------------------------------------

@app.get("/admin/leads")
async def list_leads(db: Session = Depends(get_db)):
    """All leads sorted by most recently updated, with last message preview."""
    # Single subquery to get the latest message per lead (avoids N+1)
    last_msg_subq = (
        db.query(
            Message.lead_id,
            func.max(Message.timestamp).label("max_ts"),
        )
        .group_by(Message.lead_id)
        .subquery()
    )
    last_msgs = (
        db.query(Message)
        .join(
            last_msg_subq,
            (Message.lead_id == last_msg_subq.c.lead_id)
            & (Message.timestamp == last_msg_subq.c.max_ts),
        )
        .all()
    )
    last_by_lead = {m.lead_id: m for m in last_msgs}

    leads = db.query(Lead).order_by(Lead.updated_at.desc()).all()
    result = []
    for lead in leads:
        last = last_by_lead.get(lead.id)
        result.append({
            "id": lead.id,
            "phone_number": lead.phone_number,
            "name": lead.name,
            "industry": lead.industry,
            "company_type": lead.company_type,
            "company_size": lead.company_size,
            "main_problem": lead.main_problem,
            "budget": lead.budget,
            "timeline": lead.timeline,
            "current_tools": lead.current_tools,
            "qualification_score": lead.qualification_score,
            "escalation_offered": lead.escalation_offered,
            "turns_count": lead.turns_count,
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
            "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
            "last_message": last.content[:120] if last else None,
            "last_message_role": last.role if last else None,
        })
    return result


@app.get("/admin/leads/{lead_id}/conversation")
async def get_conversation(lead_id: int, db: Session = Depends(get_db)):
    """Full conversation + lead profile for a single lead."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    messages = (
        db.query(Message)
        .filter(Message.lead_id == lead_id)
        .order_by(Message.timestamp)
        .all()
    )
    return {
        "lead": {
            "id": lead.id,
            "phone_number": lead.phone_number,
            "name": lead.name,
            "industry": lead.industry,
            "company_type": lead.company_type,
            "company_size": lead.company_size,
            "main_problem": lead.main_problem,
            "budget": lead.budget,
            "timeline": lead.timeline,
            "current_tools": lead.current_tools,
            "qualification_score": lead.qualification_score,
            "escalation_offered": lead.escalation_offered,
            "turns_count": lead.turns_count,
        },
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
            }
            for msg in messages
        ],
    }


# ---------------------------------------------------------------------------
# Frontend static files — must be mounted LAST so API routes take priority
# ---------------------------------------------------------------------------

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
