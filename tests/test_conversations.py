import os
import stat
import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import httpx
from fastapi.testclient import TestClient
from google.adk.runners import Runner
from google.adk.events import Event
from google.adk.sessions import InMemorySessionService
from google.adk.tools import BaseTool
from google.genai import types
from litellm.types.utils import Delta, ModelResponseStream, StreamingChoices
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from vtherm_assistant.conversations import ConversationResponse, ConversationRunner, ConversationStore, IncompleteResponse
from vtherm_assistant.documentation import VersatileThermostatDocumentationTool
from vtherm_assistant.ha_mcp import MCPTool
from vtherm_assistant.main import SUPERVISOR_ADDRESS, create_app
from vtherm_assistant.oauth import OAuthConfig, OAuthTokens
from vtherm_assistant.oauth_flow import SESSION_COOKIE, Session
from vtherm_assistant.storage import PrivateDatabase


@pytest.mark.parametrize("language", ["fr", "en", "de"])
def test_documentation_tool_searches_only_official_language_docs(language) -> None:
    requested = []

    async def handle(request):
        requested.append(str(request.url))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=(
                f'<urlset><url><loc>https://www.versatile-thermostat.org/{language}/docs/feature-window/</loc></url>'
                '<url><loc>https://attacker.example/fr/docs/feature-window/</loc></url>'
                '</urlset>'
            ))
        return httpx.Response(200, text="<html><nav>ignore</nav><main>La détection fenêtre ouverte coupe le chauffage automatiquement.</main></html>")

    tool = VersatileThermostatDocumentationTool(transport=httpx.MockTransport(handle))
    result = asyncio.run(tool.run_async(
        args={"query": "détection fenêtre chauffage", "language": language},
        tool_context=SimpleNamespace(user_id="alice"),
    ))

    assert len(result["results"]) == 1
    assert "détection fenêtre ouverte" in result["results"][0]["excerpt"]
    assert requested == [
        "https://www.versatile-thermostat.org/sitemap.xml",
        f"https://www.versatile-thermostat.org/{language}/docs/feature-window/",
    ]


def test_response_stream_masks_split_secrets_and_avoids_final_duplication() -> None:
    response = ConversationResponse("vtherm_assistant", ["secret-key"])
    def event(text, partial):
        return Event(author="vtherm_assistant", partial=partial,
                     content=types.Content(parts=[types.Part(text=text)]))

    output = response.accept(event("Bonjour secret-", True))
    output += response.accept(event("key !", True))
    output += response.accept(event("Bonjour secret-key !", False))
    response.finish()
    assert output == "Bonjour [masqué] !"


def test_response_stream_captures_exact_adk_tool_confirmation() -> None:
    response = ConversationResponse("vtherm_assistant", [])
    arguments = {"entity_id": "climate.salon", "temperature": 20}
    payload = {
        "user_id": "alice", "tool_name": "versatile_thermostat__set_temperature",
        "arguments": arguments, "function_call_id": "call-1",
        "expires_at": 2000000000, "nonce": "n" * 32,
    }
    event = Event(author="vtherm_assistant", content=types.Content(role="model", parts=[
        types.Part(function_call=types.FunctionCall(
            name="adk_request_confirmation", id="confirmation-1", args={
                "originalFunctionCall": {
                    "id": "call-1", "name": "versatile_thermostat__set_temperature", "args": arguments,
                },
                "toolConfirmation": {"hint": "Vérifiez les paramètres.", "payload": payload},
            },
        )),
    ]))

    assert response.accept(event) == ""
    assert response.confirmation == {
        "confirmation_id": "confirmation-1", "function_call_id": "call-1",
        "operation": "versatile_thermostat__set_temperature", "arguments": arguments,
        "hint": "Vérifiez les paramètres.", "expires_at": 2000000000, "payload": payload,
        "tool_confirmation": {"hint": "Vérifiez les paramètres.", "payload": payload},
    }


def test_response_stream_rejects_mismatched_confirmation_arguments() -> None:
    response = ConversationResponse("vtherm_assistant", [])
    event = Event(author="vtherm_assistant", content=types.Content(role="model", parts=[
        types.Part(function_call=types.FunctionCall(
            name="adk_request_confirmation", id="confirmation-1", args={
                "originalFunctionCall": {
                    "id": "call-1", "name": "versatile_thermostat__set_temperature",
                    "args": {"entity_id": "climate.salon", "temperature": 20},
                },
                "toolConfirmation": {"payload": {
                    "user_id": "alice", "tool_name": "versatile_thermostat__set_temperature",
                    "arguments": {"entity_id": "climate.salon", "temperature": 21},
                    "function_call_id": "call-1", "expires_at": 2000000000, "nonce": "n" * 32,
                }},
            },
        )),
    ]))

    with pytest.raises(IncompleteResponse, match="ne correspond pas"):
        response.accept(event)


@pytest.mark.parametrize("event", [
    Event(author="vtherm_assistant", error_code="failed", error_message="secret-key"),
    Event(author="vtherm_assistant", interrupted=True),
    Event(author="vtherm_assistant", finish_reason=types.FinishReason.MAX_TOKENS),
    Event(author="vtherm_assistant", content=types.Content(parts=[types.Part(text="Texte différent")])),
])
def test_response_stream_never_completes_failed_or_inconsistent_answer(event) -> None:
    response = ConversationResponse("vtherm_assistant", ["secret-key"])
    response.accept(Event(author="vtherm_assistant", partial=True,
                          content=types.Content(parts=[types.Part(text="Réponse partielle")])))
    with pytest.raises(IncompleteResponse, match="réessayez"):
        response.accept(event)
    with pytest.raises(IncompleteResponse):
        response.finish()


def test_response_stream_requires_a_final_event() -> None:
    response = ConversationResponse("vtherm_assistant", [])
    response.accept(Event(author="vtherm_assistant", partial=True,
                          content=types.Content(parts=[types.Part(text="Réponse partielle")])))
    with pytest.raises(IncompleteResponse):
        response.finish()


@pytest.mark.parametrize("provider_name", ["gemini", "openai", "anthropic", "ollama"])
@pytest.mark.parametrize("tool_count", [0, 1, 2])
@pytest.mark.parametrize("outcome", ["complete", "interrupted", "error"])
def test_conversation_runner_streaming_providers(tmp_path, provider_name, tool_count, outcome) -> None:
    from vtherm_assistant.models import ModelConfig

    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    application = create_app("standalone", oauth_config=config, data_dir=tmp_path / "private")
    if provider_name != "ollama":
        application.state.secrets.put("alice", provider_name, "secret-key")
    application.state.models.configure("alice", ModelConfig(
        provider_name, "model-test", "http://ollama:11434" if provider_name == "ollama" else None
    ))
    tool = Tool(name="versatile_thermostat__get_status", inputSchema={"type": "object"})
    result = CallToolResult(content=[TextContent(type="text", text="waiting")])

    async def stream(parts, *, final_step=False):
        for part in parts:
            if provider_name == "gemini":
                yield types.GenerateContentResponse(candidates=[types.Candidate(
                    content=types.Content(role="model", parts=[part])
                )])
            else:
                delta = Delta(content=part.text) if part.text else Delta(tool_calls=[{
                    "index": 0, "id": "call-test", "type": "function", "function": {
                        "name": part.function_call.name, "arguments": '{"entity_id":"climate.salon"}',
                    },
                }])
                yield ModelResponseStream(model="model-test", choices=[StreamingChoices(index=0, delta=delta)])
        if final_step and outcome == "error":
            raise RuntimeError("Provider failed with secret-key")
        if provider_name == "gemini":
            if final_step and outcome == "interrupted":
                yield types.GenerateContentResponse(candidates=[types.Candidate(finish_reason=types.FinishReason.MAX_TOKENS)])
        else:
            finish_reason = "length" if final_step and outcome == "interrupted" else "stop" if final_step else "tool_calls"
            yield ModelResponseStream(model="model-test", choices=[StreamingChoices(index=0, finish_reason=finish_reason)])

    streams = [stream([
        types.Part(text=f"Lecture {index + 1} secret-"),
        types.Part(text="key. "),
        types.Part(function_call=types.FunctionCall(name=tool.name, args={"entity_id": "climate.salon"})),
    ]) for index in range(tool_count)]
    streams.append(stream([types.Part(text="Le thermostat est en attente.")], final_step=True))

    async def run():
        return [event async for event in application.state.conversation_runner.respond("alice", "État du salon ?", ["secret-key"])]

    with patch.object(application.state.mcp, "list_tools", new_callable=AsyncMock, return_value=[tool]), \
         patch.object(application.state.mcp, "call_read_only_tool", new_callable=AsyncMock, return_value=result) as call_tool, \
         patch("google.genai.Client") as provider, \
         patch("google.adk.models.lite_llm.LiteLLMClient.acompletion", new_callable=AsyncMock) as completion:
        if provider_name == "gemini":
            provider.return_value.aio.models.generate_content_stream = AsyncMock(side_effect=streams)
        else:
            completion.side_effect = streams
        events = asyncio.run(run())

    expected = "".join(f"Lecture {index + 1} [masqué]. " for index in range(tool_count)) + "Le thermostat est en attente."
    assert call_tool.await_count == tool_count
    assert "secret-key" not in str(events)
    if provider_name != "gemini":
        assert all(call.kwargs["stream"] is True for call in completion.call_args_list)
    if outcome == "complete":
        assert events[-1] == {"type": "complete"}
        assert "".join(event.get("text", "") for event in events) == expected
        saved_messages = application.state.conversations.load("alice")[0]
        assert saved_messages[-1]["text"] == expected
        question_time = next(event["created_at"] for event in events if event["type"] == "timestamp" and event["role"] == "user")
        response_times = [event["created_at"] for event in events if event["type"] == "delta"]
        assert question_time.endswith("+00:00")
        assert response_times and len(set(response_times)) == 1
        assert saved_messages[-2]["created_at"] == question_time
        assert saved_messages[-1]["created_at"] == response_times[0]
    else:
        assert events[-1]["type"] == "error"
        assert not any(event["type"] == "complete" for event in events)
        assert application.state.conversations.load("alice") is None


@pytest.mark.parametrize(("confirmed", "tool_error", "interrupted"), [
    (True, False, False), (False, False, False), (True, True, False), (True, False, True),
], ids=["approved", "refused", "mcp-error", "interrupted"])
def test_conversation_confirmation_resume_executes_only_approved_write_once(
    tmp_path, confirmed, tool_error, interrupted,
) -> None:
    from vtherm_assistant.models import ModelConfig

    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    application = create_app("standalone", oauth_config=config, data_dir=tmp_path / "private")
    application.state.secrets.put("alice", "gemini", "fake-key")
    application.state.models.configure("alice", ModelConfig("gemini", "gemini-test"))
    description = Tool(
        name="versatile_thermostat__set_temperature",
        inputSchema={
            "type": "object",
            "properties": {"entity_id": {"type": "string"}, "temperature": {"type": "number"}},
            "required": ["entity_id", "temperature"], "additionalProperties": False,
        },
        annotations={"readOnlyHint": False, "destructiveHint": False},
    )
    arguments = {"entity_id": "climate.salon", "temperature": 20}
    tool = MCPTool(application.state.mcp, "alice", description)
    agent = application.state.models.agent_for("alice")
    agent.tools = [tool]

    async def for_user(_user_id, _additional_secrets=()):
        return agent

    runner = ConversationRunner(SimpleNamespace(for_user=for_user), application.state.conversations)
    session = AsyncMock()
    session.list_tools.return_value = ListToolsResult(tools=[description])
    session.call_tool.return_value = CallToolResult(
        isError=tool_error,
        content=[TextContent(type="text", text='{"status":"failed"}' if tool_error else '{"status":"accepted"}')],
    )

    @asynccontextmanager
    async def session_for(_user_id):
        yield session

    async def first_stream():
        yield types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[
            types.Part(function_call=types.FunctionCall(name=description.name, id="write-call", args=arguments)),
        ]))])

    async def final_stream():
        if interrupted:
            yield types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
                role="model", parts=[types.Part(text="La température a été modifiée.")],
            ))])
            yield types.GenerateContentResponse(candidates=[types.Candidate(finish_reason=types.FinishReason.MAX_TOKENS)])
            return
        text = (
            "Le serveur MCP a refusé la consigne ; la modification n'est pas confirmée."
            if tool_error else "Action transmise à VTherm." if confirmed else "Aucune écriture demandée."
        )
        yield types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[
            types.Part(text=text),
        ]))])

    async def run():
        requested = [event async for event in runner.respond("alice", "Règle le salon à 20 degrés", [])]
        confirmation = next(event for event in requested if event["type"] == "confirmation")
        pending = application.state.conversations.load("alice")[1]["pending_confirmation"]
        assert confirmation["confirmation_id"] == pending["confirmation_id"]
        assert pending["payload"]["arguments"] == arguments
        stored_events = application.state.conversations.load("alice")[1]["events"]
        assert any(event.get("actions", {}).get("requested_tool_confirmations") for event in stored_events)
        resumed = [event async for event in runner.confirm("alice", confirmation["confirmation_id"], confirmed, [])]
        replay = [event async for event in runner.confirm("alice", confirmation["confirmation_id"], confirmed, [])]
        return requested, resumed, replay

    with patch.object(application.state.mcp, "_session", side_effect=session_for), \
         patch.object(application.state.mcp, "inventory_for", new_callable=AsyncMock,
                      return_value={"thermostats": [{"entity_id": "climate.salon"}]}), \
         patch("google.genai.Client") as provider:
        provider.return_value.aio.models.generate_content_stream = AsyncMock(side_effect=[first_stream(), final_stream()])
        requested, resumed, replay = asyncio.run(run())

    assert requested[-1]["type"] == "confirmation"
    assert resumed[-1]["type"] == ("error" if interrupted else "complete")
    assert replay[-1]["type"] == "error"
    assert session.call_tool.await_count == int(confirmed)
    if interrupted:
        assert not any(event["type"] == "delta" for event in resumed)
        assert all("modifiée" not in event.get("text", "") for event in resumed)
    stored = application.state.conversations.load("alice")
    assert stored[1]["pending_confirmation"] is None
    if confirmed and not interrupted:
        responses = [
            part["function_response"]["response"]
            for event in stored[1]["events"]
            for part in event.get("content", {}).get("parts", [])
            if part.get("function_response", {}).get("name") == description.name
        ]
        assert responses[-1].get("isError", False) is tool_error
    if confirmed and not tool_error and not interrupted:
        assert stored[0][-1]["text"] == "Action transmise à VTherm."
    elif not confirmed:
        assert stored[0][-1]["text"] == "Aucune écriture demandée."


def test_conversation_confirmation_rejects_reuse_tampering_expiry_and_concurrency(tmp_path) -> None:
    store = ConversationStore(PrivateDatabase(tmp_path / "private"))
    arguments = {"entity_id": "climate.salon", "temperature": 20}
    payload = {
        "user_id": "alice", "tool_name": "versatile_thermostat__set_temperature",
        "arguments": arguments, "function_call_id": "function-1",
        "expires_at": 2000000000, "nonce": "n" * 32,
    }
    pending = {
        "confirmation_id": "confirmation-1", "function_call_id": "function-1",
        "operation": "versatile_thermostat__set_temperature", "arguments": arguments,
        "hint": "Vérifiez les paramètres.", "expires_at": payload["expires_at"],
        "payload": payload, "tool_confirmation": {"hint": "Vérifiez les paramètres.", "payload": payload},
        "user_id": "alice", "conversation_id": "conversation-1",
    }
    context = {"events": [], "conversation_id": "conversation-1", "pending_confirmation": pending}
    store.save("alice", [{"role": "user", "text": "Règle le salon."}], context)

    async def unused_agent(*_args):
        raise AssertionError("Le modèle ne doit pas être appelé pour une confirmation rejetée.")

    runner = ConversationRunner(SimpleNamespace(for_user=unused_agent), store)
    wrong_user = asyncio.run(anext(runner.confirm("bob", "confirmation-1", True, [])))
    assert wrong_user["type"] == "error"

    tampered = {**pending, "payload": {**payload, "arguments": {**arguments, "temperature": 21}}}
    store.save("alice", [{"role": "user", "text": "Règle le salon."}], {
        **context, "pending_confirmation": tampered,
    })
    tampered_result = asyncio.run(anext(runner.confirm("alice", "confirmation-1", True, [])))
    assert tampered_result["type"] == "error"

    expired = {**pending, "expires_at": 1, "payload": {**payload, "expires_at": 1}}
    expired["tool_confirmation"] = {"hint": "Vérifiez les paramètres.", "payload": expired["payload"]}
    store.save("alice", [{"role": "user", "text": "Règle le salon."}], {
        **context, "pending_confirmation": expired,
    })
    async def confirm_expired():
        return [event async for event in runner.confirm("alice", "confirmation-1", True, [])]

    expired_result = asyncio.run(confirm_expired())
    assert expired_result[-1]["type"] == "error"
    assert store.load("alice")[1]["pending_confirmation"] is None

    runner.running.add("alice")
    concurrent = asyncio.run(anext(runner.confirm("alice", "confirmation-1", True, [])))
    runner.running.remove("alice")
    assert concurrent == {"type": "error", "message": "Une réponse est déjà en cours."}


def test_conversation_runner_streams_and_restores_redacted_history(tmp_path) -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    application = create_app("standalone", oauth_config=config, data_dir=tmp_path / "private")
    application.state.secrets.put("alice", "gemini", "secret-key")
    application.state.secrets.put("bob", "gemini", "bob-key")
    from vtherm_assistant.models import ModelConfig

    application.state.models.configure("alice", ModelConfig("gemini", "gemini-test"))
    application.state.models.configure("bob", ModelConfig("gemini", "gemini-test"))
    application.state.conversations.save("bob", [{"role": "user", "text": "État du bureau ?"},
                                                  {"role": "assistant", "text": "Le bureau est en chauffe."}], {})
    conversation = ConversationRunner(application.state.conversation_agent, application.state.conversations)
    restarted = create_app("standalone", oauth_config=config, data_dir=tmp_path / "private")
    resumed = ConversationRunner(restarted.state.conversation_agent, restarted.state.conversations)

    async def stream(parts):
        for text in parts:
            yield types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text=text)]))])

    async def run():
        first = [event async for event in conversation.respond("alice", "État secret-key ?", ["secret-key"])]
        second = [event async for event in resumed.respond("alice", "Et maintenant ?", ["secret-key"])]
        third = [event async for event in resumed.respond("bob", "Et le bureau ?", ["bob-key"])]
        return first, second, third

    with patch.object(application.state.mcp, "tools_for", new_callable=AsyncMock, return_value=[]), \
            patch.object(restarted.state.mcp, "tools_for", new_callable=AsyncMock, return_value=[]), \
         patch("google.genai.Client") as provider:
        generate = AsyncMock(side_effect=[stream(["Bonjour secret-", "key !"]), stream(["Toujours en attente."]), stream(["Il chauffe."])])
        provider.return_value.aio.models.generate_content_stream = generate
        first, second, third = asyncio.run(run())
    assert first[-1] == {"type": "complete"}
    assert "".join(event.get("text", "") for event in first) == "Bonjour [masqué] !"
    assert second[-1] == {"type": "complete"}
    history = str(generate.call_args_list[1].kwargs["contents"])
    assert "État [masqué] ?" in history
    assert "Bonjour [masqué] !" in history
    assert "secret-key" not in history
    assert application.state.conversations.load("alice")[0][-1]["text"] == "Toujours en attente."
    assert third[-1] == {"type": "complete"}
    bob_history = str(generate.call_args_list[2].kwargs["contents"])
    assert "Le bureau est en chauffe." in bob_history
    assert "Bonjour" not in bob_history
    assert "bureau" not in history


def test_conversation_runner_restores_tool_evidence_after_restart_and_isolates_users(tmp_path) -> None:
    from vtherm_assistant.models import ModelConfig

    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    directory = tmp_path / "private"
    application = create_app("standalone", oauth_config=config, data_dir=directory)
    for user_id in ("alice", "bob"):
        application.state.secrets.put(user_id, "gemini", f"{user_id}-secret")
        application.state.models.configure(user_id, ModelConfig("gemini", "gemini-test"))
    tool = Tool(name="versatile_thermostat__get_status", inputSchema={"type": "object"})

    async def stream(part):
        yield types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[part]))])

    async def read_tool(user_id, _name, _arguments):
        return CallToolResult(content=[TextContent(type="text", text=json.dumps({
            "entity_id": "climate.salon", "state": "heat",
            "attributes": {"specific_states": {"messages": [f"tool-evidence-{user_id} {user_id}-secret"]}},
        }))])

    async def run():
        for user_id in ("alice", "bob"):
            events = [event async for event in application.state.conversation_runner.respond(user_id, "Diagnostic ?", [f"{user_id}-secret"])]
            assert events[-1] == {"type": "complete"}
        restarted = create_app("standalone", oauth_config=config, data_dir=directory)
        for user_id in ("alice", "bob"):
            events = [event async for event in restarted.state.conversation_runner.respond(user_id, "Pourquoi ?", [f"{user_id}-secret"])]
            assert events[-1] == {"type": "complete"}
        restarted.state.conversations.delete("alice")
        events = [event async for event in restarted.state.conversation_runner.respond("alice", "Pourquoi ?", ["alice-secret"])]
        assert events[-1] == {"type": "complete"}
        return restarted

    streams = []
    for _user_id in ("alice", "bob"):
        streams.extend([
            stream(types.Part(function_call=types.FunctionCall(name=tool.name, args={"entity_id": "climate.salon"}))),
            stream(types.Part(text="Le thermostat est inhibé.")),
        ])
    streams.extend(stream(types.Part(text="Vérifions la cause.")) for _index in range(3))
    with patch("vtherm_assistant.ha_mcp.HomeAssistantMCP.list_tools", new_callable=AsyncMock, return_value=[tool]), \
         patch("vtherm_assistant.ha_mcp.HomeAssistantMCP.call_read_only_tool", new_callable=AsyncMock, side_effect=read_tool), \
         patch("google.genai.Client") as provider:
        generate = AsyncMock(side_effect=streams)
        provider.return_value.aio.models.generate_content_stream = generate
        restarted = asyncio.run(run())
    def request_history(index):
        return json.dumps([content.model_dump(mode="json") for content in generate.call_args_list[index].kwargs["contents"]])

    alice_history = request_history(4)
    bob_history = request_history(5)
    new_history = request_history(6)
    assert "tool-evidence-alice" in alice_history
    assert "tool-evidence-bob" not in alice_history
    assert "tool-evidence-bob" in bob_history
    assert "tool-evidence-alice" not in bob_history
    assert "tool-evidence-" not in new_history
    assert "alice-secret" not in alice_history
    assert "bob-secret" not in bob_history
    assert "tool-evidence-alice" not in str(restarted.state.conversations.load("alice"))


@pytest.mark.parametrize("outcome", ["failure", "delete"])
def test_conversation_runner_does_not_save_interrupted_or_deleted_answer(tmp_path, outcome) -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    application = create_app("standalone", oauth_config=config, data_dir=tmp_path / "private")
    application.state.secrets.put("alice", "gemini", "secret-key")
    from vtherm_assistant.models import ModelConfig

    application.state.models.configure("alice", ModelConfig("gemini", "gemini-test"))
    conversation = ConversationRunner(application.state.conversation_agent, application.state.conversations)

    async def stream():
        yield types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text="Début ")]))])
        if outcome == "failure":
            raise RuntimeError("secret-key")
        application.state.conversations.delete("alice")
        yield types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text="fin")]))])

    async def run():
        running = conversation.respond("alice", "Question", ["secret-key"])
        first = await anext(running)
        concurrent = [event async for event in conversation.respond("alice", "Autre question", ["secret-key"])]
        return [first] + [event async for event in running], concurrent

    with patch.object(application.state.mcp, "tools_for", new_callable=AsyncMock, return_value=[]), \
         patch("google.genai.Client") as provider:
        provider.return_value.aio.models.generate_content_stream = AsyncMock(return_value=stream())
        events, concurrent = asyncio.run(run())
    assert events[0]["type"] == "timestamp"
    assert next(event["text"] for event in events if event["type"] == "delta") == "Début "
    assert events[-1]["type"] == "error"
    assert "secret-key" not in str(events)
    assert concurrent == [{"type": "error", "message": "Une réponse est déjà en cours."}]
    assert application.state.conversations.load("alice") is None


@pytest.mark.parametrize("sent_at", ["2026-10-25T02:59:00+02:00", "2026-10-25T02:59:00", "invalide", 42])
def test_conversation_route_validates_and_preserves_question_timestamp(tmp_path, monkeypatch, sent_at) -> None:
    from vtherm_assistant.models import ModelConfig

    monkeypatch.setenv("VTHERM_HA_INTERNAL_URL", "http://homeassistant:8123")
    async def verify_admin(user_id):
        return user_id == "alice"
    application = create_app("ingress", verify_admin=verify_admin, data_dir=tmp_path / "private")
    application.state.models.configure("alice", ModelConfig("gemini", "model-test"))
    application.state.secrets.put("alice", "gemini", "fake-key")
    async def stream():
        yield types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text="Réponse.")]))])
    with TestClient(application, client=(SUPERVISOR_ADDRESS, 12345)) as client, \
         patch.object(application.state.mcp, "tools_for", new_callable=AsyncMock, return_value=[]), \
         patch("google.genai.Client") as provider:
        provider.return_value.aio.models.generate_content_stream = AsyncMock(return_value=stream())
        response = client.post("/api/conversation", json={"question": "Question", "created_at": sent_at},
                               headers={"X-Remote-User-Id": "alice", "X-VTherm-Request": "1"})
    if sent_at == "2026-10-25T02:59:00+02:00":
        assert response.status_code == 200
        assert application.state.conversations.load("alice")[0][0]["created_at"] == "2026-10-25T00:59:00+00:00"
    else:
        assert response.status_code == 400
        assert application.state.conversations.load("alice") is None


def test_conversation_route_streams_for_verified_user_and_masks_session_tokens(tmp_path) -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    application = create_app("standalone", oauth_config=config, data_dir=tmp_path / "private")
    application.state.secrets.put("alice", "gemini", "secret-key")
    from vtherm_assistant.models import ModelConfig

    application.state.models.configure("alice", ModelConfig("gemini", "gemini-test"))
    application.state.oauth.sessions["session-secret"] = Session("alice", OAuthTokens("access-token", "refresh-token", 1800), float("inf"), float("inf"))

    async def stream():
        yield types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text="access-")]))])
        yield types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text="token et secret-key")]))])

    with TestClient(application, base_url=config.app_url) as client, \
         patch("vtherm_assistant.oauth_flow.current_admin", new_callable=AsyncMock, return_value="alice"), \
         patch.object(application.state.mcp, "tools_for", new_callable=AsyncMock, return_value=[]), \
         patch("google.genai.Client") as provider:
        provider.return_value.aio.models.generate_content_stream = AsyncMock(return_value=stream())
        assert client.post("/api/conversation", json={"question": "Question"}, headers={"Origin": config.app_url.rstrip("/")}).status_code == 403
        client.cookies.set(SESSION_COOKIE, "session-secret")
        assert client.post("/api/conversation", json={"question": "Question"}, headers={"Origin": "https://attacker.example"}).status_code == 403
        assert client.post("/api/conversation", json={"question": " "}, headers={"Origin": config.app_url.rstrip("/")}).status_code == 400
        response = client.post("/api/conversation?user_id=bob", json={"question": "Question"}, headers={"Origin": config.app_url.rstrip("/")})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert "access-token" not in response.text
        assert "secret-key" not in response.text
        assert '"type": "complete"' in response.text
        assert client.get("/api/conversation").json()["messages"][-1]["text"] == "[masqué] et [masqué]"
    assert application.state.conversations.load("bob") is None


@pytest.mark.parametrize("provider_name, model_name", [
    ("gemini", "model-test"), ("openai", "model-test"),
    ("anthropic", "model-test"), ("ollama", "model-test"), ("openai", "gpt-6-luna"),
])
def test_ingress_route_emits_first_fragment_before_producer_finishes(tmp_path, monkeypatch, provider_name, model_name) -> None:
    monkeypatch.setenv("VTHERM_HA_INTERNAL_URL", "http://homeassistant:8123")

    async def verify_admin(user_id):
        return user_id == "alice"

    application = create_app("ingress", verify_admin=verify_admin, data_dir=tmp_path / "private")
    from vtherm_assistant.models import ModelConfig

    if provider_name != "ollama":
        application.state.secrets.put("alice", provider_name, "fake-provider-key")
    application.state.models.configure("alice", ModelConfig(
        provider_name, model_name, "http://ollama:11434" if provider_name == "ollama" else None
    ))

    async def check_progress():
        release = asyncio.Event()
        sent = asyncio.Queue()
        received_request = False

        async def provider_stream():
            for index, text in enumerate(("Premier fragment.", " Suite.")):
                if index:
                    await release.wait()
                if provider_name == "gemini":
                    yield types.GenerateContentResponse(candidates=[types.Candidate(
                        content=types.Content(role="model", parts=[types.Part(text=text)])
                    )])
                else:
                    yield ModelResponseStream(model=model_name, choices=[StreamingChoices(
                        index=0, delta=Delta(content=text)
                    )])
            if provider_name != "gemini":
                yield ModelResponseStream(model=model_name, choices=[StreamingChoices(index=0, finish_reason="stop")])

        async def receive():
            nonlocal received_request
            if not received_request:
                received_request = True
                return {"type": "http.request", "body": b'{"question":"Test"}', "more_body": False}
            await asyncio.Event().wait()

        scope = {
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1", "method": "POST", "scheme": "http",
            "path": "/api/conversation", "raw_path": b"/api/conversation", "query_string": b"",
            "root_path": "", "server": ("vtherm.test", 8099), "client": (SUPERVISOR_ADDRESS, 12345),
            "headers": [(b"host", b"vtherm.test"), (b"content-type", b"application/json"),
                        (b"x-remote-user-id", b"alice"), (b"x-vtherm-request", b"1")],
        }
        with patch.object(application.state.mcp, "tools_for", new_callable=AsyncMock, return_value=[]), \
             patch("google.genai.Client") as provider, \
             patch("google.adk.models.lite_llm.LiteLLMClient.acompletion", new_callable=AsyncMock) as completion:
            if provider_name == "gemini":
                provider.return_value.aio.models.generate_content_stream = AsyncMock(return_value=provider_stream())
            else:
                completion.return_value = provider_stream()
            request_task = asyncio.create_task(application(scope, receive, sent.put))
            try:
                async with asyncio.timeout(5):
                    start = await sent.get()
                    assert start["type"] == "http.response.start"
                    assert start["status"] == 200
                    assert dict(start["headers"])[b"x-accel-buffering"] == b"no"
                    timestamp = await sent.get()
                    assert json.loads(timestamp["body"])["type"] == "timestamp"
                    first = await sent.get()
                    assert first["type"] == "http.response.body"
                    assert first["more_body"] is True
                    fragment = json.loads(first["body"])
                    assert fragment["type"] == "delta" and fragment["text"] == "Premier fragment."
                    assert fragment["created_at"].endswith("+00:00")
                    assert not request_task.done()
                    release.set()
                    await request_task
                remaining = []
                while not sent.empty():
                    remaining.append(sent.get_nowait())
                assert any(b'"type": "complete"' in message.get("body", b"") for message in remaining)
                assert application.state.conversations.load("alice")[0][-1]["text"] == "Premier fragment. Suite."
                if provider_name != "gemini":
                    assert completion.call_args.kwargs["stream"] is True
                if provider_name == "openai" and model_name == "gpt-6-luna":
                    assert completion.call_args.kwargs["model"] == "openai/gpt-6-luna"
                    assert completion.call_args.kwargs["reasoning_effort"] == "none"
            finally:
                release.set()
                if not request_task.done():
                    request_task.cancel()
                await asyncio.gather(request_task, return_exceptions=True)

    asyncio.run(check_progress())


@pytest.mark.parametrize("provider_name", ["gemini", "ollama"])
def test_conversation_route_reports_provider_failure_without_exposing_credentials(tmp_path, monkeypatch, provider_name) -> None:
    monkeypatch.setenv("VTHERM_HA_INTERNAL_URL", "http://homeassistant:8123")
    async def verify_admin(user_id: str) -> bool:
        return user_id == "alice"

    application = create_app("ingress", verify_admin=verify_admin, data_dir=tmp_path / "private")
    from vtherm_assistant.models import ModelConfig

    application.state.secrets.put("alice", "gemini", "invalid-key")
    application.state.models.configure("alice", ModelConfig(provider_name, "model-test", "http://ollama:11434" if provider_name == "ollama" else None))
    headers = {"X-Remote-User-Id": "alice", "X-VTherm-Request": "1"}
    with TestClient(application, client=(SUPERVISOR_ADDRESS, 12345)) as client, \
         patch.object(application.state.mcp, "tools_for", new_callable=AsyncMock, return_value=[]), \
         patch("google.genai.Client") as gemini, \
         patch("google.adk.models.lite_llm.LiteLLMClient.acompletion", new_callable=AsyncMock, side_effect=RuntimeError("server unavailable invalid-key")):
        gemini.return_value.aio.models.generate_content_stream = AsyncMock(side_effect=RuntimeError("invalid key invalid-key"))
        response = client.post("/api/conversation", headers=headers, json={"question": "Pourquoi ?"})
        assert response.status_code == 200
        assert '"type": "error"' in response.text
        assert "réessayez" in response.text
        assert "invalid-key" not in response.text
        assert "invalid-key" not in client.get("/api/model", headers=headers).text
        assert client.get("/api/secrets/gemini", headers=headers).status_code == 405
    assert application.state.conversations.load("alice") is None


@pytest.mark.parametrize("failure_stage", ["mcp", "provider"])
def test_conversation_runner_can_retry_without_saving_a_failed_exchange(tmp_path, failure_stage, caplog) -> None:
    from vtherm_assistant.ha_mcp import MCPConnectionError
    from vtherm_assistant.models import ModelConfig

    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    application = create_app("standalone", oauth_config=config, data_dir=tmp_path / "private")
    application.state.secrets.put("alice", "gemini", "secret-key")
    application.state.models.configure("alice", ModelConfig("gemini", "gemini-test"))
    original = [{"role": "user", "text": "État précédent ?"}, {"role": "assistant", "text": "En attente."}]
    application.state.conversations.save("alice", original, {})

    async def stream():
        yield types.GenerateContentResponse(candidates=[types.Candidate(
            content=types.Content(role="model", parts=[types.Part(text="Toujours en attente.")])
        )])

    async def run():
        failed = [event async for event in application.state.conversation_runner.respond("alice", "Question", ["secret-key"])]
        assert application.state.conversations.load("alice")[0] == original
        retried = [event async for event in application.state.conversation_runner.respond("alice", "Question", ["secret-key"])]
        return failed, retried

    tool_results = [MCPConnectionError("MCP secret-key"), []] if failure_stage == "mcp" else [[], []]
    provider_results = [RuntimeError("Provider secret-key"), stream()] if failure_stage == "provider" else [stream()]
    with patch.object(application.state.mcp, "tools_for", new_callable=AsyncMock, side_effect=tool_results), \
         patch("google.genai.Client") as provider:
        provider.return_value.aio.models.generate_content_stream = AsyncMock(side_effect=provider_results)
        failed, retried = asyncio.run(run())
    assert failed[-1]["type"] == "error"
    assert "réessayez" in failed[-1]["message"]
    assert "secret-key" not in str(failed)
    assert not any(event["type"] in {"complete", "delta"} for event in failed)
    assert retried[-1] == {"type": "complete"}
    assert len(application.state.conversations.load("alice")[0]) == len(original) + 2
    expected_stage = "prepare_agent" if failure_stage == "mcp" else "stream"
    assert f"operation=conversation.respond stage={expected_stage}" in caplog.text
    assert "secret-key" not in caplog.text


def test_conversations_persist_and_are_isolated_by_user(tmp_path) -> None:
    directory = tmp_path / "private"
    store = ConversationStore(PrivateDatabase(directory))
    store.save("alice", [{"role": "user", "text": "Chauffage"}], {"thermostat": "salon"})
    store.save("bob", [{"role": "user", "text": "Température"}], {"thermostat": "bureau"})

    restarted = ConversationStore(PrivateDatabase(directory))
    assert restarted.load("alice") == ([{"role": "user", "text": "Chauffage"}], {"thermostat": "salon"})
    assert restarted.load("bob") == ([{"role": "user", "text": "Température"}], {"thermostat": "bureau"})
    assert restarted.load("unknown") is None
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE((directory / "conversations.sqlite3").stat().st_mode) == 0o600


def test_store_rejects_missing_identity_and_unprotected_directory(tmp_path) -> None:
    store = ConversationStore(PrivateDatabase(tmp_path / "private"))
    with pytest.raises(ValueError):
        store.load("")
    with pytest.raises(ValueError):
        store.save("", [], {})
    directory = tmp_path / "public"
    directory.mkdir(mode=0o755)
    os.chmod(directory, 0o755)
    with pytest.raises(PermissionError):
        ConversationStore(PrivateDatabase(directory)).load("alice")


def test_conversation_route_uses_verified_identity_after_restart(tmp_path) -> None:
    async def verify_admin(user_id: str) -> bool:
        return user_id in {"alice", "bob"}

    directory = tmp_path / "private"
    first_app = create_app("ingress", verify_admin=verify_admin, data_dir=directory)
    first_app.state.conversations.save("alice", [{"text": "Alice"}], {"thermostat": "salon"})
    first_app.state.conversations.save("bob", [{"text": "Bob"}], {"thermostat": "bureau"})
    restarted = create_app("ingress", verify_admin=verify_admin, data_dir=directory)
    with TestClient(restarted, client=(SUPERVISOR_ADDRESS, 12345)) as client:
        response = client.get("/api/conversation?user_id=bob", headers={"X-Remote-User-Id": "alice"})
        assert response.json() == {
            "messages": [{"text": "Alice"}], "inventory": None,
            "pending_confirmation": None, "version": 1,
        }
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/api/conversation", headers={"X-Remote-User-Id": "bob"}).json() == {
            "messages": [{"text": "Bob"}], "inventory": None,
            "pending_confirmation": None, "version": 1,
        }
        assert client.get("/api/conversation", headers={"X-Remote-User-Id": "other"}).status_code == 403
        assert client.delete("/api/conversation", headers={"X-Remote-User-Id": "alice"}).status_code == 403
        assert client.delete("/api/conversation?user_id=bob", headers={"X-Remote-User-Id": "alice", "X-VTherm-Request": "1"}).status_code == 204
        assert client.get("/api/conversation", headers={"X-Remote-User-Id": "alice"}).json() == {
            "messages": [], "inventory": None, "pending_confirmation": None, "version": 2,
        }
        assert client.get("/api/conversation", headers={"X-Remote-User-Id": "bob"}).json() == {
            "messages": [{"text": "Bob"}], "inventory": None,
            "pending_confirmation": None, "version": 1,
        }
    assert restarted.state.conversations.load("alice") is None
    assert restarted.state.conversations.load("bob")[1] == {"thermostat": "bureau"}


def test_confirmation_route_exposes_only_review_fields_and_requires_exact_payload(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VTHERM_HA_INTERNAL_URL", "http://homeassistant:8123")

    async def verify_admin(user_id: str) -> bool:
        return user_id in {"alice", "bob"}

    application = create_app("ingress", verify_admin=verify_admin, data_dir=tmp_path / "private")
    arguments = {"entity_id": "climate.salon", "temperature": 20}
    payload = {
        "user_id": "alice", "tool_name": "versatile_thermostat__set_temperature",
        "arguments": arguments, "function_call_id": "function-1",
        "expires_at": 2000000000, "nonce": "n" * 32,
    }
    pending = {
        "confirmation_id": "confirmation-1", "function_call_id": "function-1",
        "operation": "versatile_thermostat__set_temperature", "arguments": arguments,
        "hint": "Vérifiez les paramètres.", "expires_at": payload["expires_at"],
        "payload": payload, "tool_confirmation": {"hint": "Vérifiez les paramètres.", "payload": payload},
        "user_id": "alice", "conversation_id": "private-conversation-id",
    }
    application.state.conversations.save("alice", [{"role": "user", "text": "Régle le salon."}], {
        "events": [], "conversation_id": "private-conversation-id", "pending_confirmation": pending,
    })
    calls = []

    async def confirm(*args):
        calls.append(args)
        yield {"type": "complete"}

    headers = {"X-Remote-User-Id": "alice", "X-VTherm-Request": "1"}
    with TestClient(application, client=(SUPERVISOR_ADDRESS, 12345)) as client, \
         patch.object(application.state.conversation_runner, "confirm", new=confirm):
        alice_state = client.get("/api/conversation", headers=headers).json()
        assert alice_state["pending_confirmation"] == {
            "confirmation_id": "confirmation-1",
            "operation": "versatile_thermostat__set_temperature",
            "target": "climate.salon", "arguments": arguments,
            "hint": "Vérifiez les paramètres.", "expires_at": 2000000000,
        }
        bob_state = client.get("/api/conversation", headers={"X-Remote-User-Id": "bob"}).json()
        assert bob_state["pending_confirmation"] is None
        assert client.post("/api/conversation/confirm", headers=headers, json={
            "confirmation_id": "confirmation-1", "confirmed": True, "arguments": arguments,
        }).status_code == 400
        response = client.post("/api/conversation/confirm", headers=headers, json={
            "confirmation_id": "confirmation-1", "confirmed": True,
        })

    assert response.status_code == 200
    assert '"type": "complete"' in response.text
    assert calls == [("alice", "confirmation-1", True, [])]
    assert "private-conversation-id" not in response.text
    assert "n" * 32 not in response.text


def test_new_conversation_removes_only_the_current_users_messages_and_context(tmp_path) -> None:
    directory = tmp_path / "private"
    store = ConversationStore(PrivateDatabase(directory))
    store.save("alice", [{"text": "Ancienne question"}], {"thermostat": "salon"})
    store.save("bob", [{"text": "Autre question"}], {"thermostat": "bureau"})
    store.delete("alice")

    restarted = ConversationStore(PrivateDatabase(directory))
    assert restarted.load("alice") is None
    assert restarted.load("bob") == ([{"text": "Autre question"}], {"thermostat": "bureau"})
    restarted.save("alice", [{"text": "Nouvelle question"}], {})
    assert restarted.load("alice") == ([{"text": "Nouvelle question"}], {})
    with pytest.raises(ValueError):
        restarted.delete("")


def test_stale_response_cannot_restore_deleted_or_overwritten_conversation(tmp_path) -> None:
    store = ConversationStore(PrivateDatabase(tmp_path / "private"))
    other_store = ConversationStore(PrivateDatabase(tmp_path / "private"))
    old, version = store.snapshot("alice")
    assert old is None
    other_store.delete("alice")
    assert not store.save_if_version("alice", version, [{"text": "Ancienne réponse"}], {})
    assert store.load("alice") is None
    _, version = store.snapshot("alice")
    assert store.save_if_version("alice", version, [{"text": "Nouvelle réponse"}], {})
    assert not other_store.save_if_version("alice", version, [{"text": "Réponse concurrente"}], {})
    assert store.load("alice") == ([{"text": "Nouvelle réponse"}], {})


def test_conversation_agent_uses_only_users_read_tools_and_requests_clarification(tmp_path) -> None:
    async def verify_admin(user_id: str) -> bool:
        return user_id == "alice"

    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    application = create_app("standalone", verify_admin=verify_admin, oauth_config=config, data_dir=tmp_path / "private")
    application.state.secrets.put("alice", "gemini", "alice-key")
    from vtherm_assistant.models import ModelConfig

    application.state.models.configure("alice", ModelConfig("gemini", "gemini-test"))
    safe_tool = BaseTool(name="versatile_thermostat__list_vtherms", description="Lecture")
    with patch.object(application.state.mcp, "tools_for", new_callable=AsyncMock, return_value=[safe_tool]) as tools_for:
        agent = asyncio.run(application.state.conversation_agent.for_user("alice"))
    tools_for.assert_awaited_once_with("alice", ())
    assert agent.tools[0] is safe_tool
    assert isinstance(agent.tools[1], VersatileThermostatDocumentationTool)
    assert "plusieurs thermostats ou intentions" in agent.instruction
    assert "demande une précision" in agent.instruction
    assert "Avant toute lecture ciblée" in agent.instruction
    assert "GetLiveContext sans filtre reste un contexte global" in agent.instruction
    assert "ne lis que les sources supplémentaires pertinentes" in agent.instruction
    assert "Attribue chaque observation à sa source et à son horodatage ou sa période" in agent.instruction
    assert "Si les sources se contredisent, expose les observations discordantes" in agent.instruction
    assert "un résultat vide valide" in agent.instruction
    assert "données incomplètes ou tronquées" in agent.instruction
    assert "accès refusé" in agent.instruction
    assert "outil absent ou indisponible" in agent.instruction
    assert "ne prouve pas l'absence d'un événement ou d'une configuration" in agent.instruction
    assert "recherche de panne ou d'incident" in agent.instruction
    assert "indique la source" in agent.instruction
    assert "demande un accord explicite sur sa cible et tous ses paramètres" in agent.instruction
    assert "N'utilise jamais d'outil générique d'écriture Home Assistant" in agent.instruction


@pytest.mark.parametrize("question,clarification", [
    ("Pourquoi le salon ne chauffe pas ?", "Quel thermostat du salon souhaitez-vous examiner ?"),
    ("Que faire pour le salon ?", "Souhaitez-vous un diagnostic ou des conseils de réglage ?"),
])
def test_conversation_agent_requests_clarification_after_tool_data(tmp_path, question, clarification) -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    application = create_app("standalone", oauth_config=config, data_dir=tmp_path / "private")
    application.state.secrets.put("alice", "gemini", "alice-key")
    from vtherm_assistant.models import ModelConfig

    application.state.models.configure("alice", ModelConfig("gemini", "gemini-test"))
    tool = Tool(name="versatile_thermostat__list_vtherms", inputSchema={"type": "object"})
    tool_result = CallToolResult(content=[TextContent(type="text", text='{"thermostats":["salon_1","salon_2"]}')])
    responses = [
        types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[
            types.Part(function_call=types.FunctionCall(name=tool.name, args={}))
        ]))]),
        types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[
            types.Part(text=clarification)
        ]))]),
    ]

    async def run_agent():
        agent = await application.state.conversation_agent.for_user("alice")
        sessions = InMemorySessionService()
        await sessions.create_session(app_name="vtherm", user_id="alice", session_id="session")
        runner = Runner(app_name="vtherm", agent=agent, session_service=sessions)
        return [event async for event in runner.run_async(
            user_id="alice", session_id="session",
            new_message=types.Content(role="user", parts=[types.Part(text=question)]),
        )]

    with patch.object(application.state.mcp, "list_tools", new_callable=AsyncMock, return_value=[tool]), \
         patch.object(application.state.mcp, "call_read_only_tool", new_callable=AsyncMock, return_value=tool_result) as call_tool, \
         patch("google.genai.Client") as provider:
        generate_content = AsyncMock(side_effect=responses)
        provider.return_value.aio.models.generate_content = generate_content
        events = asyncio.run(run_agent())
    call_tool.assert_awaited_once_with("alice", tool.name, {})
    assert events[-1].content.parts[0].text == clarification
    assert "demande une précision" in generate_content.call_args_list[0].kwargs["config"].system_instruction


def test_standalone_new_conversation_requires_admin_and_same_origin(tmp_path) -> None:
    config = OAuthConfig("https://assistant.example", "https://ha.example", "http://homeassistant:8123")
    application = create_app("standalone", oauth_config=config, data_dir=tmp_path / "private")
    application.state.conversations.save("alice", [{"text": "Question"}], {"thermostat": "salon"})
    with TestClient(application, base_url=config.app_url) as client:
        assert client.delete("/api/conversation", headers={"Origin": config.app_url.rstrip("/")}).status_code == 403
        application.state.oauth.sessions["session"] = Session("alice", OAuthTokens("access", "refresh", 1800), float("inf"), float("inf"))
        client.cookies.set(SESSION_COOKIE, "session")
        with patch("vtherm_assistant.oauth_flow.current_admin", new_callable=AsyncMock, return_value="alice"):
            assert client.delete("/api/conversation", headers={"Origin": "https://attacker.example"}).status_code == 403
            assert client.delete("/api/conversation", headers={"Origin": config.app_url.rstrip("/")}).status_code == 204
    assert application.state.conversations.load("alice") is None