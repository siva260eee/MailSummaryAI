# icloud-openai-digest

Fetches iCloud IMAP emails, summarizes and classifies them with OpenAI, and writes a grouped markdown digest.

## Setup

1) Create a virtual environment and install requirements:

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
```

2) Copy `.env.example` to `.env` and fill in values.

## Run

```bash
python -m src.main
```

## Notes

- Only `INBOX` is selected.
- Search uses `IMAP_SEARCH` (default `UNSEEN`).
- Emails are not moved. Use `MARK_SEEN=true` to mark them as read.
- `NEWSLETTER_ONLY=true` enables a light heuristic filter.
- Digest output: `out/digest-YYYY-MM-DD.md`.
