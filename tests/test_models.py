import asyncio
import logging
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
import httpx
from openai import APIStatusError
from google.adk.models import Gemini
from google.adk.models import LlmRequest
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from litellm import ModelResponse
from fastapi.testclient import TestClient

from vtherm_assistant.main import SUPERVISOR_ADDRESS, create_app
from vtherm_assistant.models import ModelConfig, ModelRegistry
from vtherm_assistant.storage import ModelConfigStore, PrivateDatabase, SecretStore


async def generate_responses(model, request):
    return [response async for response in model.generate_content_async(request)]


def test_model_configuration_and_keys_are_isolated_by_user(tmp_path) -> None:
    database = PrivateDatabase(tmp_path / "private")
    secrets = SecretStore(database)
    registry = ModelRegistry(ModelConfigStore(database), secrets)
    secrets.put("alice", "gemini", "alice-key")
    secrets.put("bob", "openai", "bob-key")
    registry.configure("alice", ModelConfig("gemini", "gemini-test"))
    registry.configure("bob", ModelConfig("openai", "model-test"))

    alice = registry.agent_for("alice").model
    bob = registry.agent_for("bob").model
    assert isinstance(alice, Gemini)
    assert getattr(alice, "client_kwargs") == {"api_key": "alice-key", "vertexai": False}
    assert isinstance(bob, LiteLlm)
    assert getattr(bob, "model") == "openai/model-test"
    assert getattr(bob, "_additional_args")["api_key"] == "bob-key"
    assert "alice-key" not in repr(alice)
    assert "bob-key" not in repr(bob)
    with pytest.raises(ValueError):
        registry.agent_for("unknown")


def test_gemini_provider_error_does_not_expose_user_key(tmp_path, caplog) -> None:
    database = PrivateDatabase(tmp_path / "private")
    secrets = SecretStore(database)
    registry = ModelRegistry(ModelConfigStore(database), secrets)
    secrets.put("alice", "gemini", "alice-key")
    registry.configure("alice", ModelConfig("gemini", "gemini-test"))
    model = cast(Gemini, registry.agent_for("alice").model)
    assert isinstance(model, Gemini)

    with patch("google.genai.Client") as client:
        client.return_value.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("invalid key alice-key"))
        with pytest.raises(Exception) as error:
            asyncio.run(generate_responses(model, LlmRequest(model="gemini-test")))
        try:
            asyncio.run(generate_responses(model, LlmRequest(model="gemini-test")))
        except RuntimeError:
            logging.getLogger(__name__).exception("Erreur du fournisseur")
    assert "alice-key" not in str(error.value)
    assert "alice-key" not in caplog.text


def test_gemini_sdk_error_log_does_not_expose_user_key(tmp_path, caplog) -> None:
    database = PrivateDatabase(tmp_path / "private")
    secrets = SecretStore(database)
    registry = ModelRegistry(ModelConfigStore(database), secrets)
    secrets.put("alice", "gemini", "alice-key")
    registry.configure("alice", ModelConfig("gemini", "gemini-test"))
    model = cast(Gemini, registry.agent_for("alice").model)
    assert isinstance(model, Gemini)

    async def failing_request(**_kwargs):
        logging.getLogger("google_genai").error("Provider error: invalid key %s", "alice-key")
        raise RuntimeError("invalid key alice-key")

    with patch("google.genai.Client") as client:
        client.return_value.aio.models.generate_content = failing_request
        with pytest.raises(RuntimeError):
            asyncio.run(generate_responses(model, LlmRequest(model="gemini-test")))
    assert "alice-key" not in caplog.text


@pytest.mark.parametrize("part", [
    types.Part(text="Le thermostat est en attente."),
    types.Part(function_call=types.FunctionCall(name="read_state", args={"entity_id": "climate.salon"})),
])
def test_gemini_request_preserves_text_and_tool_calls(tmp_path, part) -> None:
    database = PrivateDatabase(tmp_path / "private")
    secrets = SecretStore(database)
    registry = ModelRegistry(ModelConfigStore(database), secrets)
    secrets.put("alice", "gemini", "alice-key")
    registry.configure("alice", ModelConfig("gemini", "gemini-test"))
    model = cast(Gemini, registry.agent_for("alice").model)
    assert isinstance(model, Gemini)
    request = LlmRequest(
        model="gemini-test",
        contents=[types.Content(role="user", parts=[types.Part(text="État du salon ?")])],
        config=types.GenerateContentConfig(tools=[types.Tool(function_declarations=[
            types.FunctionDeclaration(name="read_state", description="Lire un état")
        ])]),
    )
    provider_response = types.GenerateContentResponse(candidates=[
        types.Candidate(content=types.Content(role="model", parts=[part]))
    ])

    with patch("google.genai.Client") as client:
        generate_content = AsyncMock(return_value=provider_response)
        client.return_value.aio.models.generate_content = generate_content
        responses = asyncio.run(generate_responses(model, request))
    assert responses[0].content.parts[0] == part
    assert generate_content.call_args.kwargs["model"] == "gemini-test"
    assert generate_content.call_args.kwargs["config"].tools[0].function_declarations[0].name == "read_state"
    assert client.call_args.kwargs["api_key"] == "alice-key"


def test_gemini_agent_executes_tool_calls(tmp_path) -> None:
    database = PrivateDatabase(tmp_path / "private")
    secrets = SecretStore(database)
    registry = ModelRegistry(ModelConfigStore(database), secrets)
    secrets.put("alice", "gemini", "alice-key")
    registry.configure("alice", ModelConfig("gemini", "gemini-test"))
    agent = registry.agent_for("alice")
    observed = []

    def read_state(entity_id: str) -> str:
        observed.append(entity_id)
        return "waiting"

    agent.tools = [read_state]
    responses = [
        types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[
            types.Part(function_call=types.FunctionCall(name="read_state", args={"entity_id": "climate.salon"}))
        ]))]),
        types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[
            types.Part(text="Le thermostat est en attente.")
        ]))]),
    ]

    async def run_agent():
        sessions = InMemorySessionService()
        await sessions.create_session(app_name="vtherm", user_id="alice", session_id="session")
        runner = Runner(app_name="vtherm", agent=agent, session_service=sessions)
        return [event async for event in runner.run_async(
            user_id="alice", session_id="session",
            new_message=types.Content(role="user", parts=[types.Part(text="État du salon ?")]),
        )]

    with patch("google.genai.Client") as client:
        generate_content = AsyncMock(side_effect=responses)
        client.return_value.aio.models.generate_content = generate_content
        events = asyncio.run(run_agent())
    assert observed == ["climate.salon"]
    assert generate_content.await_count == 2
    assert events[-1].content.parts[0].text == "Le thermostat est en attente."


@pytest.mark.parametrize("provider, model_name, url, expected_model", [
    ("openai", "model-test", None, "openai/model-test"),
    ("anthropic", "model-test", None, "anthropic/model-test"),
    ("ollama", "model-test", "http://ollama:11434", "ollama_chat/model-test"),
])
def test_litellm_agent_executes_tool_calls(tmp_path, provider, model_name, url, expected_model) -> None:
    database = PrivateDatabase(tmp_path / "private")
    secrets = SecretStore(database)
    registry = ModelRegistry(ModelConfigStore(database), secrets)
    if provider != "ollama":
        secrets.put("alice", provider, "alice-key")
    registry.configure("alice", ModelConfig(provider, model_name, url))
    agent = registry.agent_for("alice")
    observed = []

    def read_state(entity_id: str) -> str:
        observed.append(entity_id)
        return "waiting"

    agent.tools = [read_state]
    responses = [
        ModelResponse(model=expected_model, choices=[{"finish_reason": "tool_calls", "message": {
            "role": "assistant", "tool_calls": [{"id": "call-1", "type": "function", "function": {
                "name": "read_state", "arguments": '{"entity_id":"climate.salon"}'
            }}]
        }}]),
        ModelResponse(model=expected_model, choices=[{"finish_reason": "stop", "message": {
            "role": "assistant", "content": "Le thermostat est en attente."
        }}]),
    ]

    async def run_agent():
        sessions = InMemorySessionService()
        await sessions.create_session(app_name="vtherm", user_id="alice", session_id="session")
        runner = Runner(app_name="vtherm", agent=agent, session_service=sessions)
        return [event async for event in runner.run_async(
            user_id="alice", session_id="session",
            new_message=types.Content(role="user", parts=[types.Part(text="État du salon ?")]),
        )]

    with patch("google.adk.models.lite_llm.LiteLLMClient.acompletion", new_callable=AsyncMock, side_effect=responses) as completion:
        events = asyncio.run(run_agent())
    assert observed == ["climate.salon"]
    assert events[-1].content.parts[0].text == "Le thermostat est en attente."
    assert completion.await_count == 2
    assert completion.call_args_list[0].kwargs["model"] == expected_model
    assert completion.call_args_list[0].kwargs["tools"][0]["function"]["name"] == "read_state"
    assert completion.call_args_list[0].kwargs["api_key"] == ("ollama" if provider == "ollama" else "alice-key")
    if url:
        assert completion.call_args_list[0].kwargs["api_base"] == url


@pytest.mark.parametrize("provider, url", [("openai", None), ("anthropic", None), ("ollama", "http://ollama:11434")])
def test_litellm_provider_error_does_not_expose_user_key(tmp_path, provider, url, caplog) -> None:
    database = PrivateDatabase(tmp_path / "private")
    secrets = SecretStore(database)
    registry = ModelRegistry(ModelConfigStore(database), secrets)
    if provider != "ollama":
        secrets.put("alice", provider, "alice-key")
    registry.configure("alice", ModelConfig(provider, "model-test", url))
    model = cast(LiteLlm, registry.agent_for("alice").model)
    assert isinstance(model, LiteLlm)

    with patch("google.adk.models.lite_llm.LiteLLMClient.acompletion", new_callable=AsyncMock, side_effect=RuntimeError("invalid key alice-key")):
        with pytest.raises(RuntimeError) as error:
            asyncio.run(generate_responses(model, LlmRequest(model=model.model)))
        try:
            asyncio.run(generate_responses(model, LlmRequest(model=model.model)))
        except RuntimeError:
            logging.getLogger(__name__).exception("Erreur du fournisseur")
    assert "alice-key" not in str(error.value)
    assert "alice-key" not in caplog.text


@pytest.mark.parametrize("status, code, category", [
    (401, "invalid_api_key", "authentication"),
    (404, "model_not_found", "model_access"),
    (429, "insufficient_quota", "quota"),
    (400, "unsupported_parameter", "parameters"),
])
def test_openai_failure_logs_actionable_metadata_without_sensitive_payload(tmp_path, caplog, status, code, category) -> None:
    database = PrivateDatabase(tmp_path / "private")
    secrets = SecretStore(database)
    registry = ModelRegistry(ModelConfigStore(database), secrets)
    secrets.put("alice", "openai", "alice-key")
    registry.configure("alice", ModelConfig("openai", "model-test"))
    model = cast(LiteLlm, registry.agent_for("alice").model)
    response = httpx.Response(status, request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"))
    failure = APIStatusError(
        "alice-key unknown-key-prefix private-question",
        response=response,
        body={"code": code, "message": "alice-key unknown-key-prefix private-question"},
    )

    with patch("google.adk.models.lite_llm.LiteLLMClient.acompletion", new_callable=AsyncMock, side_effect=failure):
        with pytest.raises(RuntimeError, match="La requête au fournisseur a échoué"):
            asyncio.run(generate_responses(model, LlmRequest(model="openai/model-test")))

    assert "operation=provider.generate" in caplog.text
    assert f"http_status={status}" in caplog.text
    assert f"code={code}" in caplog.text
    assert f"category={category}" in caplog.text
    assert all(value not in caplog.text for value in ("alice-key", "unknown-key-prefix", "private-question"))


def test_ollama_unavailable_server_returns_safe_error(tmp_path) -> None:
    database = PrivateDatabase(tmp_path / "private")
    registry = ModelRegistry(ModelConfigStore(database), SecretStore(database))
    registry.configure("alice", ModelConfig("ollama", "model-test", "http://ollama:11434"))
    model = cast(LiteLlm, registry.agent_for("alice").model)
    assert isinstance(model, LiteLlm)

    with patch("google.adk.models.lite_llm.LiteLLMClient.acompletion", new_callable=AsyncMock, side_effect=ConnectionError("connection refused")):
        with pytest.raises(RuntimeError, match="La requête au fournisseur a échoué"):
            asyncio.run(generate_responses(model, LlmRequest(model=model.model)))


def test_local_model_does_not_require_a_remote_key(tmp_path) -> None:
    database = PrivateDatabase(tmp_path / "private")
    registry = ModelRegistry(ModelConfigStore(database), SecretStore(database))
    registry.configure("alice", ModelConfig("ollama", "model:latest", "http://ollama:11434"))
    model = registry.agent_for("alice").model
    assert isinstance(model, LiteLlm)
    assert getattr(model, "model") == "ollama_chat/model:latest"
    assert getattr(model, "_additional_args")["api_base"] == "http://ollama:11434"


@pytest.mark.parametrize("config", [
    ModelConfig("unknown", "model"),
    ModelConfig("openai", ""),
    ModelConfig("ollama", "model", "http://user:secret@localhost"),
    ModelConfig("ollama", "model", "file:///tmp/model"),
    ModelConfig("gemini", "model", "https://example.com"),
])
def test_invalid_model_configuration_is_rejected(config) -> None:
    with pytest.raises(ValueError):
        config.validate()


def test_model_config_route_is_private_and_isolated(tmp_path) -> None:
    async def verify_admin(user_id: str) -> bool:
        return user_id in {"alice", "bob"}

    application = create_app("ingress", verify_admin=verify_admin, data_dir=tmp_path / "private")
    alice = {"X-Remote-User-Id": "alice", "X-VTherm-Request": "1"}
    bob = {"X-Remote-User-Id": "bob", "X-VTherm-Request": "1"}
    with TestClient(application, client=(SUPERVISOR_ADDRESS, 12345)) as client:
        assert client.get("/api/model").status_code == 403
        assert client.put("/api/model", headers=alice, json={"provider": "gemini", "model": "model-a"}).status_code == 204
        assert client.put("/api/model", headers=bob, json={"provider": "ollama", "model": "model-b", "url": "http://ollama:11434"}).status_code == 204
        assert client.get("/api/model?user_id=bob", headers=alice).json() == {"provider": "gemini", "model": "model-a", "url": None}
        assert client.get("/api/model", headers=bob).json() == {"provider": "ollama", "model": "model-b", "url": "http://ollama:11434"}
        response = client.put("/api/model", headers=alice, json={"provider": "bad-secret", "model": "model"})
        assert response.status_code == 400
        assert "bad-secret" not in response.text