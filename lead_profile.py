"""
Lead profile: structured memory for a single WhatsApp conversation.

Why this exists (instead of just stuffing chat history into the prompt):
The spec says "never ask the same question twice" and "always remember context."
That's a behavioral promise an LLM can break under long context or paraphrased
re-asks. Making the known fields an explicit, typed object means the *code*
enforces the promise — we can literally check `if profile.industry is None`
before deciding whether to ask about industry.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List
import json


@dataclass
class LeadProfile:
    # Internal identifiers — excluded from prompt injection
    phone_number: Optional[str] = None
    db_id: Optional[int] = None

    name: Optional[str] = None
    company_type: Optional[str] = None      # e.g. "agency", "manufacturer"
    industry: Optional[str] = None          # one of the known industries, or "other"
    company_size: Optional[str] = None      # free text, e.g. "~15 employees"
    main_problem: Optional[str] = None
    current_tools: List[str] = field(default_factory=list)
    budget: Optional[str] = None
    timeline: Optional[str] = None

    # Internal tracking, not part of the spec's field list but needed
    # to drive conversation flow without re-asking or looping forever.
    turns_count: int = 0
    escalation_offered: bool = False

    _INTERNAL_FIELDS = frozenset({"turns_count", "escalation_offered", "phone_number", "db_id"})

    def known_fields(self) -> dict:
        """Fields that are already filled — the bot must never re-ask these."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v and k not in self._INTERNAL_FIELDS}

    def missing_fields(self) -> List[str]:
        core_fields = ["name", "industry", "main_problem"]
        return [f for f in core_fields if not getattr(self, f)]

    def qualification_score(self) -> int:
        """
        Simple, explainable scoring — not vibes-based.
        This gives the conversation engine an actual exit condition for
        "when do we offer escalation" instead of leaving it ambiguous.
        """
        score = 0
        if self.industry:
            score += 1
        if self.main_problem:
            score += 1
        if self.company_size or self.budget:
            score += 1
        if self.name:
            score += 1
        return score  # max 4

    def is_qualified(self) -> bool:
        # Industry + problem identified, plus one more signal (size/budget/name)
        return self.industry is not None and self.main_problem is not None and self.qualification_score() >= 3

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    def merge_updates(self, updates: dict):
        """Apply non-empty extracted fields without overwriting existing data with nulls."""
        for k, v in updates.items():
            if v is None or v == "" or v == []:
                continue
            if k == "current_tools" and isinstance(v, list):
                # merge lists, dedupe
                existing = set(self.current_tools)
                existing.update(v)
                self.current_tools = list(existing)
            elif hasattr(self, k):
                setattr(self, k, v)
