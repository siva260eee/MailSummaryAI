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
    if not html or not html.strip():
        return ""
    
    soup = BeautifulSoup(html, "lxml")
    
    # Convert links to text with URLs inline (not references)
    for a_tag in soup.find_all('a', href=True):
        href = a_tag.get('href', '')
        text = a_tag.get_text(strip=True)
        # Replace the link with text and URL inline
        if href and href.startswith(('http://', 'https://')):
            # Put URL inline to avoid losing it at the bottom
            a_tag.replace_with(f"{text} {href} ")
    
    # Remove script, style, and other non-content tags
    for tag in soup(["script", "style", "noscript", "head", "meta", "link"]):
        tag.decompose()
    
    # Get text with better separator handling
    text = soup.get_text(separator="\n", strip=True)
    
    # Clean up extra whitespace while preserving structure
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if line:  # Only keep non-empty lines
            lines.append(line)
    
    result = "\n".join(lines)
    return result if result else ""


def _extract_body(msg: Message) -> str:
    text_parts = []
    html_parts = []

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            ctype = part.get_content_type()
            if ctype in PLAIN_TYPES:
                decoded = _decode_part(part)
                if decoded.strip():
                    text_parts.append(decoded)
            elif ctype in HTML_TYPES:
                decoded = _decode_part(part)
                if decoded.strip():
                    html_parts.append(decoded)
    else:
        ctype = msg.get_content_type()
        if ctype in PLAIN_TYPES:
            decoded = _decode_part(msg)
            if decoded.strip():
                text_parts.append(decoded)
        elif ctype in HTML_TYPES:
            decoded = _decode_part(msg)
            if decoded.strip():
                html_parts.append(decoded)

    if text_parts:
        body = "\n".join(text_parts)
        return body.strip()
    if html_parts:
        html_text = "\n".join(html_parts)
        body = _html_to_text(html_text)
        return body.strip()
    return ""


def parse_email(raw: bytes, max_body_chars: int = 4000) -> Optional[Dict[str, str]]:
    msg = email.message_from_bytes(raw)
    
    # Properly decode the subject with email header decoding
    subject_header = msg.get("Subject", "(no subject)")
    if subject_header != "(no subject)":
        # Decode email header (handles encoded-words like =?UTF-8?Q?...?=)
        decoded_parts = email.header.decode_header(subject_header)
        subject_parts = []
        for content, charset in decoded_parts:
            if isinstance(content, bytes):
                try:
                    subject_parts.append(content.decode(charset or 'utf-8', errors='replace'))
                except:
                    subject_parts.append(content.decode('utf-8', errors='replace'))
            else:
                subject_parts.append(content)
        subject = ''.join(subject_parts)
    else:
        subject = "(no subject)"
    
    body = _extract_body(msg)
    
    # Debug: log parsing issues
    if not body:
        print(f"  Warning: No body extracted for email: {subject[:50]}...")
        # Return the email info anyway, even without body
        return {
            "subject": subject,
            "from": msg.get("From", ""),
            "date": msg.get("Date", ""),
            "body": "[No body content extracted]",
            "list_unsubscribe": msg.get("List-Unsubscribe", ""),
        }

    if len(body) > max_body_chars:
        body = body[: max_body_chars - 3] + "..."

    return {
        "subject": subject,
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
