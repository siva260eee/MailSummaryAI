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
            # Use BODY.PEEK[] instead of RFC822 for better iCloud IMAP compatibility
            status, msg_data = client.fetch(msg_id, "(BODY.PEEK[])")
            if status != "OK" or not msg_data:
                print(f"  Failed to fetch message {msg_id.decode()}: status={status}")
                continue
            
            # IMAP BODY[] fetch returns: [(b'1 (BODY[] {size}', email_bytes), b')']
            # We need to find the actual email bytes in the tuple
            raw = None
            for item in msg_data:
                if isinstance(item, tuple):
                    # Look for the largest bytes object in the tuple (that's the email)
                    for sub_item in item:
                        if isinstance(sub_item, bytes) and len(sub_item) > 100:
                            if raw is None or len(sub_item) > len(raw):
                                raw = sub_item
            
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
