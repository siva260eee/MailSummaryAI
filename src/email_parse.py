import email
from email.message import Message
from typing import Dict, Optional

from bs4 import BeautifulSoup


PLAIN_TYPES = {"text/plain"}
HTML_TYPES = {"text/html"}


def _decode_part(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line])


def _extract_body(msg: Message) -> str:
    text_parts = []
    html_parts = []

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            ctype = part.get_content_type()
            if ctype in PLAIN_TYPES:
                text_parts.append(_decode_part(part))
            elif ctype in HTML_TYPES:
                html_parts.append(_decode_part(part))
    else:
        ctype = msg.get_content_type()
        if ctype in PLAIN_TYPES:
            text_parts.append(_decode_part(msg))
        elif ctype in HTML_TYPES:
            html_parts.append(_decode_part(msg))

    if text_parts:
        return "\n".join(text_parts)
    if html_parts:
        return _html_to_text("\n".join(html_parts))
    return ""


def parse_email(raw: bytes, max_body_chars: int = 4000) -> Optional[Dict[str, str]]:
    msg = email.message_from_bytes(raw)
    body = _extract_body(msg)
    if not body:
        return None

    if len(body) > max_body_chars:
        body = body[: max_body_chars - 3] + "..."

    return {
        "subject": msg.get("Subject", "(no subject)"),
        "from": msg.get("From", ""),
        "date": msg.get("Date", ""),
        "body": body,
        "list_unsubscribe": msg.get("List-Unsubscribe", ""),
    }


def is_newsletter(parsed: Dict[str, str]) -> bool:
    subject = parsed.get("subject", "").lower()
    list_unsub = parsed.get("list_unsubscribe", "")
    keywords = ["newsletter", "update", "digest", "roundup"]

    if list_unsub:
        return True
    return any(word in subject for word in keywords)
