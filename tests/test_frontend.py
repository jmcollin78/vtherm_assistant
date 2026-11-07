import json
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from google.genai import types
from mcp.types import CallToolResult, TextContent, Tool
from playwright.sync_api import expect, sync_playwright

from vtherm_assistant.main import BRAND_LOGO, FRONTEND, SUPERVISOR_ADDRESS, create_app
from vtherm_assistant.models import ModelConfig


@pytest.fixture(name="page")
def browser_page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            yield browser.new_page()
        finally:
            browser.close()


@pytest.fixture(name="frontend", params=[(1280, 900), (390, 844)], ids=["desktop", "mobile"])
def browser_frontend(page, request):
    page.set_viewport_size({"width": request.param[0], "height": request.param[1]})
    state = {
        "messages": [{"role": "user", "text": "État du salon ?"}, {"role": "assistant", "text": "En attente."}],
        "model": {"provider": "gemini", "model": "model-test", "url": None},
        "failures": {}, "calls": [], "stream": "complete", "stream_events": None, "stream_text": None, "errors": [],
        "prefix": "", "request_paths": [],
    }
    page.on("pageerror", lambda error: state["errors"].append(str(error)))

    def handle(route):
        path, method = urlsplit(route.request.url).path, route.request.method
        state["request_paths"].append(path)
        if state["prefix"]:
            if not path.startswith(state["prefix"] + "/"):
                route.fulfill(status=404)
                return
            path = path[len(state["prefix"]):]
        state["calls"].append((method, path, route.request.post_data_json if route.request.post_data else None))
        failure = state["failures"].get((method, path))
        if failure == "network":
            route.abort("failed")
        elif failure == "http":
            route.fulfill(status=503, json={"detail": "FAKE_SECRET_DO_NOT_DISPLAY"})
        elif failure in {"ingress", "standalone"}:
            route.fulfill(status=403, headers={"X-VTherm-Deployment-Mode": failure}, json={"detail": "Accès refusé"})
        elif path == "/":
            route.fulfill(content_type="text/html", body=FRONTEND.read_text())
        elif path == "/brand/logo.png":
            route.fulfill(content_type="image/png", body=BRAND_LOGO.read_bytes())
        elif path == "/api/model":
            if method == "GET" and state.get("hold_model"):
                state["pending_model"] = route
            elif method == "PUT":
                state["model"] = route.request.post_data_json
                route.fulfill(status=204)
            else:
                route.fulfill(json=state["model"])
        elif path == "/api/conversation" and method == "GET":
            route.fulfill(json={"messages": state["messages"]})
        elif path == "/api/conversation" and method == "DELETE":
            state["messages"] = []
            route.fulfill(status=204)
        elif path == "/api/conversation" and method == "POST":
            if state["stream"] == "pending":
                state["pending"] = route
                return
            events = state["stream_events"] or [{"type": "delta", "text": "Je consulte le thermostat. "}, {"type": "delta", "text": "En attente."}]
            if state["stream"] == "complete":
                events = [*events, {"type": "complete"}]
                state["messages"] += [{"role": "user", "text": route.request.post_data_json["question"]},
                                      {"role": "assistant", "text": state["stream_text"] or "Je consulte le thermostat. En attente."}]
            elif state["stream"] == "error":
                events.append({"type": "error", "message": "Fournisseur indisponible ; réessayez."})
            route.fulfill(content_type="application/x-ndjson", body="".join(json.dumps(event) + "\n" for event in events))
        elif path.startswith("/api/secrets/"):
            route.fulfill(status=204)
        else:
            route.fulfill(status=404)

    page.route("http://assistant.test/**", handle)
    page.goto("http://assistant.test/")
    expect(page.locator("#conversation")).to_be_visible()
    yield page, state
    assert state["errors"] == []


def open_settings(page):
    page.locator("#settings-button").click()
    expect(page.locator("#model-form")).not_to_have_attribute("inert", "")


def assert_empty_secrets(page):
    expect(page.locator("#provider-key")).to_have_value("")
    expect(page.locator("#ha-key")).to_have_value("")


def test_frontend_navigation_under_ingress_prefix(frontend):
    page, state = frontend
    state["prefix"] = "/api/hassio_ingress/test-session"
    state["request_paths"].clear()
    state["calls"].clear()
    page.goto("http://assistant.test" + state["prefix"] + "/")
    expect(page.locator("#conversation")).to_be_visible()
    assert page.locator(".brand-logo").evaluate("image => image.complete && image.naturalWidth > 0")

    open_settings(page)
    page.locator("#model").fill("ingress-model")
    page.locator("#model-form button[type=submit]").click()
    expect(page.locator("#model-feedback")).to_have_text("Configuration enregistrée.")
    assert state["model"]["model"] == "ingress-model"
    page.locator("#back").click()
    page.locator("#question").fill("État du thermostat ?")
    page.locator("#send").click()
    expect(page.locator(".message.assistant").last.locator(".message-text")).to_have_text("Je consulte le thermostat. En attente.")
    expect(page.locator(".message-state").last).to_have_text("")
    page.reload()
    expect(page.locator(".message")).to_have_count(4)
    page.locator("#new").click()
    expect(page.locator(".empty")).to_be_visible()
    page.reload()
    expect(page.locator(".empty")).to_be_visible()

    assert all(path.startswith(state["prefix"] + "/") for path in state["request_paths"])
    assert ("GET", "/brand/logo.png", None) in state["calls"]
    assert {("GET", "/api/model"), ("PUT", "/api/model"), ("POST", "/api/conversation"),
            ("DELETE", "/api/conversation")} <= {(method, path) for method, path, _payload in state["calls"]}
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("mode", ["ingress", "standalone"])
def test_frontend_refusal_does_not_offer_oauth_in_ingress(frontend, mode):
    page, state = frontend
    state["failures"][("GET", "/api/conversation")] = mode
    page.reload()
    expect(page.locator("#login")).to_be_visible()
    expect(page.locator("#conversation")).to_be_hidden()
    if mode == "ingress":
        expect(page.locator("#login h1")).to_have_text("Accès refusé")
        expect(page.locator("#login a")).to_be_hidden()
    else:
        expect(page.locator("#login h1")).to_have_text("Connexion requise")
        expect(page.locator("#login a")).to_be_visible()
        expect(page.locator("#login a")).to_have_attribute("href", "auth/login")


@pytest.mark.parametrize("provider_name", ["gemini", "openai", "anthropic", "ollama"])
def test_frontend_configures_each_provider_without_losing_messages(frontend, provider_name):
    page, state = frontend
    open_settings(page)
    page.locator("#provider").select_option(provider_name)
    page.locator("#model").fill("model-configured")
    if provider_name == "ollama":
        expect(page.locator("#key-field")).to_be_hidden()
        expect(page.locator("#privacy")).to_be_hidden()
        page.locator("#url").fill("http://ollama:11434")
    else:
        page.locator("#provider-key").fill("FAKE_PROVIDER_KEY")
        expect(page.locator("#provider-key")).to_have_attribute("type", "password")
        expect(page.locator("#privacy")).to_be_visible()
    page.locator("#ha-key").fill("FAKE_HA_TOKEN")
    page.locator("#model-form button[type=submit]").click()
    expect(page.locator("#model-feedback")).to_have_text("Configuration enregistrée.")
    assert_empty_secrets(page)
    assert state["model"]["provider"] == provider_name
    page.locator("#back").click()
    expect(page.locator(".message")).to_have_count(2)
    page.reload()
    expect(page.locator(".message")).to_have_count(2)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("leave_action", ["back", "new"])
def test_frontend_clears_unsaved_secrets_when_leaving(frontend, leave_action):
    page, state = frontend
    open_settings(page)
    page.locator("#provider-key").fill("FAKE_PROVIDER_KEY")
    page.locator("#ha-key").fill("FAKE_HA_TOKEN")
    page.locator(f"#{leave_action}").click()
    expect(page.locator("#conversation")).to_be_visible()
    assert_empty_secrets(page)
    if leave_action == "new":
        expect(page.locator(".message")).to_have_count(0)
        page.reload()
        expect(page.locator(".empty")).to_be_visible()
        assert state["messages"] == []


@pytest.mark.parametrize("failure", ["network", "http"])
@pytest.mark.parametrize("action,method,path,feedback_id", [
    ("load", "GET", "/api/model", "model-feedback"),
    ("model", "PUT", "/api/model", "model-feedback"),
    ("provider-key", "PUT", "/api/secrets/gemini", "model-feedback"),
    ("ha", "PUT", "/api/secrets/home_assistant", "ha-feedback"),
    ("delete-key", "DELETE", "/api/secrets/gemini", "model-feedback"),
    ("delete-ha-key", "DELETE", "/api/secrets/home_assistant", "ha-feedback"),
    ("new", "DELETE", "/api/conversation", "app-feedback"),
])
def test_frontend_errors_are_visible_and_retryable(frontend, failure, action, method, path, feedback_id):
    page, state = frontend
    if action != "load":
        open_settings(page)
        page.locator("#provider-key").fill("FAKE_PROVIDER_KEY")
        page.locator("#ha-key").fill("FAKE_HA_TOKEN")
    state["failures"][(method, path)] = failure

    def trigger():
        if action == "load":
            page.locator("#settings-button").click()
        elif action in {"model", "provider-key"}:
            page.locator("#provider-key").fill("FAKE_PROVIDER_KEY")
            page.locator("#model-form button[type=submit]").click()
        elif action == "ha":
            page.locator("#ha-key").fill("FAKE_HA_TOKEN")
            page.locator("#ha-form button[type=submit]").click()
        else:
            page.locator(f"#{action}").click()

    trigger()
    expect(page.locator(f"#{feedback_id}")).to_have_class("feedback error" if feedback_id != "app-feedback" else "feedback app-feedback error")
    expect(page.locator(f"#{feedback_id}")).to_contain_text("réessayez")
    assert_empty_secrets(page)
    assert "FAKE_SECRET_DO_NOT_DISPLAY" not in page.locator("body").inner_text()
    assert "FAKE_PROVIDER_KEY" not in page.locator("body").inner_text()
    assert "FAKE_HA_TOKEN" not in page.locator("body").inner_text()
    if action == "new":
        assert len(state["messages"]) == 2
        page.locator("#back").click()
        expect(page.locator(".message")).to_have_count(2)
    state["failures"].clear()
    trigger()
    expect(page.locator(f"#{feedback_id}")).not_to_have_class("feedback error" if feedback_id != "app-feedback" else "feedback app-feedback error")
    assert_empty_secrets(page)


@pytest.mark.parametrize("stream_mode", ["complete", "interrupted", "error"])
def test_frontend_conversation_stream_and_retry(frontend, stream_mode):
    page, state = frontend
    state["stream"] = stream_mode
    page.locator("#question").fill("Pourquoi le salon ?")
    page.locator("#send").click()
    expect(page.locator(".message.assistant").last.locator(".message-text")).to_have_text("Je consulte le thermostat. En attente.")
    if stream_mode != "complete":
        expect(page.locator(".message.assistant").last.locator(".message-state")).to_have_class("message-state error")
        state["stream"] = "complete"
        page.get_by_role("button", name="Réessayer", exact=True).click()
    expect(page.locator(".message.assistant").last.locator(".message-state")).to_have_text("")
    expect(page.locator("#send")).to_be_enabled()
    expect(page.locator(".message")).to_have_count(4)
    page.reload()
    expect(page.locator(".message")).to_have_count(4)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_frontend_renders_markdown_safely_in_history_and_stream(frontend):
    page, state = frontend
    markdown = (
        "## Diagnostic\n\n**Fait observé** et _hypothèse_.\n\n"
        "- Fenêtre ouverte\n- `climate.salon`\n\n"
        "[Documentation](https://www.versatile-thermostat.org/fr/docs/feature-window/)\n\n"
        "<img src=x onerror=alert(1)> <script>window.markdownPwned = true</script>"
    )
    state["messages"] = [{"role": "user", "text": "Pourquoi ?"}, {"role": "assistant", "text": markdown}]
    page.reload()
    body = page.locator(".message.assistant .message-text").last
    expect(body.locator("h2")).to_have_text("Diagnostic")
    expect(body.locator("strong")).to_have_text("Fait observé")
    expect(body.locator("em")).to_have_text("hypothèse")
    expect(body.locator("li")).to_have_count(2)
    expect(body.locator("code").first).to_have_text("climate.salon")
    expect(body.locator("a")).to_have_attribute("href", "https://www.versatile-thermostat.org/fr/docs/feature-window/")
    assert body.locator("img, script").count() == 0
    assert "<img src=x onerror=alert(1)>" in body.inner_text()

    state["stream_text"] = markdown
    state["stream_events"] = [{"type": "delta", "text": markdown[:48]}, {"type": "delta", "text": markdown[48:]}]
    page.locator("#question").fill("Explique-moi ce résultat")
    page.locator("#send").click()
    streamed = page.locator(".message.assistant .message-text").last
    expect(streamed.locator("h2")).to_have_text("Diagnostic")
    expect(streamed.locator("strong")).to_have_text("Fait observé")
    assert streamed.locator("img, script").count() == 0
    assert page.evaluate("window.markdownPwned") is None


def test_frontend_shows_inflight_response(frontend):
    page, state = frontend
    state["stream"] = "pending"
    page.locator("#question").fill("État du bureau ?")
    with page.expect_request("**/api/conversation"):
        page.locator("#send").click()
    expect(page.locator("#send")).to_be_disabled()
    expect(page.locator(".message-state").last).to_have_text("Réponse en cours…")
    expect(page.locator("#question")).to_have_value("")
    state["pending"].fulfill(content_type="application/x-ndjson", body='{"type":"delta","text":"En attente."}\n{"type":"complete"}\n')
    expect(page.locator("#send")).to_be_enabled()
    expect(page.locator(".message-state").last).to_have_text("")


def test_frontend_shows_configuration_loading_and_clears_secrets_after_slow_failure(frontend):
    page, state = frontend
    state["hold_model"] = True
    with page.expect_request("**/api/model"):
        page.locator("#settings-button").click()
    expect(page.locator("#settings-button")).to_be_disabled()
    expect(page.locator("#model-feedback")).to_have_text("En cours…")
    expect(page.locator("#model-form")).to_have_attribute("inert", "")
    page.locator("#ha-key").fill("FAKE_HA_TOKEN")
    state["pending_model"].fulfill(status=503)
    expect(page.locator("#model-feedback")).to_contain_text("réessayez")
    expect(page.locator("#settings-button")).to_be_enabled()
    assert_empty_secrets(page)
    state["hold_model"] = False
    open_settings(page)


def test_frontend_restores_isolated_followups_after_backend_restart(frontend, tmp_path, monkeypatch):
    page, _state = frontend
    monkeypatch.setenv("VTHERM_HA_INTERNAL_URL", "http://homeassistant:8123")
    directory = tmp_path / "private"
    active = {"user": "alice"}
    observed_requests = []
    tool = Tool(name="versatile_thermostat__get_status", inputSchema={"type": "object"})

    async def verify_admin(user_id):
        return user_id in {"alice", "bob"}

    async def read_tool(user_id, _name, _arguments):
        return CallToolResult(content=[TextContent(type="text", text=f"evidence-{user_id}")])

    async def generate(**kwargs):
        contents = kwargs["contents"]
        history = json.dumps([content.model_dump(mode="json") for content in contents])
        observed_requests.append((kwargs["model"], history))
        has_response = any(part.function_response for content in contents for part in content.parts or [])
        if not has_response and contents[-1].parts[0].text == "Diagnostic ?":
            part = types.Part(function_call=types.FunctionCall(name=tool.name, args={"entity_id": "climate.salon"}))
        else:
            part = types.Part(text=f"Observation pour {kwargs['model']}.")

        async def stream():
            yield types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[part]))])

        return stream()

    def handle_backend(route):
        response = active["client"].request(
            route.request.method, urlsplit(route.request.url).path,
            content=route.request.post_data,
            headers={"X-Remote-User-Id": active["user"], "X-VTherm-Request": "1", "Content-Type": "application/json"},
        )
        route.fulfill(status=response.status_code, content_type=response.headers.get("content-type", "application/json"), body=response.content)

    with ExitStack() as stack:
        stack.enter_context(patch("vtherm_assistant.ha_mcp.HomeAssistantMCP.list_read_only_tools", new_callable=AsyncMock, return_value=[tool]))
        stack.enter_context(patch("vtherm_assistant.ha_mcp.HomeAssistantMCP.call_read_only_tool", new_callable=AsyncMock, side_effect=read_tool))
        provider = stack.enter_context(patch("google.genai.Client"))
        provider.return_value.aio.models.generate_content_stream = AsyncMock(side_effect=generate)
        application = create_app("ingress", verify_admin=verify_admin, data_dir=directory)
        for user_id in ("alice", "bob"):
            application.state.secrets.put(user_id, "gemini", f"fake-{user_id}-key")
            application.state.models.configure(user_id, ModelConfig("gemini", f"{user_id}-test"))
        active["client"] = stack.enter_context(TestClient(application, client=(SUPERVISOR_ADDRESS, 12345)))
        page.route("http://assistant.test/api/**", handle_backend)
        for user_id in ("alice", "bob"):
            active["user"] = user_id
            page.reload()
            expect(page.locator(".message")).to_have_count(0)
            page.locator("#question").fill("Diagnostic ?")
            page.locator("#send").click()
            expect(page.locator(".message.assistant").last.locator(".message-text")).to_have_text(f"Observation pour {user_id}-test.")
            expect(page.locator(".message-state").last).to_have_text("")
        restarted = create_app("ingress", verify_admin=verify_admin, data_dir=directory)
        active["client"] = stack.enter_context(TestClient(restarted, client=(SUPERVISOR_ADDRESS, 12345)))
        for user_id in ("alice", "bob"):
            active["user"] = user_id
            page.reload()
            expect(page.locator(".message")).to_have_count(2)
            page.locator("#question").fill("Pourquoi ?")
            page.locator("#send").click()
            expect(page.locator(".message")).to_have_count(4)
            expect(page.locator(".message-state").last).to_have_text("")
            model, history = observed_requests[-1]
            assert model == f"{user_id}-test"
            assert f"evidence-{user_id}" in history
            other_user = "bob" if user_id == "alice" else "alice"
            assert f"evidence-{other_user}" not in history
        active["user"] = "alice"
        page.reload()
        page.locator("#new").click()
        expect(page.locator(".empty")).to_be_visible()
        page.reload()
        expect(page.locator(".empty")).to_be_visible()
        page.locator("#question").fill("Pourquoi ?")
        page.locator("#send").click()
        expect(page.locator(".message-state").last).to_have_text("")
        assert "evidence-" not in observed_requests[-1][1]
        assert len(restarted.state.conversations.load("bob")[0]) == 4