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


def log_failure(logger: logging.Logger, operation: str, error: BaseException, *, stage: str = "request") -> None:
    codes = {
        "invalid_api_key": "authentication",
        "model_not_found": "model_access",
        "permission_denied": "permission",
        "insufficient_quota": "quota",
        "billing_hard_limit_reached": "quota",
        "rate_limit_exceeded": "rate_limit",
        "unsupported_parameter": "parameters",
        "invalid_request_error": "parameters",
        "context_length_exceeded": "context_limit",
        "account_deactivated": "authentication",
    }
    pending = [error]
    seen: set[int] = set()
    selected = error
    status = None
    code = "unknown"
    while pending and len(seen) < 50:
        candidate = pending.pop()
        if id(candidate) in seen:
            continue
        seen.add(id(candidate))
        selected = candidate
        candidate_code = getattr(candidate, "code", None)
        candidate_status = getattr(candidate, "status_code", None)
        if type(candidate_status) is not int:
            candidate_status = getattr(getattr(candidate, "response", None), "status_code", None)
        if type(candidate_status) is not int and type(candidate_code) is int:
            candidate_status = candidate_code
        body = getattr(candidate, "body", None)
        if isinstance(body, dict):
            details = body.get("error", body)
            if isinstance(details, dict):
                candidate_code = details.get("code") or candidate_code
        if type(candidate_status) is int and 100 <= candidate_status <= 599:
            status = candidate_status
        if isinstance(candidate_code, str) and candidate_code in codes:
            code = candidate_code
        if status is not None or code != "unknown":
            break
        if isinstance(candidate, BaseExceptionGroup):
            pending.extend(reversed(candidate.exceptions))
        cause = candidate.__cause__ or candidate.__context__
        if cause is not None:
            pending.append(cause)
    category = codes.get(code, {
        401: "authentication", 403: "permission", 404: "not_found",
        429: "rate_limit", 500: "server", 502: "server", 503: "server", 504: "timeout",
    }.get(status, "unexpected"))
    if category == "unexpected":
        if isinstance(selected, TimeoutError) or type(selected).__name__ in {"ReadTimeout", "ConnectTimeout", "APITimeoutError"}:
            category = "timeout"
        elif isinstance(selected, ConnectionError) or type(selected).__name__ in {"ConnectError", "APIConnectionError"}:
            category = "connection"
    logger.error(
        "operation=%s stage=%s error_type=%s http_status=%s code=%s category=%s",
        operation, stage, type(selected).__name__, status or "unknown", code, category,
    )


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