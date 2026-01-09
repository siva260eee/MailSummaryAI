import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_DB_PATH = os.getenv("STORE_PATH", "out/store.db")


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = Path(db_path or DEFAULT_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS content_items (
            id INTEGER PRIMARY KEY,
            content_id TEXT UNIQUE,
            source_type TEXT,
            source_uid TEXT,
            message_id TEXT,
            subject TEXT,
            sender TEXT,
            date TEXT,
            extracted_text TEXT,
            links_json TEXT,
            link_content_json TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS ai_cache (
            content_id TEXT PRIMARY KEY,
            summary_md TEXT,
            category TEXT,
            topic_tags_json TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS role_cache (
            content_id TEXT,
            role_name TEXT,
            startup_angle TEXT,
            role_angle TEXT,
            created_at TEXT,
            PRIMARY KEY(content_id, role_name)
        );

        CREATE TABLE IF NOT EXISTS ingest_state (
            source_type TEXT,
            mailbox TEXT,
            last_uid INTEGER,
            updated_at TEXT,
            PRIMARY KEY(source_type, mailbox)
        );
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_content_message_id "
        "ON content_items(message_id) WHERE message_id IS NOT NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_content_source_uid "
        "ON content_items(source_uid)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_content_created_at "
        "ON content_items(created_at)"
    )
    conn.commit()


def compute_content_id(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def get_last_uid(conn: sqlite3.Connection, source_type: str, mailbox: str) -> int:
    row = conn.execute(
        "SELECT last_uid FROM ingest_state WHERE source_type=? AND mailbox=?",
        (source_type, mailbox),
    ).fetchone()
    return int(row["last_uid"]) if row and row["last_uid"] is not None else 0


def set_last_uid(conn: sqlite3.Connection, source_type: str, mailbox: str, last_uid: int) -> None:
    conn.execute(
        """
        INSERT INTO ingest_state(source_type, mailbox, last_uid, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(source_type, mailbox)
        DO UPDATE SET last_uid=excluded.last_uid, updated_at=excluded.updated_at
        """,
        (source_type, mailbox, last_uid, _utc_now()),
    )
    conn.commit()


def content_exists(
    conn: sqlite3.Connection,
    *,
    source_uid: Optional[str] = None,
    message_id: Optional[str] = None,
    content_id: Optional[str] = None,
) -> bool:
    if message_id:
        row = conn.execute(
            "SELECT 1 FROM content_items WHERE message_id=? LIMIT 1",
            (message_id,),
        ).fetchone()
        if row:
            return True
    if source_uid:
        row = conn.execute(
            "SELECT 1 FROM content_items WHERE source_uid=? LIMIT 1",
            (source_uid,),
        ).fetchone()
        if row:
            return True
    if content_id:
        row = conn.execute(
            "SELECT 1 FROM content_items WHERE content_id=? LIMIT 1",
            (content_id,),
        ).fetchone()
        if row:
            return True
    return False


def insert_content_item(conn: sqlite3.Connection, item: Dict[str, Any]) -> bool:
    try:
        conn.execute(
            """
            INSERT INTO content_items(
                content_id,
                source_type,
                source_uid,
                message_id,
                subject,
                sender,
                date,
                extracted_text,
                links_json,
                link_content_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["content_id"],
                item["source_type"],
                item.get("source_uid"),
                item.get("message_id"),
                item.get("subject"),
                item.get("sender"),
                item.get("date"),
                item.get("extracted_text"),
                item.get("links_json"),
                item.get("link_content_json"),
                item.get("created_at") or _utc_now(),
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def get_content_items(
    conn: sqlite3.Connection,
    *,
    since_hours: Optional[int] = None,
    max_items: Optional[int] = None,
) -> List[Dict[str, Any]]:
    params: List[Any] = []
    where_clause = ""
    if since_hours is not None:
        cutoff = datetime.utcnow() - timedelta(hours=since_hours)
        cutoff_str = cutoff.replace(microsecond=0).isoformat() + "Z"
        where_clause = "WHERE created_at >= ?"
        params.append(cutoff_str)

    limit_clause = ""
    if max_items is not None:
        limit_clause = "LIMIT ?"
        params.append(max_items)

    query = (
        "SELECT * FROM content_items "
        f"{where_clause} "
        "ORDER BY created_at DESC "
        f"{limit_clause}"
    )
    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_content_items_by_ids(
    conn: sqlite3.Connection,
    content_ids: List[str],
) -> List[Dict[str, Any]]:
    if not content_ids:
        return []
    placeholders = ",".join(["?"] * len(content_ids))
    query = (
        f"SELECT * FROM content_items WHERE content_id IN ({placeholders}) "
        "ORDER BY created_at DESC"
    )
    rows = conn.execute(query, content_ids).fetchall()
    return [dict(row) for row in rows]


def get_ai_cache(conn: sqlite3.Connection, content_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM ai_cache WHERE content_id=?",
        (content_id,),
    ).fetchone()
    return dict(row) if row else None


def upsert_ai_cache(
    conn: sqlite3.Connection,
    *,
    content_id: str,
    summary_md: str,
    category: str,
    topic_tags: Iterable[str],
) -> None:
    conn.execute(
        """
        INSERT INTO ai_cache(content_id, summary_md, category, topic_tags_json, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(content_id)
        DO UPDATE SET
            summary_md=excluded.summary_md,
            category=excluded.category,
            topic_tags_json=excluded.topic_tags_json,
            updated_at=excluded.updated_at
        """,
        (
            content_id,
            summary_md,
            category,
            json.dumps(list(topic_tags)),
            _utc_now(),
        ),
    )
    conn.commit()


def get_role_cache(
    conn: sqlite3.Connection,
    content_id: str,
    role_name: str,
) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM role_cache WHERE content_id=? AND role_name=?",
        (content_id, role_name),
    ).fetchone()
    return dict(row) if row else None


def insert_role_cache(
    conn: sqlite3.Connection,
    *,
    content_id: str,
    role_name: str,
    startup_angle: str,
    role_angle: str,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO role_cache(
            content_id,
            role_name,
            startup_angle,
            role_angle,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (content_id, role_name, startup_angle, role_angle, _utc_now()),
    )
    conn.commit()
