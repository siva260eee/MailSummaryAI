from datetime import datetime

from dotenv import load_dotenv

from .digest_writer import write_digest
from .pipeline import build_digest_items, format_digest_markdown, ingest_emails
from .roles import get_role, load_roles


def main() -> None:
    load_dotenv()

    new_count, skipped, new_content_ids = ingest_emails()
    print(f"Ingested: {new_count}, Skipped: {skipped}")

    if not new_content_ids:
        print("No new items ingested. Skipping digest build.")
        return

    roles = load_roles()
    role = get_role("CTO", roles)
    if not role:
        raise RuntimeError("Default role 'CTO' is missing from roles.yaml")

    items = build_digest_items(role, content_ids=new_content_ids or None)
    if not items:
        print("No items to digest after filtering.")
        return

    markdown = format_digest_markdown(items, role.name)
    out_path = write_digest(markdown, date=datetime.utcnow().date())
    print(f"Wrote digest to {out_path}")


if __name__ == "__main__":
    main()
