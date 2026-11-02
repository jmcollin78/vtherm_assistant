import json
import os
import sqlite3
import stat
from contextlib import closing
from pathlib import Path
from typing import Any


class ConversationStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.database = directory / "conversations.sqlite3"

    def _connect(self) -> sqlite3.Connection:
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory_info = self.directory.lstat()
        if not stat.S_ISDIR(directory_info.st_mode) or directory_info.st_uid != os.getuid() or directory_info.st_mode & 0o077:
            raise PermissionError("Le répertoire de données doit être privé et appartenir au processus")
        descriptor = os.open(self.database, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            file_info = os.fstat(descriptor)
            if not stat.S_ISREG(file_info.st_mode) or file_info.st_uid != os.getuid() or file_info.st_mode & 0o077:
                raise PermissionError("La base de conversations doit être privée et appartenir au processus")
        finally:
            os.close(descriptor)
        connection = sqlite3.connect(self.database)
        connection.execute("CREATE TABLE IF NOT EXISTS conversations (user_id TEXT PRIMARY KEY, messages TEXT NOT NULL, context TEXT NOT NULL)")
        return connection

    def save(self, user_id: str, messages: list[dict[str, Any]], context: dict[str, Any]) -> None:
        if not user_id:
            raise ValueError("Une identité vérifiée est requise")
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO conversations VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET messages=excluded.messages, context=excluded.context",
                (user_id, json.dumps(messages), json.dumps(context)),
            )

    def load(self, user_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
        if not user_id:
            raise ValueError("Une identité vérifiée est requise")
        with closing(self._connect()) as connection, connection:
            row = connection.execute("SELECT messages, context FROM conversations WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            return None
        return json.loads(row[0]), json.loads(row[1])