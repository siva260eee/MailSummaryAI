import json
import os
import random
import re
import time
from typing import Dict, List, Tuple, Union

from openai import OpenAI


CATEGORIES = [
    "DevOps",
    "Development/Engineering",
    "AI/ML",
    "Business/Marketing",
    "FinTech",
    "Telecom",
    "Device Financing",
    "Other",
]

DOMAIN_TAGS = [
    "Telecom",
    "Device Financing",
    "AI SaaS",
    "FinTech",
]


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing required env var: OPENAI_API_KEY")
    return OpenAI(api_key=api_key)


def _call_with_retry(fn, attempts: int = 4, base_delay: float = 1.0):
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception:
            if attempt == attempts:
                raise
            sleep_for = base_delay * (2 ** (attempt - 1)) + random.random()
            time.sleep(sleep_for)


def _parse_json_response(content: str) -> Union[Dict[str, object], List[object]]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    match = re.search(r"(\{.*\}|\[.*\])", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return {}
    return {}


def _get_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def summarize_content(item: Dict[str, str], body_text: str) -> str:
    model = _get_model()
    client = _get_client()
    prompt = (
        "Summarize the email in 2-4 sentences as markdown. "
        "Focus on key facts and implications.\n\n"
        f"Subject: {item.get('subject')}\n"
        f"From: {item.get('sender')}\n"
        f"Date: {item.get('date')}\n"
        f"Body:\n{body_text}\n"
    )

    def _call():
        return client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

    resp = _call_with_retry(_call)
    return (resp.choices[0].message.content or "").strip() or "(No summary produced)"


def classify_category(item: Dict[str, str], body_text: str) -> str:
    model = _get_model()
    client = _get_client()
    prompt = (
        "Classify the email into ONE category from this list:\n"
        + ", ".join(CATEGORIES)
        + "\nReturn JSON: {\"category\": \"...\"}.\n\n"
        f"Subject: {item.get('subject')}\n"
        f"From: {item.get('sender')}\n"
        f"Date: {item.get('date')}\n"
        f"Body:\n{body_text}\n"
    )

    def _call():
        return client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

    resp = _call_with_retry(_call)
    raw = resp.choices[0].message.content or ""
    payload = _parse_json_response(raw)
    category = ""
    if isinstance(payload, dict):
        category = str(payload.get("category", "")).strip()
    elif isinstance(payload, str):
        category = payload.strip()
    else:
        category = str(payload).strip()

    if not category:
        category = raw.strip().splitlines()[0] if raw.strip() else ""
    if category not in CATEGORIES:
        category = "Other"
    return category


def tag_topics(item: Dict[str, str], body_text: str) -> List[str]:
    model = _get_model()
    client = _get_client()
    prompt = (
        "Extract 3-6 concise topic tags as a JSON array of strings. "
        "Include a domain tag from this list if relevant: "
        + ", ".join(DOMAIN_TAGS)
        + ".\n\n"
        f"Subject: {item.get('subject')}\n"
        f"From: {item.get('sender')}\n"
        f"Date: {item.get('date')}\n"
        f"Body:\n{body_text}\n"
    )

    def _call():
        return client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

    resp = _call_with_retry(_call)
    raw = resp.choices[0].message.content or ""
    payload = _parse_json_response(raw)
    tags: object
    if isinstance(payload, list):
        tags = payload
    elif isinstance(payload, dict):
        tags = payload.get("tags", payload.get("topic_tags", []))
    else:
        tags = raw
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
    if not isinstance(tags, list):
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
        else:
            tags = []
    return [str(tag).strip() for tag in tags if str(tag).strip()]


def generate_role_angles(
    *,
    item: Dict[str, str],
    summary_md: str,
    category: str,
    topic_tags: List[str],
    role,
) -> Tuple[str, str]:
    model = _get_model()
    client = _get_client()
    objectives = "; ".join(role.objectives) if role.objectives else "Provide actionable insights."
    tags = ", ".join(topic_tags) if topic_tags else "None"
    prompt = (
        "You are generating concise insights for a role-based digest.\n"
        f"Role: {role.name}\n"
        f"Role objectives: {objectives}\n"
        f"Category: {category}\n"
        f"Topic tags: {tags}\n"
        "Write TWO concise sentences as JSON with keys:\n"
        "\"startup_angle\" and \"role_angle\". Keep each to one sentence.\n\n"
        f"Subject: {item.get('subject')}\n"
        f"Summary:\n{summary_md}\n"
    )

    def _call():
        return client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.25,
        )

    resp = _call_with_retry(_call)
    raw = resp.choices[0].message.content or ""
    payload = _parse_json_response(raw)
    startup = ""
    role_angle = ""
    if isinstance(payload, dict):
        startup = str(payload.get("startup_angle", "")).strip()
        role_angle = str(payload.get("role_angle", "")).strip()
    if not startup or not role_angle:
        for line in raw.splitlines():
            lower = line.lower()
            if "startup angle" in lower:
                startup = line.split(":", 1)[-1].strip()
            if "role angle" in lower or f"{role.name.lower()} angle" in lower:
                role_angle = line.split(":", 1)[-1].strip()

    if not startup:
        startup = "Monitor for implications that inform startup strategy."
    if not role_angle:
        role_angle = f"Assess impact on {role.name} priorities and execution."

    return startup, role_angle
