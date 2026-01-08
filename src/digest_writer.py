from datetime import date
from pathlib import Path


def write_digest(markdown: str, date: date) -> str:
    out_dir = Path("out")
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = f"digest-{date.isoformat()}.md"
    out_path = out_dir / filename
    out_path.write_text(markdown.strip() + "\n", encoding="utf-8")
    return str(out_path)
