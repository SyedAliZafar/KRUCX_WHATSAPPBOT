"""
Local CLI test harness.

Simulates one WhatsApp conversation in the terminal. No DB, no webhook —
just the conversation engine + in-memory state, so we can validate the
bot's behavior (tone, qualification, memory, escalation) before wiring
up any real infrastructure.

Run from the project root:
    export DEEPSEEK_API_KEY=sk-...
    uv run python scripts/chat_cli.py

Commands during chat:
    /profile   - print the current lead profile JSON
    /reset     - start a new conversation
    /quit      - exit
"""

import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path so `app.*` imports resolve
# regardless of which directory the script is invoked from.
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.lead_profile import LeadProfile
from app import conversation_engine as engine


def print_bot(message: str):
    print(f"\033[96mKrucx Bot:\033[0m {message}\n")


def print_system(message: str):
    print(f"\033[90m[{message}]\033[0m")


def run():
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("ERROR: set DEEPSEEK_API_KEY environment variable first.")
        print('  export DEEPSEEK_API_KEY="sk-..."')
        sys.exit(1)

    profile = LeadProfile()
    history = []  # list of {"role": ..., "content": ...}

    print_system("New conversation started. Type /profile, /reset, or /quit anytime.")
    # Opening message, as if the prospect just messaged the WhatsApp number
    opening = "Hi! 👋 Thanks for reaching out to Krucx. What's your business, and what's the main thing you're hoping to improve?"
    print_bot(opening)
    history.append({"role": "assistant", "content": opening})

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() == "/quit":
            break
        if user_input.lower() == "/reset":
            profile = LeadProfile()
            history = []
            print_system("Conversation reset.")
            print_bot(opening)
            history.append({"role": "assistant", "content": opening})
            continue
        if user_input.lower() == "/profile":
            print_system("Current lead profile:")
            print(profile.to_json())
            continue

        # 1. Extract structured updates from this message and merge into profile
        updates = engine.extract_profile_updates(user_input)
        profile.merge_updates(updates)
        profile.turns_count += 1

        # 2. Generate the reply using current state
        history.append({"role": "user", "content": user_input})
        reply = engine.generate_reply(profile, history[:-1], user_input)
        history.append({"role": "assistant", "content": reply})

        if profile.is_qualified() and not profile.escalation_offered:
            print_system(f"qualification score {profile.qualification_score()}/4 — bot may escalate soon")

        print_bot(reply)

        if engine.detect_escalation_offered(reply):
            profile.escalation_offered = True


if __name__ == "__main__":
    run()
