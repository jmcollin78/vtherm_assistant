import os
import sqlite3
import stat
from contextlib import closing
from pathlib import Path


class PrivateDatabase:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.database = directory / "conversations.sqlite3"

    def connect(self) -> sqlite3.Connection:
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory_info = self.directory.lstat()
        if not stat.S_ISDIR(directory_info.st_mode) or directory_info.st_uid != os.getuid() or directory_info.st_mode & 0o077:
            raise PermissionError("Le répertoire de données doit être privé et appartenir au processus")
        descriptor = os.open(self.database, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            file_info = os.fstat(descriptor)
            if not stat.S_ISREG(file_info.st_mode) or file_info.st_uid != os.getuid() or file_info.st_mode & 0o077:
                raise PermissionError("La base de données doit être privée et appartenir au processus")
        finally:
            os.close(descriptor)
        connection = sqlite3.connect(self.database)
        connection.execute("PRAGMA secure_delete = ON")
        return connection


class SecretStore:
    def __init__(self, database: PrivateDatabase) -> None:
        self.database = database

    def _connect(self) -> sqlite3.Connection:
        connection = self.database.connect()
        connection.execute("CREATE TABLE IF NOT EXISTS secrets (user_id TEXT NOT NULL, name TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY (user_id, name))")
        return connection

    def put(self, user_id: str, name: str, value: str) -> None:
        if not user_id or not name or not value:
            raise ValueError("Identité, nom et valeur requis")
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("INSERT INTO secrets VALUES (?, ?, ?) ON CONFLICT(user_id, name) DO UPDATE SET value=excluded.value", (user_id, name, value))

    def get(self, user_id: str, name: str) -> str | None:
        if not user_id or not name:
            raise ValueError("Identité et nom requis")
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT value FROM secrets WHERE user_id = ? AND name = ?", (user_id, name)).fetchone()
        return row[0] if row else None

    def delete(self, user_id: str, name: str) -> None:
        if not user_id or not name:
            raise ValueError("Identité et nom requis")
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("DELETE FROM secrets WHERE user_id = ? AND name = ?", (user_id, name))


class ModelConfigStore:
    def __init__(self, database: PrivateDatabase) -> None:
        self.database = database

    def _connect(self) -> sqlite3.Connection:
        connection = self.database.connect()
        connection.execute("CREATE TABLE IF NOT EXISTS model_configs (user_id TEXT PRIMARY KEY, provider TEXT NOT NULL, model TEXT NOT NULL, url TEXT)")
        return connection

    def put(self, user_id: str, provider: str, model: str, url: str | None) -> None:
        if not user_id:
            raise ValueError("Une identité vérifiée est requise")
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("INSERT INTO model_configs VALUES (?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET provider=excluded.provider, model=excluded.model, url=excluded.url", (user_id, provider, model, url))

    def get(self, user_id: str) -> tuple[str, str, str | None] | None:
        if not user_id:
            raise ValueError("Une identité vérifiée est requise")
        with closing(self._connect()) as connection:
            return connection.execute("SELECT provider, model, url FROM model_configs WHERE user_id = ?", (user_id,)).fetchone()