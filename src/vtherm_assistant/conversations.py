import json
import sqlite3
from contextlib import closing
from typing import Any

from .storage import PrivateDatabase


class ConversationStore:
    def __init__(self, database: PrivateDatabase) -> None:
        self.database = database

    def _connect(self) -> sqlite3.Connection:
        connection = self.database.connect()
        connection.execute("CREATE TABLE IF NOT EXISTS conversations (user_id TEXT PRIMARY KEY, messages TEXT NOT NULL, context TEXT NOT NULL)")
        return connection

    def save(self, user_id: str, messages: list[dict[str, Any]], context: dict[str, Any]) -> None:
        if not user_id:
            raise ValueError("Une identité vérifiée est requise")
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    "INSERT INTO conversations VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET messages=excluded.messages, context=excluded.context",
                    (user_id, json.dumps(messages), json.dumps(context)),
                )

    def load(self, user_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
        if not user_id:
            raise ValueError("Une identité vérifiée est requise")
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT messages, context FROM conversations WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            return None
        return json.loads(row[0]), json.loads(row[1])

    def delete(self, user_id: str) -> None:
        if not user_id:
            raise ValueError("Une identité vérifiée est requise")
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))