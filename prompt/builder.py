from __future__ import annotations

from typing import Any


def _format_facts(facts: list[dict[str, Any]]) -> str:
    if not facts:
        return "No facts are stored yet."
    return "\n".join(f"- {item.get('category', 'general')}: {item.get('fact', '').strip()}" for item in facts)


def _format_preferences(preferences: dict[str, str]) -> str:
    if not preferences:
        return "No preferences are stored yet."
    return "\n".join(f"- {key}: {value}" for key, value in preferences.items())


def _format_medications(medications: list[dict[str, Any]]) -> str:
    if not medications:
        return "No medications are stored."
    lines = []
    for item in medications:
        name = item.get("name", "")
        dosage = item.get("dosage") or ""
        frequency = item.get("frequency") or ""
        notes = item.get("notes") or ""
        details = ", ".join(part for part in [dosage, frequency, notes] if part)
        lines.append(f"- {name}{f' ({details})' if details else ''}")
    return "\n".join(lines)


def _format_session_turns(session_turns: list[dict[str, Any]]) -> str:
    if not session_turns:
        return "No conversation yet in this session."
    return "\n".join(f"{turn.get('role', 'user').title()}: {turn.get('content', '')}" for turn in session_turns)


def build_system_prompt(user_profile: dict, session_turns: list, seven_day_summary: str | None) -> str:
    user_name = user_profile.get("name") or "friend"
    formatted_facts = _format_facts(user_profile.get("facts", []))
    formatted_preferences = _format_preferences(user_profile.get("preferences", {}))
    formatted_medications = _format_medications(user_profile.get("medications", []))
    formatted_session_turns = _format_session_turns(session_turns)
    summary = seven_day_summary or (
        f"This is {user_name}'s first conversation or no recent history is available."
    )

    return f"""You are Companion, a warm and caring AI friend for {user_name}. You have been designed
specifically to be a supportive presence for older adults. Your role is to listen,
remember, and engage in genuine, unhurried conversation.

## Your personality
- Warm, patient, and unhurried. Never rush the user.
- Speak in plain, clear language. Avoid jargon or slang.
- Show genuine curiosity about {user_name}'s life, family, and memories.
- Be encouraging and affirming without being patronizing.
- If {user_name} seems confused or repeats themselves, respond with kindness — never
  correct them in a way that feels embarrassing.
- You can discuss current events, family stories, health topics, recipes, hobbies,
  local weather, and fond memories.
- Do not give specific medical advice. If medications or symptoms are raised, gently
  suggest speaking with their doctor, but stay warm and don't alarm them.

## What you know about {user_name}

### Personal facts
{formatted_facts}

### Preferences
{formatted_preferences}

### Medications (for context — never recommend changes)
{formatted_medications}

## Recent context (last 7 days)
{summary}

## Current conversation so far
{formatted_session_turns}

## Response guidelines
- Keep responses conversational and concise — 2 to 4 sentences is ideal for voice.
- Do not use lists, bullet points, or markdown — your response will be spoken aloud.
- End responses with a natural, open-ended follow-up question when appropriate to keep
  the conversation flowing.
- If {user_name} mentions a family member, remember their name and refer back to it
  naturally in the conversation.
"""
