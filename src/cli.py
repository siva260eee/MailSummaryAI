import argparse
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

from .digest_writer import write_digest
from .pipeline import build_digest_items, format_digest_markdown, ingest_emails
from .roles import enabled_roles, get_role, load_roles


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MailSummaryAI CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest new emails into the store")
    ingest_parser.add_argument("--quiet", action="store_true", help="Less console output")

    digest_parser = subparsers.add_parser("build-digest", help="Build a role-based digest")
    digest_parser.add_argument("--role", type=str, help="Role name (e.g., CTO)")
    digest_parser.add_argument("--all-roles", action="store_true", help="Build for all enabled roles")
    digest_parser.add_argument("--since-hours", type=int, default=None, help="Only include items since N hours")
    digest_parser.add_argument("--max-items", type=int, default=None, help="Maximum items to include")

    subparsers.add_parser("list-roles", help="List configured roles")

    return parser.parse_args()


def _build_for_role(role_name: str, since_hours: Optional[int], max_items: Optional[int]) -> str:
    roles = load_roles()
    role = get_role(role_name, roles)
    if not role:
        raise RuntimeError(f"Unknown role: {role_name}")

    items = build_digest_items(role, since_hours=since_hours, max_items=max_items)
    markdown = format_digest_markdown(items, role.name)
    out_path = write_digest(markdown, date=datetime.utcnow().date(), role=role.name)
    return out_path


def main() -> None:
    load_dotenv()
    args = _parse_args()

    if args.command == "ingest":
        new_count, skipped, _ = ingest_emails()
        if not args.quiet:
            print(f"Ingested: {new_count}, Skipped: {skipped}")
        return

    if args.command == "list-roles":
        roles = load_roles()
        for role in roles.values():
            status = "enabled" if role.enabled else "disabled"
            print(f"{role.name} ({status})")
        return

    if args.command == "build-digest":
        if args.all_roles:
            roles = enabled_roles(load_roles())
            for role in roles:
                out_path = _build_for_role(role.name, args.since_hours, args.max_items)
                print(f"Wrote digest for {role.name} to {out_path}")
            return

        if not args.role:
            raise RuntimeError("Provide --role or --all-roles")
        out_path = _build_for_role(args.role, args.since_hours, args.max_items)
        print(f"Wrote digest for {args.role} to {out_path}")


if __name__ == "__main__":
    main()
