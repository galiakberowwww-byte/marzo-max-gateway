import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


QUESTIONS = (
    ("object", "Какой объект планируете: квартира, дом или коммерческое помещение?"),
    ("location", "В каком районе или населённом пункте находится объект?"),
    ("area", "Какая примерная площадь?"),
    ("timeline", "Когда хотите начать работы или подбор материалов?"),
    ("budget", "Какой ориентир по бюджету? Можно диапазоном."),
)


@dataclass
class LeadDraft:
    max_user_id: str
    source: str = "max_direct"
    direction: str | None = None
    answers: dict[str, str] = field(default_factory=dict)
    question_index: int = 0


class LeadStore:
    def __init__(self, database_path: str) -> None:
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS leads (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, source TEXT NOT NULL,
                direction TEXT NOT NULL, max_user_id TEXT, phone TEXT, customer_name TEXT,
                brief_json TEXT NOT NULL, status TEXT NOT NULL, interior_project_status TEXT NOT NULL
            )""")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def save(self, draft: LeadDraft, *, phone: str | None, customer_name: str | None) -> str:
        lead_id = f"MRZ-{datetime.now(UTC):%Y%m%d}-{uuid4().hex[:8].upper()}"
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO leads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (lead_id, datetime.now(UTC).isoformat(), draft.source, draft.direction or "unknown",
                 draft.max_user_id, phone, customer_name, json.dumps(draft.answers, ensure_ascii=False),
                 "qualified", "pending"),
            )
        return lead_id

    def add_manual(self, *, phone: str, direction: str, source: str, customer_name: str | None, brief: dict[str, str]) -> str:
        return self.save(LeadDraft(max_user_id="manager", source=source, direction=direction, answers=brief), phone=phone, customer_name=customer_name)

