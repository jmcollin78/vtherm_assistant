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


@pytest.mark.parametrize("provider_name", ["openai", "anthropic", "gemini", "ollama"])
def test_model_catalog_uses_personal_credentials_and_installed_models(tmp_path, provider_name):
    database = PrivateDatabase(tmp_path / "private")
    secrets = SecretStore(database)
    registry = ModelRegistry(ModelConfigStore(database), secrets)
    if provider_name == "ollama":
        registry.configure("alice", ModelConfig("ollama", "manual-model", "http://ollama:11434"))
    else:
        secrets.put("alice", provider_name, "alice-key")
    requests = []
    def handle(request):
        requests.append(request)
        if provider_name == "gemini":
            return httpx.Response(200, json={"models": [
                {"name": "models/model-test", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/embedding-test", "supportedGenerationMethods": ["embedContent"]},
            ]})
        if provider_name == "ollama":
            return httpx.Response(200, json={"models": [{"name": "model-test"}]})
        return httpx.Response(200, json={"data": [{"id": "model-test"}, {"id": "model-test"}]})
    result = asyncio.run(registry.catalog_for("alice", provider_name, transport=httpx.MockTransport(handle)))
    assert result["source"] == "dynamic" and result["complete"] is True
    assert [model["id"] for model in result["models"]] == ["model-test"]
    assert result["models"][0]["compatibility"] == "unverified"
    assert len(requests) == 1 and requests[0].method == "GET"
    if provider_name == "gemini":
        assert requests[0].headers["x-goog-api-key"] == "alice-key"
    elif provider_name == "anthropic":
        assert requests[0].headers["x-api-key"] == "alice-key"
    elif provider_name == "openai":
        assert requests[0].headers["authorization"] == "Bearer alice-key"
    else:
        assert str(requests[0].url) == "http://ollama:11434/api/tags"
        assert "authorization" not in requests[0].headers
    assert "alice-key" not in str(result)


@pytest.mark.parametrize("provider_name", ["anthropic", "gemini"])
@pytest.mark.parametrize("outcome", ["complete", "failure", "repeated", "bounded"])
def test_model_catalog_paginates_and_signals_incomplete_results(tmp_path, provider_name, outcome):
    database = PrivateDatabase(tmp_path / "private")
    secrets = SecretStore(database)
    registry = ModelRegistry(ModelConfigStore(database), secrets)
    secrets.put("alice", provider_name, "alice-key")
    requests = []
    def handle(request):
        requests.append(request)
        page_number = len(requests)
        if page_number == 2 and outcome == "failure":
            return httpx.Response(503, text="private-error alice-key")
        more = outcome != "complete" or page_number == 1
        cursor = "same" if outcome == "repeated" else str(page_number)
        if provider_name == "gemini":
            data = {"models": [{"name": f"models/model-{page_number}", "supportedGenerationMethods": ["generateContent"]}]}
            if more:
                data["nextPageToken"] = cursor
        else:
            data = {"data": [{"id": f"model-{page_number}"}], "has_more": more, "last_id": cursor}
        return httpx.Response(200, json=data)
    result = asyncio.run(registry.catalog_for("alice", provider_name, transport=httpx.MockTransport(handle)))
    assert result["source"] == "dynamic"
    assert result["complete"] is (outcome == "complete")
    assert len(requests) == (10 if outcome == "bounded" else 2)
    assert [model["id"] for model in result["models"]] == [f"model-{index + 1}" for index in range(1 if outcome == "failure" else len(requests))]
    cursor_name = "pageToken" if provider_name == "gemini" else "after_id"
    assert requests[1].url.params[cursor_name] == ("same" if outcome == "repeated" else "1")


@pytest.mark.parametrize("provider_name", ["openai", "anthropic", "gemini", "ollama"])
def test_model_catalog_missing_configuration_uses_identified_suggestions(tmp_path, provider_name):
    database = PrivateDatabase(tmp_path / "private")
    registry = ModelRegistry(ModelConfigStore(database), SecretStore(database))
    def handle(_request):
        pytest.fail("Aucun appel externe sans paramètres personnels")
    result = asyncio.run(registry.catalog_for("alice", provider_name, transport=httpx.MockTransport(handle)))
    assert result["source"] == "suggestions" and result["complete"] is False
    assert result["models"] and "sans garantie" in result["message"]


def test_model_catalog_isolates_users_and_never_reuses_replaced_credentials(tmp_path):
    database = PrivateDatabase(tmp_path / "private")
    secrets = SecretStore(database)
    registry = ModelRegistry(ModelConfigStore(database), secrets)
    secrets.put("alice", "openai", "alice-key")
    secrets.put("bob", "openai", "bob-key")
    observed = []
    def handle(request):
        observed.append(request.headers["authorization"])
        return httpx.Response(200, json={"data": [{"id": f"model-{len(observed)}"}]})
    async def run():
        first = await registry.catalog_for("alice", "openai", transport=httpx.MockTransport(handle))
        second = await registry.catalog_for("bob", "openai", transport=httpx.MockTransport(handle))
        secrets.put("alice", "openai", "replacement-key")
        third = await registry.catalog_for("alice", "openai", transport=httpx.MockTransport(handle))
        return first, second, third
    results = asyncio.run(run())
    assert observed == ["Bearer alice-key", "Bearer bob-key", "Bearer replacement-key"]
    assert [result["models"][0]["id"] for result in results] == ["model-1", "model-2", "model-3"]


def test_model_catalog_uses_reconfigured_ollama_url_without_cache(tmp_path):
    database = PrivateDatabase(tmp_path / "private")
    registry = ModelRegistry(ModelConfigStore(database), SecretStore(database))
    urls = []
    def handle(request):
        urls.append(str(request.url))
        return httpx.Response(200, json={"models": []})
    async def run():
        for url in ("http://first:11434", "http://second:11434"):
            registry.configure("alice", ModelConfig("ollama", "manual", url))
            await registry.catalog_for("alice", "ollama", transport=httpx.MockTransport(handle))
    asyncio.run(run())
    assert urls == ["http://first:11434/api/tags", "http://second:11434/api/tags"]


@pytest.mark.parametrize("outcome", ["empty", "http", "network", "invalid"])
def test_model_catalog_errors_do_not_expose_credentials(tmp_path, caplog, outcome):
    database = PrivateDatabase(tmp_path / "private")
    secrets = SecretStore(database)
    registry = ModelRegistry(ModelConfigStore(database), secrets)
    secrets.put("alice", "openai", "alice-key")
    def handle(request):
        if outcome == "network":
            raise httpx.ConnectError("alice-key private-body", request=request)
        if outcome == "http":
            return httpx.Response(401, text="alice-key private-body")
        if outcome == "invalid":
            return httpx.Response(200, text="alice-key private-body")
        return httpx.Response(200, json={"data": []})
    result = asyncio.run(registry.catalog_for("alice", "openai", transport=httpx.MockTransport(handle)))
    assert "alice-key" not in str(result) + caplog.text
    assert "private-body" not in str(result) + caplog.text
    assert result["source"] == ("dynamic" if outcome == "empty" else "suggestions")
    assert result["complete"] is (outcome == "empty")
    if outcome == "empty":
        assert result["models"] == []


def test_model_catalog_route_requires_verified_user_and_returns_no_store(tmp_path):
    async def verify_admin(user_id):
        return user_id == "alice"
    application = create_app("ingress", verify_admin=verify_admin, data_dir=tmp_path / "private")
    with TestClient(application, client=(SUPERVISOR_ADDRESS, 12345)) as client, \
         patch.object(application.state.models, "catalog_for", new_callable=AsyncMock, return_value={
             "provider": "openai", "source": "dynamic", "complete": True, "models": [], "message": "Aucun modèle retourné.",
         }) as catalog:
        denied = client.get("/api/models?provider=openai", headers={"X-Remote-User-Id": "bob"})
        response = client.get("/api/models?provider=openai", headers={"X-Remote-User-Id": "alice"})
    assert denied.status_code == 403 and response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    catalog.assert_awaited_once_with("alice", "openai")


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


@pytest.mark.parametrize("provider, model_name, url, expected_model, expected_reasoning_effort", [
    ("openai", "model-test", None, "openai/model-test", None),
    ("openai", "gpt-6-luna", None, "openai/gpt-6-luna", "none"),
    ("anthropic", "model-test", None, "anthropic/model-test", None),
    ("ollama", "model-test", "http://ollama:11434", "ollama_chat/model-test", None),
])
def test_litellm_agent_executes_tool_calls(tmp_path, provider, model_name, url, expected_model, expected_reasoning_effort) -> None:
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
    assert completion.call_args_list[0].kwargs.get("reasoning_effort") == expected_reasoning_effort
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