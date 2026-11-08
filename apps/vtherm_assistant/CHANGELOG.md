# Changelog

## 1.0.0 - Dynamic VTherm Tools, 2026-11-08

- Discover accepted VTherm MCP tools dynamically, including newly published read and write tools.
- Expand diagnostics with plugin status, thermostat history, technical logs, linked entity states, and official VTherm documentation when available.
- Require a separate UI approval for every VTherm write, showing its target and arguments; generic Home Assistant writes remain unavailable.

## 0.1.2 - Conversations and Models, 2026-11-08

- Dynamic per-provider model catalogs, identified fallback suggestions, and
  manual model entry.
- Localized date and time before message authors; timestamps survive session
  recovery.
- Initial MCP VTherm inventory without model generation; saved without
  duplication, with error reporting and retry.
- Safe Markdown table rendering with horizontal scrolling.
- Read-only behavior, personal tokens, permissions, and Assist exposure
  unchanged; the new workflows still require validation on real HA OS.

## 0.1.1 - MCP Fix, 2026-11-08

- Accept the three VTherm read tools with the `assist__` prefix when HA merges
  multiple LLM APIs.
- Preserve unprefixed names when only one API is exposed.
- Write commands remain disallowed; local schemas and security checks are
  unchanged.

## 0.1.0 - Experimental Release, 2026-11-08

- Python 3.14.10 slim Debian image with pinned release dependencies.
- Local Linux arm64 and amd64 builds and tests.
- Public GHCR image; anonymous downloads verified for both architectures.
- Clean catalog distributed from the `ha-app` branch, without OpenSpec files.
- Ingress UI with relative assets and denial of access without OAuth.
- Internal HA URL option; per-user MCP and provider tokens.
- Private persistent storage and cold app backups.
- Supervisor permissions, streaming, and restore on HA OS still require
  verification.

French version: [CHANGELOG-fr](CHANGELOG-fr.md).