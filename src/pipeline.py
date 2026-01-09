import json
import os
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from .agent_pipeline import (
    CATEGORIES,
    DOMAIN_TAGS,
    classify_category,
    generate_role_angles,
    summarize_content,
    tag_topics,
)
from .email_parse import is_newsletter, parse_email
from .icloud_imap import ImapSession
from .link_fetcher import extract_links, fetch_links_interactive
from .roles import Role
from .store import (
    compute_content_id,
    content_exists,
    get_ai_cache,
    get_content_items,
    get_content_items_by_ids,
    get_connection,
    get_last_uid,
    get_role_cache,
    init_db,
    insert_content_item,
    insert_role_cache,
    set_last_uid,
    upsert_ai_cache,
)


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y"}


def _safe_int(value: Optional[str], default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _build_prompt_text(item: Dict[str, str], max_body_chars: int) -> str:
    body = item.get("extracted_text") or ""
    body = body.strip()
    if len(body) > max_body_chars:
        body = body[: max_body_chars - 3] + "..."

    link_content = {}
    if item.get("link_content_json"):
        try:
            link_content = json.loads(item["link_content_json"])
        except json.JSONDecodeError:
            link_content = {}

    if link_content:
        appended: List[str] = []
        for url, content in link_content.items():
            if not content:
                continue
            trimmed = content[:1000] + ("..." if len(content) > 1000 else "")
            appended.append(f"--- Content from {url} ---\n{trimmed}")
        if appended:
            body = body + "\n\n" + "\n\n".join(appended)

    return body


def _domain_tag_from_topics(tags: Iterable[str]) -> Optional[str]:
    domain_map = {tag.lower(): tag for tag in DOMAIN_TAGS}
    for tag in tags:
        if str(tag).lower() in domain_map:
            return domain_map[str(tag).lower()]
    return None


def ingest_emails() -> Tuple[int, int, List[str]]:
    conn = get_connection()
    init_db(conn)

    search_query = os.getenv("IMAP_SEARCH", "UNSEEN")
    mark_seen = _env_bool("MARK_SEEN", False)
    newsletter_only = _env_bool("NEWSLETTER_ONLY", False)
    max_body_chars = _safe_int(os.getenv("MAX_BODY_CHARS"), 4000)
    fetch_links = _env_bool("FETCH_LINKS", True)
    max_links = _safe_int(os.getenv("MAX_LINKS_TO_FETCH"), 10)
    interactive_links = _env_bool("INTERACTIVE_LINK_FETCH", True)

    last_uid = get_last_uid(conn, "email", "INBOX")
    new_count = 0
    skipped = 0
    inspected_max_uid = last_uid
    new_content_ids: List[str] = []

    with ImapSession(mark_seen=mark_seen) as session:
        uid_query = f"UID {last_uid + 1}:*"
        if search_query:
            uid_query = f"{uid_query} {search_query}"
        uids = session.uid_search(uid_query)
        if not uids:
            return 0, 0, []

        for uid in uids:
            inspected_max_uid = max(inspected_max_uid, uid)
            headers_raw = session.fetch_headers(uid)
            if not headers_raw:
                continue
            message_id = session.extract_message_id(headers_raw)
            source_uid = f"INBOX:{uid}"

            if message_id and content_exists(conn, message_id=message_id):
                skipped += 1
                continue
            if content_exists(conn, source_uid=source_uid):
                skipped += 1
                continue

            raw = session.fetch_body(uid)
            if not raw:
                continue

            parsed = parse_email(raw, max_body_chars=max_body_chars)
            if not parsed:
                skipped += 1
                continue

            if newsletter_only and not is_newsletter(parsed):
                skipped += 1
                continue

            full_body = parsed.get("full_body", parsed.get("body", ""))
            links = extract_links(full_body)
            link_content = {}
            if fetch_links and links:
                link_content = fetch_links_interactive(
                    links,
                    subject=parsed.get("subject", ""),
                    max_links=max_links,
                    interactive=interactive_links,
                )

            payload = {
                "source_type": "email",
                "source_uid": source_uid,
                "message_id": message_id,
                "subject": parsed.get("subject"),
                "sender": parsed.get("from"),
                "date": parsed.get("date"),
                "extracted_text": full_body,
            }
            content_id = compute_content_id(
                {
                    "source_type": payload["source_type"],
                    "subject": payload["subject"],
                    "sender": payload["sender"],
                    "date": payload["date"],
                    "extracted_text": payload["extracted_text"],
                }
            )
            if content_exists(conn, content_id=content_id):
                skipped += 1
                continue

            stored = insert_content_item(
                conn,
                {
                    **payload,
                    "content_id": content_id,
                    "links_json": json.dumps(links),
                    "link_content_json": json.dumps(link_content),
                    "created_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                },
            )
            if stored:
                new_count += 1
                new_content_ids.append(content_id)

            if mark_seen:
                session.mark_seen(uid)

        if inspected_max_uid > last_uid:
            set_last_uid(conn, "email", "INBOX", inspected_max_uid)

    return new_count, skipped, new_content_ids


def ensure_ai_cache_for_item(item: Dict[str, str]) -> Dict[str, str]:
    conn = get_connection()
    init_db(conn)

    cached = get_ai_cache(conn, item["content_id"])
    summary = cached.get("summary_md") if cached else None
    category = cached.get("category") if cached else None
    topic_tags: List[str] = []
    topic_tags_cached = False
    if cached is not None:
        if cached.get("topic_tags_json") is not None:
            topic_tags_cached = True
            try:
                topic_tags = json.loads(cached["topic_tags_json"])
            except json.JSONDecodeError:
                topic_tags = []
                topic_tags_cached = False

    prompt_text = _build_prompt_text(item, _safe_int(os.getenv("MAX_BODY_CHARS"), 4000))

    if summary is None or summary.strip() == "":
        summary = summarize_content(item, prompt_text)
    if category is None or category.strip() == "":
        category = classify_category(item, prompt_text)
    if not topic_tags_cached:
        topic_tags = tag_topics(item, prompt_text)

    upsert_ai_cache(
        conn,
        content_id=item["content_id"],
        summary_md=summary,
        category=category,
        topic_tags=topic_tags,
    )

    return {
        "summary_md": summary,
        "category": category,
        "topic_tags": topic_tags,
    }


def ensure_role_cache_for_item(
    item: Dict[str, str],
    role: Role,
    ai_cache: Dict[str, str],
) -> Dict[str, str]:
    conn = get_connection()
    init_db(conn)

    cached = get_role_cache(conn, item["content_id"], role.name)
    if cached:
        return {
            "startup_angle": cached.get("startup_angle", ""),
            "role_angle": cached.get("role_angle", ""),
        }

    startup_angle, role_angle = generate_role_angles(
        item=item,
        summary_md=ai_cache["summary_md"],
        category=ai_cache["category"],
        topic_tags=ai_cache["topic_tags"],
        role=role,
    )
    insert_role_cache(
        conn,
        content_id=item["content_id"],
        role_name=role.name,
        startup_angle=startup_angle,
        role_angle=role_angle,
    )
    return {
        "startup_angle": startup_angle,
        "role_angle": role_angle,
    }


def build_digest_items(
    role: Role,
    *,
    content_ids: Optional[List[str]] = None,
    since_hours: Optional[int] = None,
    max_items: Optional[int] = None,
) -> List[Dict[str, str]]:
    conn = get_connection()
    init_db(conn)

    if content_ids:
        items = get_content_items_by_ids(conn, content_ids)
    else:
        items = get_content_items(conn, since_hours=since_hours, max_items=max_items)
    digest_items: List[Dict[str, str]] = []

    for item in items:
        ai_cache = ensure_ai_cache_for_item(item)
        role_cache = ensure_role_cache_for_item(item, role, ai_cache)

        topic_tags = ai_cache.get("topic_tags") or []
        domain_tag = _domain_tag_from_topics(topic_tags)

        digest_items.append(
            {
                "content_id": item["content_id"],
                "subject": item.get("subject") or "(no subject)",
                "category": ai_cache["category"],
                "summary_md": ai_cache["summary_md"],
                "topic_tags": topic_tags,
                "domain_tag": domain_tag,
                "startup_angle": role_cache["startup_angle"],
                "role_angle": role_cache["role_angle"],
            }
        )

    filtered: List[Dict[str, str]] = []
    focus_topics = [topic.lower() for topic in role.focus_topics]
    for item in digest_items:
        if role.focus_categories and item["category"] not in role.focus_categories:
            continue
        if focus_topics:
            item_tags = [str(tag).lower() for tag in item.get("topic_tags", [])]
            if not any(tag in focus_topics for tag in item_tags):
                continue
        filtered.append(item)

    return filtered


def format_digest_markdown(items: List[Dict[str, str]], role_name: str) -> str:
    grouped: Dict[str, List[Dict[str, str]]] = {cat: [] for cat in CATEGORIES}
    for item in items:
        grouped.setdefault(item["category"], []).append(item)

    lines: List[str] = ["# Digest of Recent Insights", ""]

    for category in CATEGORIES:
        if not grouped.get(category):
            continue
        lines.append(f"## {category}")
        for item in grouped[category]:
            title = item.get("subject") or "(no subject)"
            domain_tag = item.get("domain_tag")
            if domain_tag:
                title = f"{title} (Domain: {domain_tag})"
            lines.append(f"- **{title}**")
            lines.append(f"  - **Startup angle:** {item.get('startup_angle', '')}")
            lines.append(f"  - **{role_name} angle:** {item.get('role_angle', '')}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"
