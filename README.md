# MailSummaryAI - Role-Based Email Digest Generator

MailSummaryAI ingests iCloud IMAP newsletters into a local SQLite store, caches all AI work, and generates role-based digests (CEO, CTO, Developer, Tester, Investor) with two concise angles per item.

## Key Features

- **Strict dedupe**: Uses IMAP UID + Message-ID + content hash. Stored emails are never re-processed.
- **Header-first ingest**: Skips known emails before fetching full bodies or links.
- **AI caching**: Summaries, categories, topic tags are computed once per content item. Role angles are cached per (content_id, role).
- **Role-based digests**: Each digest includes a startup angle plus a role-specific angle.
- **Optional link enrichment**: Fetches and appends article content from extracted URLs with interactive limits.

## Setup

1) Create a virtual environment and install requirements:

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
```

2) Copy `.env.example` to `.env` and fill in values.

## Roles Configuration

Edit `roles.yaml` to enable/disable roles and tune objectives:

```yaml
roles:
  CTO:
    enabled: true
    objectives:
      - Track architecture or platform shifts that affect product delivery.
    focus_categories:
      - DevOps
      - AI/ML
    focus_topics:
      - infrastructure
```

## Commands

### Ingest (IMAP only)

```bash
python -m src.cli ingest
```

- Uses UID search and header-first dedupe.
- Stores only new content in SQLite (`STORE_PATH`, default `out/store.db`).

### Build Digest (no IMAP)

```bash
python -m src.cli build-digest --role CTO --since-hours 24 --max-items 20
```

```bash
python -m src.cli build-digest --all-roles
```

Digests are written to `out/<ROLE>/digest-YYYY-MM-DD.md`.

### List Roles

```bash
python -m src.cli list-roles
```

### Backward-Compatible Entry Point

```bash
python -m src.main
```

This ingests new emails and builds a CTO digest for the emails ingested in that run. Output is written to `out/digest-YYYY-MM-DD.md` to preserve the prior behavior.

## Caching and Dedupe Details

- **Never re-process stored emails**: On ingest, UID headers are fetched first. If Message-ID or UID exists in `content_items`, the email is skipped without downloading the full body or links.
- **Content hash**: Each item has a `content_id` (sha256 of canonical fields) to prevent duplicates when Message-ID is missing.
- **AI caches**:
  - `ai_cache`: summary, category, topic tags (once per content item).
  - `role_cache`: startup angle + role angle (once per content_id + role).
- Re-running digests uses the cache and avoids OpenAI calls unless missing.

## Output Format

```markdown
# Digest of Recent Insights

## AI/ML
- **Title (Domain: AI SaaS)**
  - **Startup angle:** ...
  - **CTO angle:** ...
```

## Environment Variables

See `.env.example` for the full list. Common options:

- `IMAP_SEARCH` (default `UNSEEN`)
- `MARK_SEEN` (`true`/`false`)
- `NEWSLETTER_ONLY` (`true`/`false`)
- `FETCH_LINKS` (`true`/`false`)
- `MAX_LINKS_TO_FETCH` (default `10`)
- `INTERACTIVE_LINK_FETCH` (`true`/`false`)
- `STORE_PATH` (default `out/store.db`)

## Project Structure

```
icloud-openai-digest/
├── src/
│   ├── cli.py
│   ├── icloud_imap.py
│   ├── email_parse.py
│   ├── link_fetcher.py
│   ├── agent_pipeline.py
│   ├── pipeline.py
│   ├── store.py
│   └── digest_writer.py
├── roles.yaml
├── out/
└── README.md
```
