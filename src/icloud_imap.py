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
        print(f"Found {len(ids)} message(s) matching search criteria: {search_query}")
        
        if not ids:
            return []

        messages: List[bytes] = []
        for msg_id in ids:
            status, msg_data = client.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data:
                print(f"  Failed to fetch message {msg_id.decode()}: status={status}")
                continue
            # msg_data structure varies, could be:
            # [(b'1 (RFC822 {size}', email_bytes), b')'] or [email_bytes] or [(b'FLAGS...', email_bytes)]
            raw = None
            if isinstance(msg_data, list) and len(msg_data) > 0:
                # Check if first item is already bytes (direct email content)
                if isinstance(msg_data[0], bytes):
                    raw = msg_data[0]
                # Check if it's a tuple with email bytes as second element
                elif isinstance(msg_data[0], tuple) and len(msg_data[0]) >= 2:
                    if isinstance(msg_data[0][1], bytes):
                        raw = msg_data[0][1]
            
            if raw:
                messages.append(raw)
            else:
                print(f"  Could not extract email bytes from message {msg_id.decode()}")

            if mark_seen:
                client.store(msg_id, "+FLAGS", "\\Seen")

        print(f"Successfully fetched {len(messages)} message(s)\n")

        return messages
    finally:
        try:
            client.close()
        except Exception:
            pass
        client.logout()
