import json
import os
from pathlib import Path

import uvicorn

from .oauth import _validate_base_url


def _configure_ingress(options_path: Path = Path("/data/options.json")) -> None:
    try:
        options = json.loads(options_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if os.environ.get("SUPERVISOR_TOKEN"):
            raise ValueError("Options de l'app Home Assistant manquantes") from None
        address = os.environ.get("VTHERM_HA_INTERNAL_URL")
        if address is None:
            return
    except (OSError, UnicodeError, ValueError):
        raise ValueError("Options de l'app Home Assistant illisibles") from None
    else:
        if not isinstance(options, dict) or set(options) - {"ha_internal_url"}:
            raise ValueError("Options de l'app Home Assistant invalides")
        address = options.get("ha_internal_url", "http://homeassistant:8123")

    if not isinstance(address, str):
        raise ValueError("Adresse interne Home Assistant invalide")
    try:
        validated_address = _validate_base_url(address, public=False)
    except ValueError:
        raise ValueError("Adresse interne Home Assistant invalide") from None
    os.environ["VTHERM_HA_INTERNAL_URL"] = validated_address


def main() -> None:
    mode = os.environ.get("VTHERM_DEPLOYMENT_MODE", "standalone")
    if mode not in ("ingress", "standalone"):
        raise ValueError("Mode de déploiement inconnu")
    if mode == "ingress":
        _configure_ingress()
    uvicorn.run(
        "vtherm_assistant.main:app",
        host="0.0.0.0" if mode == "ingress" else "127.0.0.1",
        port=8099 if mode == "ingress" else 8765,
        proxy_headers=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()