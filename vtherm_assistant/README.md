# VTherm Assistant

![VTherm](logo.png)

A conversational assistant for diagnosing Versatile Thermostat in Home
Assistant OS. It discovers all VTherm tools published by the MCP server whose
schemas it accepts, and can analyze the states, history, and other diagnostics
they provide.

It can also search the official online VTherm documentation at
[versatile-thermostat.org](https://www.versatile-thermostat.org/) in French,
English, or German. Search returns targeted excerpts, not a complete copy of
the site.

Published VTherm actions (for example mode, target temperature, preset, or
on/off) each require explicit approval of the target and every argument in the
UI. Always verify in Home Assistant what actually changed. Availability depends
on VTherm, the MCP tools published and accepted, and the selected entity;
generic Home Assistant write commands are not available.

**Never enter secrets in conversations.** Messages and results used to answer
are sent to the configured model provider. Enter API keys and the Home
Assistant token only in their dedicated fields.

App repository:
`https://github.com/jmcollin78/vtherm_assistant#ha-app`

See [DOCS](DOCS.md) for installation, MCP configuration, long-lived tokens,
model selection, conversation recovery, backups, and restores. French version:
[README-fr](README-fr.md).