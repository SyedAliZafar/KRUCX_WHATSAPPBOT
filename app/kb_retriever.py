"""
KB retriever: deterministic keyword lookup over the structured knowledge base.

Why not embeddings/RAG yet: the KB is a few hundred lines of JSON. A vector
store adds infra (chunking, embedding model, similarity search) for no real
gain at this size, and makes debugging "why did it say that" harder. This
returns exact, traceable matches. Swap for pgvector/Chroma later if the KB
grows or becomes unstructured (e.g. ingesting raw PDFs/contracts).
"""

import json
from pathlib import Path
from typing import Optional

KB_PATH = Path(__file__).parent.parent / "data" / "knowledge_base.json"

with open(KB_PATH, "r") as f:
    KB = json.load(f)

KNOWN_INDUSTRIES = list(KB["industries"].keys())


def get_industry_info(industry: Optional[str]) -> Optional[dict]:
    """Return problems/solutions for a known industry, or None if unrecognized."""
    if not industry:
        return None
    key = industry.lower().strip()
    # light normalization for common synonyms
    synonyms = {
        "ecommerce": ["e-commerce", "online store", "online retail", "shop", "store"],
        "logistics": ["shipping", "freight", "transport", "trucking", "supply chain"],
        "healthcare": ["medical", "clinic", "dental", "hospital"],
        "restaurants": ["restaurant", "cafe", "food service", "dining"],
        "manufacturing": ["factory", "production", "industrial"],
    }
    if key in KB["industries"]:
        return KB["industries"][key]
    for canon, alts in synonyms.items():
        if key in alts or any(alt in key for alt in alts):
            return KB["industries"].get(canon)
    return None


def get_company_info() -> dict:
    return KB["company"]


def get_services() -> dict:
    return KB["services"]


def get_team() -> list:
    return KB["team"]


def get_contact() -> dict:
    return KB["contact"]


def get_links() -> dict:
    return KB["links"]


def get_faq() -> dict:
    return KB.get("faq", {})


def get_pricing() -> dict:
    return KB.get("pricing_ranges", {})


def get_portfolio_highlights() -> dict:
    return KB.get("portfolio_highlights", {})


def get_process() -> dict:
    return KB.get("process", {})


def kb_summary_for_prompt() -> str:
    """Compact text summary injected into the system prompt every turn."""
    company = KB["company"]
    services_flat = []
    for category, items in KB["services"].items():
        services_flat.append(f"- {category.replace('_', ' ').title()}: {', '.join(items)}")

    industries_flat = []
    for name, data in KB["industries"].items():
        problems = data.get("common_problems", [])
        solutions = data.get("solutions") or data.get("automation_opportunities", [])
        industries_flat.append(
            f"- {name.title()}: common problems = {', '.join(problems)}; "
            f"solutions = {', '.join(solutions)}"
        )

    pricing = KB.get("pricing_ranges", {})
    pricing_flat = []
    for category, items in pricing.items():
        if category == "note":
            continue
        for service, range_str in items.items():
            pricing_flat.append(f"- {service.replace('_', ' ').title()}: {range_str}")

    faq_flat = []
    for q, a in KB.get("faq", {}).items():
        faq_flat.append(f"Q: {q.replace('_', ' ')}\nA: {a}")

    process_steps = KB.get("process", {}).get("steps", [])
    timelines = KB.get("process", {}).get("typical_timelines", {})
    timelines_flat = [f"- {k.replace('_', ' ').title()}: {v}" for k, v in timelines.items()]

    return (
        f"COMPANY: {company['name']}, founded {company['founded']}, "
        f"{company['clients_served']} clients served. {company['positioning']} "
        f"Based in {company.get('locations', 'Germany & UK')}.\n\n"
        f"SERVICES:\n" + "\n".join(services_flat) + "\n\n"
        f"INDUSTRY EXPERTISE:\n" + "\n".join(industries_flat) + "\n\n"
        f"PRICING (indicative ranges — always recommend free quote for exact pricing):\n"
        + "\n".join(pricing_flat) + "\n\n"
        f"TYPICAL TIMELINES:\n" + "\n".join(timelines_flat) + "\n\n"
        f"FAQ (use these answers directly when prospects ask these questions):\n"
        + "\n\n".join(faq_flat) + "\n\n"
        f"CONTACT: {KB['contact']['email']} | DE {KB['contact']['phone_germany']} | "
        f"UK {KB['contact']['phone_uk']}\n"
        f"LINKS: Start a project: {KB['links']['start_a_project']} | "
        f"Free quote: {KB['links']['free_quote']} | Portfolio: {KB['links']['portfolio']}"
    )
