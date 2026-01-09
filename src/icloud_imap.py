import email
import imaplib
import os
from typing import List, Optional


def _get_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _extract_raw_message(msg_data) -> Optional[bytes]:
    raw = None
    for item in msg_data:
        if isinstance(item, tuple):
            for sub_item in item:
                if isinstance(sub_item, bytes) and len(sub_item) > 10:
                    if raw is None or len(sub_item) > len(raw):
                        raw = sub_item
    return raw


class ImapSession:
    def __init__(self, mailbox: str = "INBOX", mark_seen: bool = False) -> None:
        self.mailbox = mailbox
        self.mark_seen = mark_seen
        self.client: Optional[imaplib.IMAP4_SSL] = None

    def __enter__(self) -> "ImapSession":
        user = _get_env("IMAP_USER")
        password = _get_env("IMAP_PASSWORD")
        self.client = imaplib.IMAP4_SSL("imap.mail.me.com", 993)
        self.client.login(user, password)
        self.client.select(self.mailbox, readonly=not self.mark_seen)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self.client:
            return
        try:
            self.client.close()
        except Exception:
            pass
        self.client.logout()

    def uid_search(self, query: str) -> List[int]:
        if not self.client:
            raise RuntimeError("IMAP session not initialized")
        status, data = self.client.uid("SEARCH", None, query)
        if status != "OK" or not data or not data[0]:
            return []
        return [int(uid) for uid in data[0].split()]

    def fetch_headers(self, uid: int) -> Optional[bytes]:
        if not self.client:
            raise RuntimeError("IMAP session not initialized")
        fields = "MESSAGE-ID SUBJECT FROM DATE LIST-ID LIST-UNSUBSCRIBE"
        status, msg_data = self.client.uid(
            "FETCH",
            str(uid),
            f"(BODY.PEEK[HEADER.FIELDS ({fields})])",
        )
        if status != "OK" or not msg_data:
            return None
        return _extract_raw_message(msg_data)

    def fetch_body(self, uid: int) -> Optional[bytes]:
        if not self.client:
            raise RuntimeError("IMAP session not initialized")
        status, msg_data = self.client.uid("FETCH", str(uid), "(BODY.PEEK[])")
        if status != "OK" or not msg_data:
            return None
        return _extract_raw_message(msg_data)

    def mark_seen(self, uid: int) -> None:
        if not self.client:
            raise RuntimeError("IMAP session not initialized")
        self.client.uid("STORE", str(uid), "+FLAGS", "\\Seen")

    @staticmethod
    def extract_message_id(headers_raw: bytes) -> Optional[str]:
        if not headers_raw:
            return None
        msg = email.message_from_bytes(headers_raw)
        message_id = msg.get("Message-ID")
        return message_id.strip() if message_id else None


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
            status, msg_data = client.fetch(msg_id, "(BODY.PEEK[])")
            if status != "OK" or not msg_data:
                continue
            raw = _extract_raw_message(msg_data)
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
