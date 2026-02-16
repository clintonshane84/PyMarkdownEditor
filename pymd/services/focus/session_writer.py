from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pymd.domain.interfaces import IFileService


class SessionWriter:
    """Create session notes and append local JSONL logs."""

    def __init__(self, file_service: IFileService) -> None:
        self._files = file_service

    def create_note(
        self,
        *,
        folder: Path,
        session_id: str,
        start_at: datetime,
        focus_minutes: int,
        break_minutes: int,
        title: str,
        tag: str,
        interruptions: int = 0,
    ) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        slug = self._slugify(title) if title.strip() else "focus-session"
        note_path = folder / f"{session_id}-{slug}.md"
        note_body = self._build_template(
            session_id=session_id,
            start_at=start_at,
            focus_minutes=focus_minutes,
            break_minutes=break_minutes,
            title=title,
            tag=tag,
            interruptions=interruptions,
        )
        self._files.write_text_atomic(note_path, note_body)
        return note_path

    def append_log(self, *, log_entry: dict[str, object], at_time: datetime | None = None) -> Path:
        now = at_time or datetime.now().astimezone()
        log_dir = Path.home() / ".focusforge" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        out = log_dir / f"{now.date().isoformat()}.jsonl"
        line = json.dumps(log_entry, ensure_ascii=True)
        with out.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        return out

    def _build_template(
        self,
        *,
        session_id: str,
        start_at: datetime,
        focus_minutes: int,
        break_minutes: int,
        title: str,
        tag: str,
        interruptions: int,
    ) -> str:
        safe_title = title.strip() or "Focus Session"
        safe_tag = tag.strip()
        preset = f"{focus_minutes}/{break_minutes}"
        start_iso = start_at.astimezone().isoformat(timespec="seconds")
        frontmatter = [
            "---",
            f"id: {session_id}",
            f"start: {start_iso}",
            f"preset: {preset}",
            f"tag: {safe_tag}",
            f"interruptions: {interruptions}",
            "---",
            "",
        ]
        content = [
            f"# {safe_title}",
            "",
            "## Goal",
            "-",
            "",
            "## Notes",
            "-",
            "",
            "## Next actions",
            "- [ ]",
            "",
        ]
        return "\n".join(frontmatter + content)

    def _slugify(self, text: str) -> str:
        chars = []
        prev_dash = False
        for ch in text.lower():
            if ch.isalnum():
                chars.append(ch)
                prev_dash = False
            elif not prev_dash:
                chars.append("-")
                prev_dash = True
        slug = "".join(chars).strip("-")
        return slug or "focus-session"
