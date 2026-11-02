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