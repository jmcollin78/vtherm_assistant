# VTherm Assistant: Home Assistant OS Operations

This documentation describes release `1.0.0` and its latest features. The app
opens through ingress and is restricted to HA administrators. It uses only the
official Home Assistant MCP server; it requires no host port or dashboard card.

## Features and Limitations

The assistant dynamically discovers all VTherm tools announced by the MCP
server whose schemas it accepts, for both reads and writes. It can read a
VTherm climate's state and diagnosis, published algorithm information, plugins,
history, and logs, as well as linked entity states, when the HA/VTherm versions
and configuration publish them. History requests are limited to 14 days and
results are bounded. Plugins, history, and logs are available only when the
VTherm version and MCP configuration expose them. The assistant distinguishes
observations from hypotheses; it cannot guarantee a failure's cause or freely
change internal algorithm settings.

Discovered VTherm write tools can change actions exposed by the integration,
for example HVAC mode, target temperature, a preset, or on/off state. The list
varies by version and thermostat. No generic Home Assistant write tool is
allowed.

The assistant can also search the official online VTherm documentation at
[versatile-thermostat.org](https://www.versatile-thermostat.org/). Search is
available in French, English, and German and returns targeted excerpts with
source-page links; it does not browse the entire site without limits.

**Every write requires separate, mandatory approval in advance.** The UI shows
the tool name, target VTherm, and exact arguments. A request in the conversation
is not approval. A rejected, ambiguous, or expired request is not executed.
After approval, the app reports the actual MCP result. Always verify the state
and effect in Home Assistant: approval or a response does not guarantee that
the heating behaves as intended.

## Prerequisites and Installation

Use Home Assistant OS with an active administrator account, a configured MCP
server, and a working Versatile Thermostat integration. Target VTherm climate
entities must be exposed to Assist to appear in the inventory. Expose only the
entities you need.

Repository: `https://github.com/jmcollin78/vtherm_assistant#ha-app`.

1. In **Settings > Apps > App Store > Repositories**, add the repository URL
   above, including the `#ha-app` suffix.
2. Install **VTherm Assistant** (release `1.0.0`), start it, and enable its
   sidebar entry.
3. Open the app through ingress with an HA administrator account.

The app does not require Docker access, a mount of the HA configuration, or
additional Supervisor privileges. The Core API verifies identity and access
rights; it does not replace the personal MCP token.

## Configure Home Assistant MCP

1. Go to **Settings > Devices & services > Add integration** and add
   **Model Context Protocol**, Home Assistant's MCP server.
2. Open the integration configuration and publish the VTherm APIs/tools needed
   by the assistant. Enable only useful tool sets. The assistant accepts a
   limited selection of HA reads and VTherm tools identified by their MCP
   namespaces.
3. In Assist's exposed-entities settings, expose only the VTherm climates the
   assistant should discover.
4. For history, make sure Recorder retained the requested period. Missing data
   does not prove that no event occurred.

API, tool, and option settings can vary by Home Assistant version. See the
[official MCP documentation](https://www.home-assistant.io/integrations/mcp_server/).
The app's internal Core URL is `ha_internal_url`, defaulting to
`http://homeassistant:8123`. It must be a base HTTP or HTTPS URL with no path,
credentials, query, or fragment. Never put a token in the URL. Over HTTP,
tokens and data are sent in clear text on the internal network; use a trusted
network or HTTPS with a verifiable certificate.

## Long-Lived Token

Each administrator stores a personal MCP token in the app settings:

1. In Home Assistant, open your **user profile > Security**.
2. Scroll to **Long-Lived Access Tokens**, select **Create Token**, and give it
   a clear name, such as `VTherm Assistant`.
3. Copy the token when it is created; it will not be shown again.
4. In the assistant settings, paste it into the **Home Assistant token** field
   and save.

The token must belong to an active administrator. It is separate from the
ingress session and `SUPERVISOR_TOKEN`, which the app uses only to verify rights
through Core. Never send any of these tokens in a conversation, bug report, or
log. Revoke the token in the HA profile when it is no longer needed. See the
[Home Assistant authentication documentation](https://www.home-assistant.io/docs/authentication/).

## Provider and Model

In the app settings, choose Google Gemini, OpenAI, Anthropic Claude, or Ollama.
Choose a model from the catalog or enter its ID manually. The catalog may show
models returned by the provider or preset suggestions; `unverified` means
tool-call and streaming compatibility has not been certified.

For a remote provider, save the key in its dedicated field. For Ollama, enter
a URL reachable from the app container and a model already installed on that
server. After saving, test with a read-only question. The configured model is
never replaced automatically by a suggestion.

## Privacy and Secrets

The app stores conversations and MCP results needed for context in its local
database. During generation, the conversation text and required results are
sent to the selected model provider; that provider's policy determines how
they are handled and retained. Redaction of known secrets cannot identify
unknown private information.

**Never enter an API key, username, password, token, callback code, sensitive
private address, or any other secret in a conversation.** Enter secrets only
in dedicated fields. Secrets stored in SQLite are not encrypted; protect any
backup containing the database and never attach it to an issue or PR.

## Conversation Recovery

The app saves the current conversation and context for each administrator.
After an app restart or container replacement, it resumes the latest saved
conversation. Past conversations are not archived: **New conversation** replaces
that user's current session without deleting saved secrets. Interrupted
responses are not saved as complete answers.

Automatic recovery is distinct from an exportable HA backup. An app backup
contains the database and therefore the secrets stored in it.

## App Backup

The manifest uses `backup: cold`: Supervisor temporarily stops the app to
back up its database without concurrent writes, then restarts it if it was
running. This may interrupt an active conversation, but does not require
stopping Home Assistant or the heating.

1. Confirm the temporary app interruption before starting.
2. In **Settings > System > Backups**, create a manual backup and select
   **VTherm Assistant only** for this isolated operation.
3. Verify that the archive contains the app and protect it as a secret. If it
   is encrypted, keep its recovery key out of chat and logs.
4. Verify that the app restarts and recovers its conversation.

## Restore

Restoring replaces the app's conversations, settings, and secrets with those
in the archive; changes made since then will be lost. An existing backup does
not automatically authorize a restore.

1. Verify the archive, app version, and availability of its decryption key.
   Separately confirm the restore and overwrite of current data.
2. If needed, back up the current app state first.
3. In Home Assistant's partial restore flow, select **VTherm Assistant** and
   its data only. Do not restore HA settings, Recorder, VTherm, or other apps
   to recover this conversation.
4. After restart, check ingress, the conversation, model, and MCP connection.
   A restored token may have been revoked; replace it in settings if needed.

Do not restore an old image over a migrated database unless compatibility is
documented. Changing the image tag alone does not restore data.

French version: [DOCS-fr](DOCS-fr.md).