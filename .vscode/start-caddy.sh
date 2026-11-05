#!/bin/sh
set -eu

if ! command -v brew >/dev/null 2>&1; then
	for brew_path in /opt/homebrew/bin/brew /usr/local/bin/brew; do
		if [ -x "$brew_path" ]; then
			PATH="$(dirname "$brew_path"):$PATH"
			export PATH
			break
		fi
	done
fi

if ! command -v caddy >/dev/null 2>&1; then
	if ! command -v brew >/dev/null 2>&1; then
		printf '%s\n' "Caddy est absent et Homebrew est introuvable. Installez Homebrew, puis relancez cette tâche." >&2
		exit 1
	fi
	brew install caddy
fi

exec caddy run --config "$1" --adapter caddyfile