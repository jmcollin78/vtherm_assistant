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
def browser_page(request):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            yield browser.new_page(**getattr(request, "param", {}))
        finally:
            browser.close()


@pytest.fixture(name="frontend", params=[(1280, 900), (390, 844)], ids=["desktop", "mobile"])
def browser_frontend(page, request):
    page.set_viewport_size({"width": request.param[0], "height": request.param[1]})
    state = {
        "messages": [{"role": "user", "text": "État du salon ?"}, {"role": "assistant", "text": "En attente."}],
        "model": {"provider": "gemini", "model": "model-test", "url": None},
        "failures": {}, "calls": [], "stream": "complete", "stream_events": None, "stream_text": None, "errors": [],
        "prefix": "", "request_paths": [], "pending_confirmation": None, "confirmation_requests": [],
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
        elif path == "/api/models":
            selected_provider = route.request.url.split("provider=")[-1]
            if state.get("hold_catalog") == selected_provider:
                state["pending_catalog"] = route
            else:
                route.fulfill(json=state.get("catalogs", {}).get(selected_provider, {
                    "provider": selected_provider, "source": "dynamic", "complete": True,
                    "models": [{"id": selected_provider + "-catalog-model", "compatibility": "unverified"}], "message": "Compatibilité non vérifiée.",
                }))
        elif path == "/api/model":
            if method == "GET" and state.get("hold_model"):
                state["pending_model"] = route
            elif method == "PUT":
                state["model"] = route.request.post_data_json
                route.fulfill(status=204)
            else:
                route.fulfill(json=state["model"])
        elif path == "/api/conversation" and method == "GET":
            route.fulfill(json={"messages": state["messages"], "version": state.get("version", 0),
                                "inventory": state.get("inventory"),
                                "pending_confirmation": state.get("pending_confirmation")})
        elif path == "/api/conversation" and method == "DELETE":
            state["messages"] = []
            state["inventory"] = None
            state["pending_confirmation"] = None
            state["version"] = state.get("version", 0) + 1
            route.fulfill(status=204)
        elif path == "/api/conversation/inventory":
            if state.get("hold_inventory"):
                state["pending_inventory"] = route
            elif state.get("inventory_payload") is None:
                route.fulfill(status=503, json={"code": "missing_token"})
            else:
                state["inventory"] = state["inventory_payload"]
                state["version"] = state.get("version", 0) + 1
                route.fulfill(json={"inventory": state["inventory"], "version": state["version"]})
        elif path == "/api/conversation" and method == "POST":
            if state["stream"] == "pending":
                state["pending"] = route
                return
            events = state["stream_events"] or [{"type": "delta", "text": "Je consulte le thermostat. "}, {"type": "delta", "text": "En attente."}]
            if state["stream"] == "confirmation":
                confirmation = state["confirmation"]
                state["pending_confirmation"] = confirmation
                state["messages"].append({"role": "user", "text": route.request.post_data_json["question"]})
                events = [{"type": "confirmation", **confirmation}]
            elif state["stream"] == "complete":
                events = [*events, {"type": "complete"}]
                state["messages"] += [{"role": "user", "text": route.request.post_data_json["question"]},
                                      {"role": "assistant", "text": state["stream_text"] or "Je consulte le thermostat. En attente."}]
                state["messages"][-2]["created_at"] = route.request.post_data_json.get("created_at")
                state["messages"][-1]["created_at"] = next((event.get("created_at") for event in events if event["type"] == "delta"), None)
            elif state["stream"] == "error":
                events.append({"type": "error", "message": "Fournisseur indisponible ; réessayez."})
            route.fulfill(content_type="application/x-ndjson", body="".join(json.dumps(event) + "\n" for event in events))
        elif path == "/api/conversation/confirm" and method == "POST":
            state["confirmation_requests"].append(route.request.post_data_json)
            approved = route.request.post_data_json["confirmed"]
            state["pending_confirmation"] = None
            response_text = "Résultat MCP reçu." if approved else "Aucune écriture demandée."
            state["messages"].append({"role": "assistant", "text": response_text})
            events = [{"type": "delta", "text": response_text}, {"type": "complete"}]
            route.fulfill(content_type="application/x-ndjson", body="".join(json.dumps(event) + "\n" for event in events))
        elif path.startswith("/api/secrets/"):
            route.fulfill(status=204)
        else:
            route.fulfill(status=404)

    page.route("http://assistant.test/**", handle)
    state["handle"] = handle
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


def confirmation_details(**updates):
    return {
        "confirmation_id": "confirmation-test-id",
        "operation": "versatile_thermostat__set_temperature",
        "target": "climate.salon",
        "arguments": {"entity_id": "climate.salon", "temperature": 20},
        "hint": "Vérifiez la cible et la température.",
        "expires_at": 2000000000,
        **updates,
    }


@pytest.mark.parametrize("approved", [True, False], ids=["approve", "refuse"])
def test_frontend_confirmation_shows_exact_parameters_and_sends_only_decision(frontend, approved):
    page, state = frontend
    state["stream"] = "confirmation"
    state["confirmation"] = confirmation_details()
    page.reload()
    page.locator("#question").fill("Règle le salon à 20 degrés")
    page.locator("#send").click()
    panel = page.locator(".confirmation-panel")
    expect(panel).to_be_visible()
    expect(panel.locator(".confirmation-field").nth(0)).to_contain_text("versatile_thermostat__set_temperature")
    expect(panel.locator(".confirmation-field").nth(1)).to_contain_text("climate.salon")
    expect(panel.locator("pre")).to_contain_text('"temperature": 20')
    expect(page.locator("#send")).to_be_disabled()
    page.locator(".confirmation-actions button").nth(0 if approved else 1).click()
    expect(page.locator(".confirmation-panel .confirmation-status")).to_contain_text(
        "Accord transmis" if approved else "Action refusée",
    )
    expect(page.locator("#send")).to_be_enabled()
    assert state["confirmation_requests"] == [{
        "confirmation_id": "confirmation-test-id", "confirmed": approved,
    }]
    page.reload()
    expect(page.locator(".confirmation-panel")).to_have_count(0)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_frontend_restores_pending_confirmation_and_blocks_ambiguous_or_expired_actions(frontend):
    page, state = frontend
    state["pending_confirmation"] = confirmation_details(target=None)
    page.reload()
    expect(page.locator(".confirmation-panel")).to_be_visible()
    expect(page.locator(".confirmation-field").nth(1)).to_contain_text("Cible non déterminée")
    expect(page.locator(".confirmation-status")).to_contain_text("cible est ambiguë")
    expect(page.locator(".confirmation-actions button").first).to_be_disabled()
    expect(page.locator("#send")).to_be_disabled()
    assert not state["confirmation_requests"]

    state["pending_confirmation"] = confirmation_details(expires_at=1)
    page.reload()
    expect(page.locator(".confirmation-status")).to_contain_text("a expiré")
    expect(page.locator(".confirmation-actions button").first).to_be_disabled()
    expect(page.locator(".confirmation-actions button").nth(1)).to_be_disabled()
    expect(page.locator("#send")).to_be_enabled()
    assert not state["confirmation_requests"]


@pytest.mark.parametrize("page", [
    {"locale": "fr-FR", "timezone_id": "Europe/Paris"},
    {"locale": "en-US", "timezone_id": "America/New_York"},
    {"locale": "en-GB", "timezone_id": "UTC"},
], indirect=True)
def test_frontend_localizes_and_restores_message_timestamps(frontend, tmp_path):
    page, state = frontend
    expect(page.locator(".message time:visible")).to_have_count(0)
    instants = ["2026-10-25T00:59:00Z", "2026-10-25T01:01:00Z"]
    for message, instant in zip(state["messages"], instants):
        message["created_at"] = instant
    page.reload()
    expected = page.evaluate("instants => instants.map(value => new Intl.DateTimeFormat(navigator.language, {dateStyle: 'short', timeStyle: 'medium'}).format(new Date(value)))", instants)
    expect(page.locator(".message time")).to_have_text(expected)
    assert page.locator(".message-label").first.evaluate("label => label.firstElementChild.tagName") == "TIME"
    zone = page.evaluate("Intl.DateTimeFormat().resolvedOptions().timeZone")
    hours = page.evaluate("instants => instants.map(value => new Date(value).getHours())", instants)
    assert hours == {"Europe/Paris": [2, 2], "America/New_York": [20, 21], "UTC": [0, 1]}[zone]
    state["stream_events"] = [
        {"type": "delta", "text": "Premier. ", "created_at": instants[0]},
        {"type": "delta", "text": "Dernier.", "created_at": instants[1]},
    ]
    page.locator("#question").fill("Question horodatée")
    page.locator("#send").click()
    expect(page.locator(".message-state").last).to_have_text("")
    expect(page.locator(".message.assistant time").last).to_have_text(expected[0])
    before = page.locator(".message time").all_text_contents()
    page.reload()
    expect(page.locator(".message time")).to_have_text(before)
    open_settings(page)
    page.locator("#back").click()
    expect(page.locator(".message time")).to_have_text(before)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if zone == "Europe/Paris":
        screenshot = tmp_path / "timestamps.png"
        page.screenshot(path=str(screenshot), full_page=True)
        print(f"Capture horodatages : {screenshot}")
    saved_instants = page.locator(".message time").evaluate_all("elements => elements.map(element => element.dateTime)")
    changed_context = page.context.browser.new_context(locale=page.evaluate("navigator.language"), timezone_id="Asia/Tokyo", viewport=page.viewport_size)
    try:
        changed_page = changed_context.new_page()
        changed_page.route("http://assistant.test/**", state["handle"])
        changed_page.goto("http://assistant.test/")
        localized = changed_page.evaluate("instants => instants.map(value => new Intl.DateTimeFormat(navigator.language, {dateStyle: 'short', timeStyle: 'medium'}).format(new Date(value)))", saved_instants)
        expect(changed_page.locator(".message time")).to_have_text(localized)
        assert changed_page.locator(".message time").evaluate_all("elements => elements.map(element => element.dateTime)") == saved_instants
    finally:
        changed_context.close()


@pytest.mark.parametrize("count", [0, 12])
def test_frontend_initial_inventory_is_safe_restored_and_not_duplicated(frontend, count, tmp_path):
    page, state = frontend
    state["messages"] = []
    state["prefix"] = "/api/hassio_ingress/test-session"
    state["inventory_payload"] = {"count": count, "created_at": "2026-11-08T11:00:00+00:00", "thermostats": [
        {"entity_id": f"climate.test_{index}", "name": "<img src=x onerror=alert(1)>" if index == 0 else f"Thermostat {index}"}
        for index in range(count)
    ]}
    page.goto("http://assistant.test" + state["prefix"] + "/")
    expect(page.locator("#inventory summary")).to_contain_text(f"{count} VTherm")
    expect(page.locator("#inventory li")).to_have_count(count)
    expect(page.locator("#send")).to_be_enabled()
    assert page.locator("#inventory img, #inventory script").count() == 0
    if count:
        expect(page.locator("#inventory code").first).to_have_text("climate.test_0")
        expect(page.locator("#inventory li span").first).to_contain_text("<img")
    calls = sum(path == "/api/conversation/inventory" for _method, path, _body in state["calls"])
    page.reload()
    expect(page.locator("#inventory li")).to_have_count(count)
    expect(page.locator("#inventory")).to_have_count(1)
    assert sum(path == "/api/conversation/inventory" for _method, path, _body in state["calls"]) == calls
    page.locator("#new").click()
    expect(page.locator("#new")).to_be_enabled()
    expect(page.locator("#inventory summary")).to_contain_text(f"{count} VTherm")
    assert sum(path == "/api/conversation/inventory" for _method, path, _body in state["calls"]) == calls + 1
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if count:
        state["inventory"]["thermostats"][0]["name"] = "Thermostat salon (test)"
        page.reload()
        expect(page.locator("#inventory li span").first).to_have_text("Thermostat salon (test)")
        inventory_image = tmp_path / "inventory.png"
        page.screenshot(path=str(inventory_image), full_page=True)
        open_settings(page)
        expect(page.locator("#model-catalog")).to_be_enabled()
        catalog_image = tmp_path / "catalog.png"
        page.screenshot(path=str(catalog_image), full_page=True)
        print(f"Captures inventaire et catalogue : {inventory_image} {catalog_image}")


def test_frontend_initial_inventory_errors_can_be_retried(frontend):
    page, state = frontend
    state["messages"] = []
    page.reload()
    expect(page.locator("#inventory")).to_contain_text("jeton Home Assistant")
    expect(page.locator("#send")).to_be_enabled()
    state["inventory_payload"] = {"count": 0, "thermostats": [], "created_at": "2026-11-08T11:00:00+00:00"}
    page.get_by_role("button", name="Réessayer l'inventaire", exact=True).click()
    expect(page.locator("#inventory")).to_contain_text("Aucun VTherm interrogeable")
    expect(page.locator("#inventory")).to_have_attribute("data-state", "ready")


def test_frontend_initial_inventory_ignores_late_deleted_conversation(frontend):
    page, state = frontend
    state["messages"] = []
    state["hold_inventory"] = True
    page.reload()
    expect(page.locator("#inventory")).to_contain_text("Chargement")
    expect(page.locator("#send")).to_be_disabled()
    old_request = state["pending_inventory"]
    state["hold_inventory"] = False
    state["inventory_payload"] = {"count": 1, "thermostats": [{"entity_id": "climate.new", "name": "Nouvelle liste"}]}
    page.locator("#new").click()
    expect(page.locator("#inventory")).to_contain_text("Nouvelle liste")
    old_request.fulfill(json={"inventory": {"count": 1, "thermostats": [{"entity_id": "climate.old", "name": "Ancienne liste"}]}, "version": 1})
    expect(page.locator("#inventory li")).to_have_count(1)
    expect(page.locator("#inventory code")).to_have_text("climate.new")
    assert "Ancienne liste" not in page.locator("#inventory").inner_text()


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
    expect(page.locator("#model-catalog")).to_be_enabled()
    expect(page.locator("#model-catalog option").last).to_contain_text(provider_name + "-catalog-model")
    expect(page.locator("#model-catalog")).to_have_value("")
    expect(page.locator("#model")).to_have_value("model-test")
    page.locator("#model-catalog").select_option(provider_name + "-catalog-model")
    expect(page.locator("#model")).to_have_value(provider_name + "-catalog-model")
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


@pytest.mark.parametrize("failure", ["network", "http"])
def test_frontend_model_catalog_errors_preserve_manual_configuration(frontend, failure):
    page, state = frontend
    state["failures"][("GET", "/api/models")] = failure
    open_settings(page)
    expect(page.locator("#catalog-feedback")).to_contain_text("réessayez")
    expect(page.locator("#model")).to_have_value("model-test")
    assert "FAKE_SECRET_DO_NOT_DISPLAY" not in page.locator("body").inner_text()
    state["failures"].clear()
    page.locator("#catalog-retry").click()
    expect(page.locator("#catalog-feedback")).to_have_text("Compatibilité non vérifiée.")
    expect(page.locator("#model")).to_have_value("model-test")


def test_frontend_model_catalog_ignores_late_results_and_identifies_fallback(frontend):
    page, state = frontend
    state["hold_catalog"] = "gemini"
    open_settings(page)
    expect(page.locator("#catalog-feedback")).to_contain_text("Chargement")
    state["catalogs"] = {"openai": {"provider": "openai", "source": "suggestions", "complete": False,
                                   "models": [{"id": "suggestion", "compatibility": "unverified"}], "message": "Sans garantie d'accès."}}
    page.locator("#provider").select_option("openai")
    expect(page.locator("#catalog-feedback")).to_contain_text("Suggestions prédéfinies")
    state["pending_catalog"].fulfill(json={"provider": "gemini", "source": "dynamic", "complete": True,
                                           "models": [{"id": "late-model", "compatibility": "unverified"}]})
    expect(page.locator("#model-catalog option").last).to_have_attribute("value", "suggestion")
    expect(page.locator("#model")).to_have_value("model-test")
    assert page.locator("#model-catalog").inner_text().find("late-model") == -1


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


def test_frontend_renders_markdown_tables_in_history_and_stream(frontend):
    page, state = frontend
    markdown = (
        "Inventaire disponible :\n"
        "| Nom | Entité | Type |\n"
        "| :--- | --- | ---: |\n"
        "| **Thermostat salon** | `climate.salon_thermostat_salon` | over_climate |\n"
        "| Sdb \\| étage | `climate.thermostat_sdb` | over_climate |\n\n"
        "<img src=x onerror=alert(1)>"
    )
    state["prefix"] = "/api/hassio_ingress/test-session"
    state["messages"] = [{"role": "assistant", "text": markdown}]
    page.goto("http://assistant.test" + state["prefix"] + "/")

    def check_table():
        body = page.locator(".message.assistant .message-text").last
        expect(body.locator("thead th")).to_have_text(["Nom", "Entité", "Type"])
        expect(body.locator("tbody tr")).to_have_count(2)
        expect(body.locator("tbody tr").first.locator("code")).to_have_text("climate.salon_thermostat_salon")
        expect(body.locator("tbody tr").last.locator("td").first).to_have_text("Sdb | étage")
        expect(body.locator("strong")).to_have_text("Thermostat salon")
        assert body.locator("img, script").count() == 0
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

    check_table()
    state["stream_text"] = markdown
    state["stream_events"] = [{"type": "delta", "text": markdown[:70]}, {"type": "delta", "text": markdown[70:]}]
    page.locator("#question").fill("Liste les thermostats")
    page.locator("#send").click()
    check_table()
    page.reload()
    check_table()


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
    timestamps = {}
    observed_requests = []
    tool = Tool(name="versatile_thermostat__list_vtherms", inputSchema={"type": "object"})

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
            part = types.Part(function_call=types.FunctionCall(name=tool.name, args={}))
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
        stack.enter_context(patch("vtherm_assistant.ha_mcp.HomeAssistantMCP.list_tools", new_callable=AsyncMock, return_value=[tool]))
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
            timestamps[user_id] = page.locator(".message time").all_text_contents()
        restarted = create_app("ingress", verify_admin=verify_admin, data_dir=directory)
        active["client"] = stack.enter_context(TestClient(restarted, client=(SUPERVISOR_ADDRESS, 12345)))
        for user_id in ("alice", "bob"):
            active["user"] = user_id
            page.reload()
            expect(page.locator(".message")).to_have_count(2)
            expect(page.locator(".message time")).to_have_text(timestamps[user_id])
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