import imaplib
import os
from typing import List


def _get_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def fetch_messages(search_query: str = "UNSEEN", mark_seen: bool = False) -> List[bytes]:
    user = _get_env("IMAP_USER")
    password = _get_env("IMAP_PASSWORD")

    client = imaplib.IMAP4_SSL("imap.mail.me.com", 993)
    try:
        client.login(user, password)
        client.select("INBOX", readonly=not mark_seen)

        status, data = client.search(None, search_query)
        if status != "OK" or not data or not data[0]:
            return []

        ids = data[0].split()
        if not ids:
            return []

        messages: List[bytes] = []
        for msg_id in ids:
            status, msg_data = client.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data:
                continue
            # msg_data is a list of tuples: [(b'1 (RFC822 {size}', email_bytes), b')']
            # We need to find the bytes object in the response
            raw = None
            for item in msg_data:
                if isinstance(item, tuple) and len(item) > 1:
                    if isinstance(item[1], bytes):
                        raw = item[1]
                        break
            if raw:
                messages.append(raw)

            if mark_seen:
                client.store(msg_id, "+FLAGS", "\\Seen")

        return messages
    finally:
        try:
            client.close()
        except Exception:
            pass
        client.logout()
