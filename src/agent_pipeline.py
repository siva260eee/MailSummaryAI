import os
from typing import Dict, List, Tuple

from openai import OpenAI


CATEGORIES = [
    "Telecom",
    "Device Financing",
    "AI SaaS",
    "FinTech",
    "Other",
]


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing required env var: OPENAI_API_KEY")
    return OpenAI(api_key=api_key)


def summarize_and_classify(parsed: Dict[str, str]) -> Tuple[str, str]:
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = _get_client()

    prompt = (
        "Summarize the email in 2-4 sentences and classify it into one of: "
        + ", ".join(CATEGORIES)
        + ".\n"
        "Return JSON with keys summary and category.\n\n"
        f"Subject: {parsed['subject']}\n"
        f"From: {parsed['from']}\n"
        f"Date: {parsed['date']}\n"
        f"Body:\n{parsed['body']}\n"
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    content = resp.choices[0].message.content or ""
    summary, category = _parse_summary_category(content)
    return summary, category


def _parse_summary_category(content: str) -> Tuple[str, str]:
    try:
        import json

        data = json.loads(content)
        summary = str(data.get("summary", "")).strip()
        category = str(data.get("category", "Other")).strip()
    except Exception:
        summary = content.strip()
        category = "Other"

    if category not in CATEGORIES:
        category = "Other"
    if not summary:
        summary = "(No summary produced)"
    return summary, category


def synthesize_digest(items: List[Dict[str, str]]) -> str:
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = _get_client()

    lines = []
    for idx, item in enumerate(items, start=1):
        lines.append(
            f"{idx}. [{item['category']}] {item['subject']} - {item['summary']}"
        )

    prompt = (
        "Create a markdown digest grouped by category with clear headings. "
        "Under each category, list the relevant items with bullet points. "
        "After each item, add a short 'Startup angle:' phrase. "
        "Keep it concise and professional.\n\n"
        "Items:\n" + "\n".join(lines)
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    return resp.choices[0].message.content or ""
