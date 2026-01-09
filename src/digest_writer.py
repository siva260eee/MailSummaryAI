from datetime import date
from pathlib import Path
from typing import Optional


def write_digest(markdown: str, date: date, role: Optional[str] = None) -> str:
    out_dir = Path("out")
    if role:
        out_dir = out_dir / role
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = f"digest-{date.isoformat()}.md"
    out_path = out_dir / filename
    out_path.write_text(markdown.strip() + "\n", encoding="utf-8")
    return str(out_path)
