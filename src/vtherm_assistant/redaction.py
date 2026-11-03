import logging
import traceback
from contextlib import asynccontextmanager
from contextvars import ContextVar


_log_secrets: ContextVar[tuple[str, ...] | None] = ContextVar("log_secrets", default=None)
_original_record_factory = logging.getLogRecordFactory()
_sensitive_transports = ("httpx", "httpcore", "authlib", "websockets", "mcp")


@asynccontextmanager
async def protect_logs(secrets):
    values = tuple(secret for secret in secrets if secret)
    token = _log_secrets.set((_log_secrets.get() or ()) + values)
    try:
        yield
    finally:
        _log_secrets.reset(token)


def _protected_record_factory(*args, **kwargs):
    record = _original_record_factory(*args, **kwargs)
    secrets = _log_secrets.get()
    if secrets is not None:
        if record.name.split(".", 1)[0] in _sensitive_transports:
            record.msg = "Journal de transport sensible masqué"
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
        else:
            record.msg = redact_data(record.getMessage(), secrets)
            if record.exc_info:
                record.exc_text = redact_data("".join(traceback.format_exception(*record.exc_info)), secrets)
                record.exc_info = None
            if record.stack_info:
                record.stack_info = redact_data(record.stack_info, secrets)
        record.args = ()
    return record


logging.setLogRecordFactory(_protected_record_factory)


class StreamingRedactor:
    def __init__(self, secrets: list[str] | tuple[str, ...]) -> None:
        self.secrets = tuple(sorted({secret for secret in secrets if secret}, key=len, reverse=True))
        self.pending = ""

    def feed(self, text: str, *, final: bool = False) -> str:
        self.pending += text
        output = []
        while self.pending:
            if not final and any(secret.startswith(self.pending) and len(secret) > len(self.pending) for secret in self.secrets):
                break
            match = next((secret for secret in self.secrets if self.pending.startswith(secret)), None)
            if match is not None:
                output.append("[masqué]")
                self.pending = self.pending[len(match):]
            else:
                output.append(self.pending[0])
                self.pending = self.pending[1:]
        return "".join(output)


def redact_data(value, secrets: list[str] | tuple[str, ...]):
    if isinstance(value, str):
        return StreamingRedactor(secrets).feed(value, final=True)
    if isinstance(value, list):
        return [redact_data(item, secrets) for item in value]
    if isinstance(value, dict):
        return {redact_data(key, secrets): redact_data(item, secrets) for key, item in value.items()}
    return value