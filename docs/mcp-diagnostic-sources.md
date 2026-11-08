# VTherm MCP Diagnostic Sources

## Verification Status as of 2026-11-08

- The local instance exposed on port `8123` runs Home Assistant Core
  `2026.10.4`, confirmed from its container. The VTherm checkout is at Git tag
  `10.6.4`, although the manifest in that tag declares version `10.6.3`. This
  metadata discrepancy exists in the tag and was not corrected.
- On 2026-11-08, an administrator OAuth session in the app obtained an MCP
  inventory of two climates. Unfiltered `homeassistant__GetLiveContext` and the
  status of `climate.thermostat_switch_1` both returned data. The global context
  was kept distinct from a targeted read; no dependencies were queried for
  history.
- History for `climate.thermostat_switch_1` was read for 24 hours, from
  `2026-11-07T19:15:00Z` to `2026-11-08T19:15:00Z`: 18 rows, complete
  pagination, and no truncation reported. These are Recorder state changes,
  not regular samples; retention, exclusions, and gaps remain limitations.
- `get_plugins` returned for this climate: no identified configured plugin
  (`configured_plugin_count: 0`), with diagnostics unsupported. Discovery is
  limited to covered categories and is not exhaustive for third-party or future
  plugins.
- `get_logs` returned for this climate at `DEBUG` over the same requested
  window: 140 entries selected, 100 returned, 40 omitted. Returned rows cover
  `18:59:56.183Z` to `19:14:57.131Z`, not the full 24-hour window. The
  documented upstream limit is 5000 entries; the app projection limits results
  sent onward to 100 items and 64 KiB.
- A positive permission check was performed for the administrator identity
  used by the app; no non-administrator denial test was performed. A request to
  change the target temperature was rejected by the assistant. A subsequent
  read kept `off`, `7.0`, and the same `last_changed`
  (`2026-11-08T18:59:57.081703Z`). `last_updated` changed during observation;
  that change was not attributed to the diagnostic. This evidence came from an
  earlier read-only client and does not describe the write capability of later
  code.
- Tools are exposed only under their exact announced names. History periods
  must be explicit, timezone-aware, and no longer than 14 days; pages are
  limited to 500 rows, and projected responses to 100 items and 64 KiB.
  Structured access-denied and Recorder-unavailable errors are distinguished
  from empty results; other untrusted error bodies are replaced with a generic
  message.
- In the integrated validation, a target-temperature change was rejected. An
  immediate read of the same climate still showed `off`, target `7.0`, and
  `last_changed` `2026-11-08T18:59:57.081703Z`. No MCP write tool was allowed
  by that client and the test did not change HA/VTherm state.
- Integrated app, MCP client, conversation, and secret tests (186 passed on
  2026-11-08) cover isolation of two app identities, rejection of a different
  user and an unselected VTherm target, redaction of known secrets, exclusion
  of unprojected fields, and unavailable, erroneous, and truncated sources.
- The two identities, secrets, and missing/unavailable sources are simulated
  by tests. No second HA identity was used, and no secret was injected into
  logs or plugins on the live instance. Live validation confirms only the
  workflows actually accessible without modifying the installation.

## Linked Entities and Data Minimization

In the VTherm code at tag `10.6.4` (whose manifest says `10.6.3`), the fields
that establish an entity relationship are `vtherm_over_switch.underlying_entities`,
`vtherm_over_valve.underlying_entities`, and
`vtherm_over_climate.underlying_entities`, depending on the thermostat type.
For `over_climate`, `vtherm_over_climate.temp_synchronisation.sync_entity_ids`
adds synchronization entities when published. These IDs are used only to
target a state read through `GetLiveContext` with `name` set to the exact
`entity_id`; they do not authorize a general search or history for a dependency.
Other attributes containing entity keys, names, areas, configuration, and
global context do not prove a relationship.

`get_status` and `diagnose` return more than these IDs, including configuration
and preset temperatures. Application secret redaction covers only known
secrets and does not filter fields. Therefore, raw responses must not be sent
to the model: an explicit, tested projection of only necessary diagnostic
fields is required. The `configuration` and `preset_temperatures` sections,
plugin configuration, and raw logs are excluded. OpenSpec task 2.3's projection
tests cover known/unknown secrets and excluded fields. The IDs above establish
relationships without reading or transmitting configuration.

## Superseded Historical Proposal

The original proposal was to let the assistant inspect events already recorded
for a thermostat and relevant entities over an explicit period, without taking
action or changing Home Assistant, VTherm, or Recorder retention. The tool was
to be exposed by the official HA MCP server, not a second server.

The proposed read-only tool (for example,
`versatile_thermostat__get_history`; final name to be agreed) would receive the
VTherm ID and requested entity IDs, an inclusive start and exclusive end with
an explicit timezone, a bounded page size, and an optional opaque cursor. It
would return the entities queried and actual period covered; stably ordered
events with entity ID, timestamp, state, and available attributes; a next-page
cursor or explicit end-of-results marker; unavailable data and safe reasons;
and any known coverage or truncation limits. Missing events must not be
confused with missing records. A cursor would be tied to the same query and
avoid duplicates or omissions across pages, including events with equal
timestamps; expired or invalid cursors would have explicit behavior.

Coverage was intended to include relevant thermostat dependencies, such as
temperatures, setpoints, modes, actuators, and recorded inhibition reasons.
Values or attributes not retained must not be reconstructed. Discovery and
reads must respect HA permissions and official MCP entity exposure. The
assistant's token can be an administrator token distinct from the ingress user;
the tool must not assume it automatically delegates the ingress identity.
Authorization errors must not reveal inaccessible data, and no write tool or
service should be required.

Original verification criteria included checking periods, timezones, boundary
conditions and pagination; returning available states and attributes with
timestamps and sources; explicitly describing absent, partial, expired, or
unrecorded history; testing hidden entities and denied access without data
leaks; making no changes to VTherm, Home Assistant, or Recorder retention; and
detecting unavailable tools on versions that do not provide them, including
VTherm `10.6.3` at that time. Availability, permissions, side effects, and
version compatibility were to be verified after delivery.

## Inventory and Exposure Investigation

This section records the progression of a real-instance investigation; it is
not a blanket compatibility claim.

The local test was strengthened with a fake result containing ten VTherm
entities. The count and all entities passed through the client and ADK tool
without truncation. Three focused tests passed. This did not prove the live MCP
payload or model output. On HA OS `0.1.1`, the user initially reported four
VTherm in a system containing more. That conversation answer alone did not
prove the raw MCP result, invoked tools, absence of write calls, or streaming.

Upstream VTherm `10.6.3`, in
`custom_components/versatile_thermostat/llm.py`, selects climate entities from
its config entries that are present in HA state and exposed to the assistant
according to `async_should_expose`. `ListVThermsTool` returns the list and
count without a four-entity limit. The local MCP client does not truncate it.
`Expose all LLM APIs` does not bypass entity exposure.

A direct MCP call performed by the user returned
`assist__versatile_thermostat__list_vtherms`, count `4`, and the same four
entities as the conversation. The check used only `tools/list` and `tools/call`
with empty arguments for the list tool; it did not request a heating command or
change exposure. This corroborated that the omission was in the HA/VTherm
server path for that call, not LLM truncation.

A read-only comparison of a missing and a returned climate checked
`config/entity_registry/get_entries`, `conversation` exposure options, and
presence in HA states. Both entities were registered, loaded, on the
`versatile_thermostat` platform, and not disabled. The missing entity had
`conversation.should_expose: false` and no assistant in
`homeassistant/expose_entity/list`; the returned entity had
`conversation.should_expose: true` and was listed for `conversation`. This
established non-exposure to Assist as the cause for that omission, not
necessarily for every missing entity.

The user found the unexposed climate in its entity details under voice
assistants and enabled Assist exposure. They confirmed it reappeared. The
count then increased from four to five. The user made this HA change; the agent
did not modify HA or republish the app. A discrepancy between the general
exposure screen and the entity detail remained an unreplicated UI/cache
hypothesis. The count of five did not prove the whole installation was
represented. The user later reported count `12` and twelve climate entities,
and confirmed the inventory issue resolved. No automatic comparison to the HA
registry was performed, and the changes that preceded the count of twelve were
not detailed.

The official HA `2026.10.4` MCP server uses `assistant="conversation"` and
returns tool data as JSON without truncation. No floor/area filter is added in
that path. The next discriminating check was a direct call to `/api/mcp` from
the HA browser session, using `tools/list` and the authorized `list_vtherms`
tool, recording only the exact tool name, count, and entity IDs. The frontend
`hass.callApi` in version `20260930.5` accepts the required JSON headers and
reuses the existing authentication without reading or displaying a token.

## Streaming and Documentation Lookup Investigation

The user confirmed that an actual VTherm diagnosis matched the HA state.
Initially, a long wait followed by a response that seemed to appear all at once
left streaming unproven. Code inspection showed that documentation search can
download a sitemap and then up to 20 pages sequentially if invoked. The
conversation renderer does not display tool-call or tool-result events; it
forwards model text fragments. These facts do not prove that web search was
used in the reported session, explain the delay, or establish ingress buffering.

The user then requested 30 sentences without a tool or web lookup. The first
impression on HA OS was a response appearing all at once after about five
seconds. On another attempt through HA's local HTTP address, without the
external Nginx reverse proxy, the user saw three or four closely spaced display
packets after several seconds. This corrected the earlier impression of no
streaming: rapid progressive display was observed, but the timing of fragments
relative to request completion was not established. Nginx was not required to
reproduce the behavior, which does not prove that it never affects the
external route. No Nginx or HA configuration was changed.

A local temporal test in `tests/test_conversations.py` blocks the second
simulated provider fragment until the first ASGI `http.response.body` with
`more_body: true` is received. Gemini, OpenAI, Anthropic, and Ollama variants,
plus OpenAI `gpt-6-luna`, pass with ADK, redaction, and ingress middleware
enabled; the answer is finalized and saved without duplication. The user
confirmed the live provider and model as OpenAI `gpt-6-luna`. The matching test
checks `stream=True` and the existing `reasoning_effort="none"`; it makes no
real provider call and uses no personal key.

```sh
arch -arm64 .venv/bin/python -m pytest -q tests/test_conversations.py -k ingress_route_emits_first_fragment
```

Result: five tests passed. This ASGI test does not cover Uvicorn networking, a
real provider, the browser, or HA proxies. The two reported real paths were
HTTPS through local Nginx resolving to a public IP, then direct local-network
HTTP to HA; the app remained behind ingress in both. The user later clearly
confirmed that twelve VTherm appeared progressively on HA OS `0.1.1`, and
asked to mark streaming resolved. This is user-observed evidence, not a
timestamped network capture. Inventory discovery and streaming were resolved
by that report. OpenSpec task 6.3 remained open for a trace of tools actually
called and evidence of no command call in the real conversation; local
simulations and direct read-only MCP calls do not replace that trace.

A separate local frontend issue was that Markdown tables displayed as text.
The local fix added table rendering with cells built without raw HTML and
horizontal scrolling. The reproduction failed before the fix on desktop and
mobile; after the fix, 12 tests passed:

```sh
arch -arm64 .venv/bin/python -m pytest -q tests/test_frontend.py -k 'markdown or conversation_stream or navigation_under_ingress'
```

These tests cover history, fragment receipt, and reload under simulated
ingress, not real HA OS network streaming. The fix was not published. Public
tags `0.1.0` and `0.1.1` were unchanged. OpenSpec task 6.3 and tasks 6.4-6.6
were still open at that point (21/25 complete).

## Release and Deployment Records

On 2026-11-08, after explicit approval, image
`ghcr.io/jmcollin78/vtherm-assistant:0.1.0` was published with multi-architecture
index digest
`sha256:1e706799da51a80d83cf39f32ed14123177d541978dc6be01dc0d5878fbeea8d`.
All 12 Docker tests passed. Published arm64 and amd64 manifests matched the
tested images; version, source, and revision labels were checked. Each
configuration and layer was downloaded from the anonymous registry with size
and SHA-256 verified. The `ha-app` catalog was published at
`5cc3de833d08c81c4f125d76be02ecad90384888` and contained exactly nine expected
files, without OpenSpec or application source. The user confirmed the catalog
showed only Assistant VTherm, version `0.1.0`, experimental stage, and
successfully installed with `ha_internal_url` set to
`http://homeassistant:8123`. Ingress opening was confirmed for the current
account; denial for another account was not tested. No HA/VTherm update,
heating change, or entity exposure change was needed for that installation.

The `0.1.0` instance was reported as HA Core `2026.10.4`, Supervisor
`2026.10.5`, OS `18.4`, frontend `20260930.5`, amd64, and VTherm `10.6.3`.
Installation, sidebar, and conversation page were confirmed. Full ingress,
permissions, streaming, persistence, real account isolation, error handling,
and backup/restore were not certified by that confirmation.

Publication steps documented in the French source are authorization-gated:
source push and successful CI first; consistency and uniqueness of the
immutable version tag; separately approved GHCR publication; both image
architectures and anonymous pulls verified before catalog publication; then a
new catalog from the `ha-app` branch, preserving its history and excluding
OpenSpec. No force-push, implicit CI publication, or operation on primary HA
is authorized by this record.

French version: [contrat-historique-mcp-fr](contrat-historique-mcp-fr.md).