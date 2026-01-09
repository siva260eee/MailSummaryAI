import os
from datetime import datetime

from dotenv import load_dotenv

from icloud_imap import fetch_messages
from email_parse import parse_email, is_newsletter
from agent_pipeline import summarize_and_classify, synthesize_digest
from digest_writer import write_digest
from link_fetcher import enrich_email_with_links


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y"}


def main() -> None:
    load_dotenv()

    search_query = os.getenv("IMAP_SEARCH", "UNSEEN")
    mark_seen = _env_bool("MARK_SEEN", False)
    newsletter_only = _env_bool("NEWSLETTER_ONLY", False)
    max_body_chars = int(os.getenv("MAX_BODY_CHARS", "4000"))
    fetch_links = _env_bool("FETCH_LINKS", True)
    max_links = int(os.getenv("MAX_LINKS_TO_FETCH", "10"))
    interactive_links = _env_bool("INTERACTIVE_LINK_FETCH", True)

    messages = fetch_messages(search_query=search_query, mark_seen=mark_seen)
    if not messages:
        print("No messages to process after search.")
        return

    print(f"Processing {len(messages)} message(s)...")
    items = []
    skipped = 0
    for raw in messages:
        parsed = parse_email(raw, max_body_chars=max_body_chars)
        if not parsed:
            skipped += 1
            continue
        
        if newsletter_only and not is_newsletter(parsed):
            skipped += 1
            continue
        
        # Enrich email with link content if enabled
        if fetch_links:
            parsed = enrich_email_with_links(parsed, max_links=max_links, interactive=interactive_links)

        summary, category = summarize_and_classify(parsed)
        items.append({
            "subject": parsed["subject"],
            "from": parsed["from"],
            "date": parsed["date"],
            "summary": summary,
            "category": category,
        })

    print(f"\nProcessed: {len(items)} items, Skipped: {skipped}")
    
    if not items:
        print("No items to digest after filtering.")
        return

    digest_md = synthesize_digest(items)
    out_path = write_digest(digest_md, date=datetime.utcnow().date())
    print(f"Wrote digest to {out_path}")


if __name__ == "__main__":
    main()
