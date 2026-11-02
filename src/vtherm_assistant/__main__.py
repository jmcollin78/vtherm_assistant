import os

import uvicorn


def main() -> None:
    mode = os.environ.get("VTHERM_DEPLOYMENT_MODE", "standalone")
    if mode not in ("ingress", "standalone"):
        raise ValueError("Mode de déploiement inconnu")
    uvicorn.run(
        "vtherm_assistant.main:app",
        host="0.0.0.0" if mode == "ingress" else "127.0.0.1",
        port=8099 if mode == "ingress" else 8765,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()