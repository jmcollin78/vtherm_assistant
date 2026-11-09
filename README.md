[![GitHub Release][releases-shield]][releases] [![GitHub Activity][commits-shield]][commits] [![License][license-shield]](LICENSE) [![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

<p align="center">
<img src="brand/icon@2x.png" />
</p>

# VTherm Assistant

A conversational assistant for diagnosing and understanding [Versatile
Thermostat](https://github.com/jmcollin78/versatile_thermostat) thermostats in
Home Assistant. This documentation describes release `1.0.0` and its latest
features.

> **Privacy:** Questions, tool results needed for diagnosis, and context sent
> to the model are transmitted to the selected provider (OpenAI, Google,
> Anthropic, or the configured Ollama server). Never enter an API key, username,
> password, token, sensitive private address, or any other secret in a
> conversation. Secrets entered in dedicated settings fields must not be copied
> into messages.

## What It Does

The assistant dynamically discovers all VTherm tools announced by the Home
Assistant MCP server whose schemas it accepts, for both reads and writes. It
explains the available data in natural language. Depending on the tools
published by the installed versions, it can:

- summarize a thermostat's current state and diagnosis: temperatures, target
  temperature, mode, algorithm phase, action, hysteresis, modulation, and the
  reason reported by VTherm;
- inspect known VTherm plugins and their status when a plugin diagnostic tool is
  available;
- inspect a thermostat's history, technical logs, and the states of linked
  entities when the relevant tools and data are available;
- explain a situation such as a thermostat that is not heating, compare
  available observations, or suggest checks;
- search the official online VTherm documentation at
  [versatile-thermostat.org](https://www.versatile-thermostat.org/) in French,
  English, or German, and cite useful source pages.

Available tools and data depend on Home Assistant, VTherm, entity exposure, and
the MCP configuration. A diagnosis analyzes the available information; it does
not guarantee a cause or provide access to the algorithm's internal code.

The assistant can also request a VTherm change exposed by the integration, for
example changing the HVAC mode, target temperature, or preset, or turning a
thermostat on or off. These examples are not exhaustive; availability depends
on the thermostat and the MCP tools actually published. **Every published and
accepted VTherm write tool requires a separate, mandatory approval in the UI.**
Before a call, the assistant displays the target thermostat, action, and every
argument. Review them and approve or reject the request. The original chat
request is never approval. A rejected, ambiguous, or expired request is not
executed. After approval, always verify in Home Assistant what actually changed
and its effect on the heating; a tool result or assistant response is not a
substitute for that check. No generic Home Assistant write tool is exposed.

## Overview

![Splash screen](images/screen-2.png)

![Full state](images/screen-3.png)

![Why stopped](images/screen-4.png)

![Turn on](images/screen-5.png)

## Example Questions

### Diagnosis

> Give me the full status of `Office thermostat`

> Why did the thermostat turn off around 12:30?

> Give me an overview of SmartPI

> Are my TPI settings configured correctly?

> Why did the office thermostat switch to safety mode?

### Actions

> Turn on the `office thermostat` and set the preset to comfort

> Turn off the `office thermostat`

### VTherm Features

> How does safety mode work?

> What's the difference between presence detection and motion detection in Versatile Thermostat?

Ask away! Share your best conversations in the [discussions](https://github.com/jmcollin78/vtherm_assistant/discussions/).

## Install and Configure

The Home Assistant OS version is installed as an app from the repository:

1. In **Settings > Apps > App Store > Repositories**, add
   `https://github.com/jmcollin78/vtherm_assistant#ha-app`, keeping the
   `#ha-app` suffix.
2. Install **VTherm Assistant** (release `1.0.0`), start it, and open it from
   the sidebar. No host port or dashboard card is required.
3. Configure the MCP server and personal token in the assistant settings as
   described below.

### Configure Home Assistant MCP

1. Make sure the Versatile Thermostat integration is installed and the target
   thermostats are loaded.
2. Go to **Settings > Devices & services > Add integration** and add
   **Model Context Protocol**, Home Assistant's MCP server.
3. In the integration options, publish the APIs/tools required by VTherm. Do
   not enable unnecessary tool sets. The assistant filters the tools it accepts
   and exposes no generic Home Assistant write command.
4. In Home Assistant's Assist exposed-entities settings, expose only the
   VTherm climate entities you want the assistant to discover. Reads of linked
   entities are limited to entities whose relationship to the VTherm has been
   established.
5. See the [official Home Assistant MCP server documentation](https://www.home-assistant.io/integrations/mcp_server/)
   for details about the integration and its options.

### Create a Home Assistant Token

Each administrator configures their own long-lived token for MCP calls. In
Home Assistant, open your **user profile > Security**, scroll to **Long-Lived
Access Tokens**, select **Create Token**, give it a recognizable name (for
example, `VTherm Assistant`), and copy its value immediately. Home Assistant
will not show it again. Save it in the Home Assistant token field in the
assistant settings, never in a conversation, URL, repository file, or log.
Revoke it from your profile when it is no longer needed.

This personal token is for MCP. It is separate from the UI login and the app's
internal `SUPERVISOR_TOKEN`; do not use one in place of the other.

### Choose a Model

In settings, select **Google Gemini**, **OpenAI**, **Anthropic Claude**, or
**Ollama**, then choose a model ID from the catalog or enter it manually.
Dynamic catalogs list models returned by the provider, but their presence does
not certify compatibility. Choose a model that supports tool calls and
streaming. Preset suggestions do not guarantee access to a model or its
compatibility.

For a remote provider, enter its key only in the dedicated field. For Ollama,
the model must already be installed, and its URL must be reachable from the
assistant backend, not just from your browser. After configuration, start with
a read-only question.

## Conversations and Backups

The app automatically stores the current conversation and its context in
private local storage, separately for each verified Home Assistant
administrator. It restores that conversation after an app restart. It does not
archive every past conversation: **New conversation** replaces the current
session for that user. Fragments from an interrupted response are not saved as
a complete answer.

To keep an independent restore point, create a Home Assistant backup of
**VTherm Assistant only**. Restoring replaces the app's conversation,
configuration, and secrets with those in the archive; do not include Home
Assistant settings, Recorder, VTherm, or other apps. Backups contain secrets
that are not encrypted at the application database level, so protect the
archive and its key. See the [HA operations guide](apps/vtherm_assistant/DOCS.md)
for the full procedure.

## Documentation and Development

- [HA OS operations guide](apps/vtherm_assistant/DOCS.md)
- [Local development guide](docs/development.md)
- [Contribution guidelines](CONTRIBUTING.md)
- [HA app build and test guide](docs/ha-app-build.md)
- [MCP diagnostic sources](docs/mcp-diagnostic-sources.md)
- French documents use the `-fr` suffix, for example [README-fr](README-fr.md).

## License

See [LICENSE](LICENSE).


***

[vtherm_assistant]: https://github.com/jmcollin78/vtherm_assistant
[buymecoffee]: https://www.buymeacoffee.com/jmcollin78
[buymecoffeebadge]: https://img.shields.io/badge/Buy%20me%20a%20beer-%245-orange?style=for-the-badge&logo=buy-me-a-beer
[commits-shield]: https://img.shields.io/github/commit-activity/y/jmcollin78/vtherm_assistant.svg?style=for-the-badge
[commits]: https://github.com/jmcollin78/vtherm_assistant/commits/master
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/jmcollin78/vtherm_assistant.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-Joakim%20Sørensen%20%40ludeeus-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/jmcollin78/vtherm_assistant.svg?style=for-the-badge
[releases]: https://github.com/jmcollin78/vtherm_assistant/releases
