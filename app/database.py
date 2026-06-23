"""
database.py — SQLAlchemy 2.x models and session factory.

Uses DATABASE_URL env var so the same code runs on SQLite (dev) and
PostgreSQL (prod) without any application code changes.

Tables:
  leads    — one row per unique WhatsApp phone number
  messages — append-only log of every conversation turn
"""

import os
from datetime import datetime
from typing import List

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    Integer, String, Text, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./krucx_leads.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String, unique=True, nullable=False, index=True)

    # Profile fields — mirrors LeadProfile dataclass
    name = Column(String, nullable=True)
    company_type = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    company_size = Column(String, nullable=True)
    main_problem = Column(Text, nullable=True)
    current_tools = Column(Text, nullable=True)   # JSON-serialized list
    budget = Column(String, nullable=True)
    timeline = Column(String, nullable=True)

    # Conversation state
    qualification_score = Column(Integer, default=0)
    escalation_offered = Column(Boolean, default=False)
    turns_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="lead", order_by="Message.timestamp"
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    role = Column(String, nullable=False)    # "user" or "assistant"
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    lead: Mapped["Lead"] = relationship("Lead", back_populates="messages")


def get_db():
    """FastAPI dependency — yields a session and ensures it is closed after the request."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables if they don't exist. Called once at app startup."""
    Base.metadata.create_all(bind=engine)
