import json
import logging
import math
import secrets as token_secrets
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from google.adk.tools import BaseTool, ToolContext
from google.genai import types
from jsonschema import Draft202012Validator, FormatChecker, SchemaError, ValidationError
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, Tool

from .oauth import _validate_base_url, current_admin_for_url
from .redaction import log_failure, protect_logs, redact_data
from .storage import SecretStore


_LOGGER = logging.getLogger(__name__)
HISTORY_TOOL_NAMES = frozenset({
    "versatile_thermostat__get_history",
    "assist__versatile_thermostat__get_history",
})
HISTORY_MAX_PERIOD = timedelta(days=14)
HISTORY_MAX_PAGE_SIZE = 500
TOOL_RESPONSE_MAX_ITEMS = 100
TOOL_RESPONSE_MAX_TEXT = 2048
TOOL_RESPONSE_MAX_BYTES = 64 * 1024
HISTORY_ERROR_CODES = frozenset({
    "invalid_parameters", "entity_not_exposed", "read_permission_denied", "recorder_unavailable",
    "timezone_required", "invalid_period_max_14_days", "future_period", "recorder_query_failed",
})
VTherm_DIAGNOSTIC_TOOL_NAMES = frozenset({
    "versatile_thermostat__get_logs",
    "assist__versatile_thermostat__get_logs",
    "versatile_thermostat__get_plugins",
    "assist__versatile_thermostat__get_plugins",
})
LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR"})


READ_ONLY_TOOL_DEFINITIONS = {
    "homeassistant__GetLiveContext": (
        "Lire le contexte global sans filtre, ou l'état ciblé d'une entité liée au VTherm sélectionné via son entity_id exact dans name.",
        {"type": "object", "properties": {"name": {"type": "string", "description": "Nom, alias ou entity_id exact pour cibler une entité."}, "area": {"type": "string"},
         "domain": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}}},
    ),
    "versatile_thermostat__list_vtherms": (
        "Lister les thermostats VTherm exposés à Assist.", {"type": "object", "properties": {}},
    ),
    "versatile_thermostat__get_status": (
        "Lire l'état courant d'un thermostat VTherm exposé.",
        {"type": "object", "properties": {"entity_id": {"type": "string"}}, "required": ["entity_id"]},
    ),
    "versatile_thermostat__diagnose": (
        "Lire le diagnostic courant d'un thermostat VTherm exposé.",
        {"type": "object", "properties": {"entity_id": {"type": "string"}}, "required": ["entity_id"]},
    ),
    "versatile_thermostat__get_history": (
        "Lire l'historique Recorder d'un climate VTherm exposé, sur une période zonée de 14 jours maximum et par pages de 500 états maximum.",
        {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "entity_id exact d'un climate VTherm exposé."},
                "start_time": {"type": "string", "format": "date-time"},
                "end_time": {"type": "string", "format": "date-time"},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": HISTORY_MAX_PAGE_SIZE, "default": HISTORY_MAX_PAGE_SIZE},
            },
            "required": ["entity_id", "start_time", "end_time"],
        },
    ),
    "versatile_thermostat__get_logs": (
        "Lire les journaux du collecteur VTherm pour un seul thermostat sélectionné, avec filtres temporels et niveau vérifiés.",
        {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "entity_id exact du climate VTherm sélectionné."},
                "start_time": {"type": "string", "format": "date-time"},
                "end_time": {"type": "string", "format": "date-time"},
                "min_level": {"type": "string", "enum": sorted(LOG_LEVELS), "default": "DEBUG"},
            },
            "required": ["entity_id"],
            "additionalProperties": False,
        },
    ),
    "versatile_thermostat__get_plugins": (
        "Lire les plugins et diagnostics publiés pour un seul thermostat VTherm sélectionné.",
        {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "entity_id exact du climate VTherm sélectionné."},
            },
            "required": ["entity_id"],
            "additionalProperties": False,
        },
    ),
}
READ_ONLY_TOOL_DEFINITIONS.update({
    f"assist__{name}": READ_ONLY_TOOL_DEFINITIONS[name]
    for name in (
        "versatile_thermostat__list_vtherms",
        "versatile_thermostat__get_status",
        "versatile_thermostat__diagnose",
        "versatile_thermostat__get_history",
        "versatile_thermostat__get_logs",
        "versatile_thermostat__get_plugins",
    )
})
READ_ONLY_TOOLS = frozenset(READ_ONLY_TOOL_DEFINITIONS)
GLOBAL_CONTEXT_TOOL_NAMES = frozenset({"homeassistant__GetLiveContext"})
VTHERM_STATE_TOOL_NAMES = frozenset({
    "versatile_thermostat__get_status",
    "assist__versatile_thermostat__get_status",
    "versatile_thermostat__diagnose",
    "assist__versatile_thermostat__diagnose",
})


class MCPConnectionError(RuntimeError):
    pass


class MCPToolDenied(RuntimeError):
    pass


def _tool_result_payload(result: CallToolResult) -> dict[str, Any] | None:
    if result.isError:
        return None
    if isinstance(result.structuredContent, dict):
        return result.structuredContent
    text = "".join(content.text for content in result.content if content.type == "text")
    try:
        payload = json.loads(text)
    except (ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def _is_vtherm_tool_name(name: str) -> bool:
    return name.startswith(("versatile_thermostat__", "assist__versatile_thermostat__"))


def _is_read_only_vtherm_tool(tool: Tool) -> bool:
    annotations = tool.annotations
    return (
        _is_vtherm_tool_name(tool.name)
        and annotations is not None
        and annotations.readOnlyHint is True
        and annotations.destructiveHint is False
    )


def _validate_dynamic_tool_schema(schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise MCPToolDenied("Schéma d'outil VTherm non représentable")
    try:
        if len(json.dumps(schema, separators=(",", ":")).encode()) > 16_384:
            raise MCPToolDenied("Schéma d'outil VTherm trop volumineux")
        Draft202012Validator.check_schema(schema)
    except (TypeError, ValueError, SchemaError):
        raise MCPToolDenied("Schéma d'outil VTherm invalide") from None

    supported_keywords = {
        "type", "title", "description", "default", "properties", "required", "items", "enum",
        "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minLength", "maxLength",
        "minItems", "maxItems", "additionalProperties",
    }
    supported_types = {"object", "string", "number", "integer", "boolean", "array"}

    def check_schema_node(node: Any) -> None:
        if not isinstance(node, dict) or set(node) - supported_keywords or node.get("type") not in supported_types:
            raise MCPToolDenied("Schéma d'outil VTherm non représentable")
        if node.get("additionalProperties", False) is not False:
            raise MCPToolDenied("Schéma d'outil VTherm non représentable")
        properties = node.get("properties", {})
        if not isinstance(properties, dict):
            raise MCPToolDenied("Schéma d'outil VTherm non représentable")
        required = node.get("required", [])
        if not isinstance(required, list) or any(not isinstance(key, str) or key not in properties for key in required):
            raise MCPToolDenied("Schéma d'outil VTherm non représentable")
        for property_schema in properties.values():
            check_schema_node(property_schema)
        if "items" in node:
            check_schema_node(node["items"])

    check_schema_node(schema)
    return schema


def _provider_tool_schema(schema: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in schema.items() if key not in {"additionalProperties", "title", "default"}}
    if isinstance(schema.get("properties"), dict):
        result["properties"] = {
            name: _provider_tool_schema(property_schema)
            for name, property_schema in schema["properties"].items()
        }
    if isinstance(schema.get("items"), dict):
        result["items"] = _provider_tool_schema(schema["items"])
    return result


def _validate_dynamic_tool_arguments(schema: dict[str, Any], arguments: Any) -> None:
    if not isinstance(arguments, dict):
        raise MCPToolDenied("Paramètres VTherm invalides")
    try:
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(arguments)
    except (SchemaError, ValidationError, TypeError, ValueError):
        raise MCPToolDenied("Paramètres VTherm invalides") from None


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return value[:TOOL_RESPONSE_MAX_TEXT]
    return None


def _safe_string_list(value: Any, *, limit: int = TOOL_RESPONSE_MAX_ITEMS) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item[:TOOL_RESPONSE_MAX_TEXT] for item in value[:limit] if isinstance(item, str)]


def _project_scalar_fields(source: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(source, dict):
        return {}
    return {
        field: safe_value
        for field in fields
        if field in source and (safe_value := _safe_scalar(source[field])) is not None
    }


def _project_reason_fields(source: Any) -> dict[str, Any]:
    fields = (
        "messages", "hvac_off_reason", "hvac_mode_reason", "should_device_be_active",
        "device_actives", "unavailable_underlying_entities", "temperature_slope",
        "is_sleeping", "is_recalculate_scheduled",
    )
    result = _project_scalar_fields(source, fields)
    if isinstance(source, dict):
        for field in ("messages", "device_actives", "unavailable_underlying_entities"):
            if field in source:
                result[field] = _safe_string_list(source[field])
    return result


_COMPACT_STATE_FIELDS = (
    "entity_id", "name", "hvac_mode", "hvac_action", "preset_mode", "current_temperature",
    "target_temperature", "target_minus_current", "min_temperature", "max_temperature",
    "target_temperature_step", "thermostat_type",
)
_CLIMATE_ATTRIBUTE_FIELDS = (
    "friendly_name", "hvac_action", "preset_mode", "current_temperature", "temperature",
    "min_temp", "temp_min", "max_temp", "temp_max", "target_temp_step",
)
_FEATURE_FLAG_FIELDS = (
    "is_presence_configured", "is_motion_configured", "is_power_configured",
    "is_window_configured", "is_window_auto_configured", "is_safety_configured",
    "is_auto_start_stop_configured", "is_lock_configured", "is_heating_failure_detection_configured",
    "is_over_switch", "is_over_valve", "is_over_climate", "is_over_climate_valve",
)


def _project_compact_state(source: Any) -> dict[str, Any]:
    result = _project_scalar_fields(source, _COMPACT_STATE_FIELDS)
    if isinstance(source, dict):
        for field in ("hvac_modes", "preset_modes", "messages"):
            if field in source:
                result[field] = _safe_string_list(source[field])
    return result


def _project_status(payload: dict[str, Any]) -> dict[str, Any]:
    result = _project_scalar_fields(payload, ("entity_id", "state", "last_changed", "last_updated"))
    attributes = payload.get("attributes")
    if isinstance(attributes, dict):
        projected = _project_scalar_fields(attributes, _CLIMATE_ATTRIBUTE_FIELDS)
        for field in ("hvac_modes", "preset_modes"):
            if field in attributes:
                projected[field] = _safe_string_list(attributes[field])
        flags = _project_scalar_fields(attributes, _FEATURE_FLAG_FIELDS)
        projected.update({key: value for key, value in flags.items() if isinstance(value, bool)})
        if isinstance(attributes.get("specific_states"), dict):
            projected["specific_states"] = _project_reason_fields(attributes["specific_states"])
        result["attributes"] = projected
    return result


def _project_diagnose(payload: dict[str, Any]) -> dict[str, Any]:
    result = _project_scalar_fields(
        payload, ("entity_id", "name", "availability", "last_changed", "last_updated"),
    )
    if "current" in payload:
        result["current"] = _project_compact_state(payload["current"])
    if isinstance(payload.get("reasons"), dict):
        result["reasons"] = _project_reason_fields(payload["reasons"])
    if isinstance(payload.get("feature_flags"), dict):
        flags = _project_scalar_fields(payload["feature_flags"], _FEATURE_FLAG_FIELDS)
        result["feature_flags"] = {key: value for key, value in flags.items() if isinstance(value, bool)}
    sections = payload.get("sections")
    if isinstance(sections, dict) and isinstance(sections.get("specific_states"), dict):
        result["sections"] = {"specific_states": _project_reason_fields(sections["specific_states"])}
    return result


def _project_history(payload: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "entity_id", "start_time", "end_time", "timezone", "offset", "total_rows",
        "next_offset", "pagination_complete", "state_changed",
    )
    result = _project_scalar_fields(payload, fields)
    result["semantics"] = (
        "États et attributs Recorder, pas des échantillons réguliers. Les champs nuls ne sont pas enregistrés ; "
        "la rétention, les exclusions et les lacunes limitent la couverture. Ne pas reconstruire les valeurs absentes."
    )
    rows = payload.get("rows")
    if isinstance(rows, list):
        projected_rows = []
        for row in rows[:TOOL_RESPONSE_MAX_ITEMS]:
            if not isinstance(row, dict):
                continue
            projected_row = _project_scalar_fields(row, ("timestamp", "state"))
            attributes = row.get("attributes")
            if isinstance(attributes, dict):
                projected_row["attributes"] = {
                    field: _safe_scalar(attributes[field])
                    for field in (
                        "current_temperature", "temperature", "target_temp_low", "target_temp_high",
                        "hvac_action", "preset_mode", "unit_of_measurement",
                    )
                    if field in attributes and _safe_scalar(attributes[field]) is not None
                }
            projected_rows.append(projected_row)
        result["rows"] = projected_rows
        offset = result.get("offset")
        total_rows = result.get("total_rows")
        if len(rows) > len(projected_rows) and type(offset) is int:
            result["next_offset"] = offset + len(projected_rows)
            result["pagination_complete"] = False
            result["projection_truncated"] = True
        if type(offset) is int and type(total_rows) is int:
            result["pagination_complete"] = offset + len(projected_rows) >= total_rows
            result["next_offset"] = None if result["pagination_complete"] else offset + len(projected_rows)
    return result


def _project_errors(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    fields = ("code", "scope", "plugin_id", "source", "field", "message_fr", "message_en")
    return [_project_scalar_fields(item, fields) for item in value[:TOOL_RESPONSE_MAX_ITEMS] if isinstance(item, dict)]


def _project_logs(payload: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "schema_version", "status", "entity_id", "queried_at", "read_started_at", "read_finished_at",
        "limit", "selection_policy", "order", "selected_count", "returned_count", "omitted_count",
        "limit_exceeded", "truncated", "history_completeness",
    )
    result = _project_scalar_fields(payload, fields)
    if isinstance(payload.get("target"), dict):
        result["target"] = _project_scalar_fields(payload["target"], ("config_entry_id", "unique_id", "name"))
    if isinstance(payload.get("filters"), dict):
        result["filters"] = _project_scalar_fields(
            payload["filters"],
            ("requested_start_time", "requested_end_time", "start_time", "end_time", "normalization_policy",
             "normalization_path", "min_level", "thermostat_name"),
        )
    if isinstance(payload.get("returned_range"), dict):
        result["returned_range"] = _project_scalar_fields(
            payload["returned_range"], ("first", "last", "minimum", "maximum"),
        )
    result["warnings"] = _safe_string_list(payload.get("warnings"))
    result["errors"] = _project_errors(payload.get("errors"))
    entries = payload.get("entries")
    if isinstance(entries, list):
        selected = entries[:TOOL_RESPONSE_MAX_ITEMS]
        result["entries"] = [
            _project_scalar_fields(entry, ("timestamp", "level", "level_name", "logger_name", "message"))
            for entry in selected if isinstance(entry, dict)
        ]
        extra = max(0, len(entries) - len(selected))
        if extra:
            result["projection_truncated"] = True
            result["omitted_count"] = (result.get("omitted_count") or 0) + extra
            result["truncated"] = True
        result["returned_count"] = len(result["entries"])
    return result


_PLUGIN_FACT_FIELDS = (
    "configured", "selected", "loaded", "handler_loaded", "configuration_applied", "enabled",
    "operational_ready", "active", "available", "declared_enabled", "runtime_configuration_present",
)
_PLUGIN_VALUE_FIELDS = (
    "phase", "mode", "hysteresis_state", "is_active", "hvac_mode", "on_percent", "last_reason",
    "current_cycle_percent", "next_cycle_percent", "pi_percent", "ff_percent", "hold_percent",
    "sensor", "error", "integral_error", "integral_mode", "integral_hold_mode", "available",
    "current_level", "current_level_index", "observed_cycle", "observed_phase", "pending_command",
    "command_error", "heating_failure_state", "cooling_failure_state", "heating_failure_threshold",
    "cooling_failure_threshold", "detection_delay_min", "temperature_change_tolerance", "status",
    "raw_status", "stop_underlyings", "bypass", "pending_status", "waiting_for_vtherm_start",
    "retry_pending", "enabled", "current_gap", "selected_fan_mode", "sent_fan_mode", "rest_mode",
)


def _project_facts(source: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(source, dict):
        return {}
    facts = {}
    for field in fields:
        fact = source.get(field)
        if not isinstance(fact, dict):
            continue
        projected = _project_scalar_fields(fact, ("value", "knowledge", "source", "scope", "reason"))
        if projected:
            facts[field] = projected
    return facts


def _project_plugins(payload: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "schema_version", "status", "entity_id", "queried_at", "read_started_at", "read_finished_at",
        "identified_configured_plugin_count", "configured_plugin_count", "configured_plugin_count_reason",
        "proven_unresolved_selection_count", "diagnostics_status", "state_minimum_status",
    )
    result = _project_scalar_fields(payload, fields)
    if isinstance(payload.get("target"), dict):
        result["target"] = _project_scalar_fields(payload["target"], ("config_entry_id", "unique_id", "name"))
    plugins = payload.get("plugins")
    if isinstance(plugins, list):
        projected_plugins = []
        for plugin in plugins[:TOOL_RESPONSE_MAX_ITEMS]:
            if not isinstance(plugin, dict):
                continue
            item = _project_scalar_fields(plugin, ("plugin_id", "domain", "config_entry_id", "label", "state_minimum_status"))
            item["categories"] = _safe_string_list(plugin.get("categories"))
            item["facts"] = _project_facts(plugin.get("facts"), _PLUGIN_FACT_FIELDS)
            links = plugin.get("links")
            if isinstance(links, list):
                item["links"] = []
                for link in links[:TOOL_RESPONSE_MAX_ITEMS]:
                    if not isinstance(link, dict):
                        continue
                    projected_link = _project_scalar_fields(
                        link, ("relation", "target", "source", "algorithm", "physical_climate"),
                    )
                    if isinstance(link.get("applies_to_target"), dict):
                        projected_link["applies_to_target"] = _project_facts(
                            {"applies_to_target": link["applies_to_target"]}, ("applies_to_target",),
                        ).get("applies_to_target", {})
                    item["links"].append(projected_link)
            diagnostic = plugin.get("diagnostics")
            if isinstance(diagnostic, dict):
                projected_diagnostic = _project_scalar_fields(diagnostic, ("status", "producer"))
                projected_diagnostic["reasons"] = _safe_string_list(diagnostic.get("reasons"))
                projected_diagnostic["values"] = _project_scalar_fields(diagnostic.get("values"), _PLUGIN_VALUE_FIELDS)
                sources = diagnostic.get("sources")
                if isinstance(sources, list):
                    source_fields = (
                        "source_entity_id", "attribute_path", "state_last_updated", "state_last_changed",
                        "observed_at", "measurement_at", "availability", "restoration",
                    )
                    projected_diagnostic["sources"] = [
                        _project_scalar_fields(source, source_fields)
                        for source in sources[:TOOL_RESPONSE_MAX_ITEMS] if isinstance(source, dict)
                    ]
                item["diagnostics"] = projected_diagnostic
            projected_plugins.append(item)
        result["plugins"] = projected_plugins
        if len(plugins) > len(projected_plugins):
            result["projection_truncated"] = True
    result["errors"] = _project_errors(payload.get("errors"))
    result["warnings"] = _safe_string_list(payload.get("warnings"))
    coverage = payload.get("coverage")
    if isinstance(coverage, dict):
        result["coverage"] = _project_scalar_fields(
            coverage, ("discovery", "third_party_exhaustive", "future_plugins_discovery"),
        )
        if isinstance(coverage.get("discovery"), dict):
            result["coverage"]["discovery"] = _project_scalar_fields(coverage["discovery"], ("status",))
        categories = coverage.get("categories")
        if isinstance(categories, dict):
            result["coverage"]["categories"] = {}
            for category, category_data in categories.items():
                if category not in {"CAT-01", "CAT-02", "CAT-03", "CAT-04"} or not isinstance(category_data, dict):
                    continue
                projected_category = _project_scalar_fields(category_data, ("status",))
                projected_category["reasons"] = _safe_string_list(category_data.get("reasons"))
                integrations = category_data.get("integrations")
                if isinstance(integrations, list):
                    projected_category["integrations"] = [
                        _project_scalar_fields(integration, ("domain", "format", "version"))
                        for integration in integrations[:TOOL_RESPONSE_MAX_ITEMS] if isinstance(integration, dict)
                    ]
                result["coverage"]["categories"][category] = projected_category
    return result


def _shrink_projected(value: Any, *, item_limit: int, text_limit: int) -> Any:
    if isinstance(value, str):
        return value[:text_limit]
    if isinstance(value, list):
        return [_shrink_projected(item, item_limit=item_limit, text_limit=text_limit) for item in value[:item_limit]]
    if isinstance(value, dict):
        return {key: _shrink_projected(item, item_limit=item_limit, text_limit=text_limit) for key, item in value.items()}
    return value


def _serialize_projected(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(text.encode("utf-8")) <= TOOL_RESPONSE_MAX_BYTES:
        return text
    original_entries = payload.get("entries")
    original_rows = payload.get("rows")
    original_omitted = payload.get("omitted_count", 0)
    for item_limit, text_limit in ((20, 512), (5, 256), (1, 128)):
        reduced = _shrink_projected(payload, item_limit=item_limit, text_limit=text_limit)
        reduced["projection_truncated"] = True
        if isinstance(original_entries, list) and isinstance(reduced.get("entries"), list):
            omitted = max(0, len(original_entries) - len(reduced["entries"]))
            reduced["returned_count"] = len(reduced["entries"])
            reduced["omitted_count"] = (original_omitted if type(original_omitted) is int else 0) + omitted
            reduced["truncated"] = True
        if isinstance(original_rows, list) and isinstance(reduced.get("rows"), list):
            offset = reduced.get("offset")
            total_rows = reduced.get("total_rows")
            if type(offset) is int:
                reduced["next_offset"] = offset + len(reduced["rows"])
                reduced["pagination_complete"] = (
                    type(total_rows) is int and reduced["next_offset"] >= total_rows
                )
                if reduced["pagination_complete"]:
                    reduced["next_offset"] = None
            reduced["projection_truncated"] = True
        text = json.dumps(reduced, ensure_ascii=False, separators=(",", ":"))
        if len(text.encode("utf-8")) <= TOOL_RESPONSE_MAX_BYTES:
            return text
    fallback = {
        key: payload[key] for key in ("entity_id", "status", "queried_at", "read_started_at", "read_finished_at")
        if key in payload
    }
    fallback["projection_truncated"] = True
    fallback["detail"] = "Le résultat a été omis car il dépasse la limite de taille."
    return json.dumps(fallback, ensure_ascii=False, separators=(",", ":"))


def _redact_projected_values(value: Any, secrets: tuple[str, ...]) -> Any:
    if isinstance(value, str):
        return redact_data(value, secrets)
    if isinstance(value, list):
        return [_redact_projected_values(item, secrets) for item in value]
    if isinstance(value, dict):
        return {key: _redact_projected_values(item, secrets) for key, item in value.items()}
    return value


def _projected_result(payload: dict[str, Any], is_error: bool, secrets: tuple[str, ...]) -> dict[str, Any]:
    safe_payload = _redact_projected_values(payload, secrets)
    return {"isError": is_error, "content": [{
        "type": "text", "text": _serialize_projected(safe_payload),
    }]}


def _project_mcp_result(name: str, result: dict[str, Any], secrets: tuple[str, ...]) -> dict[str, Any]:
    if name not in VTHERM_STATE_TOOL_NAMES | VTherm_DIAGNOSTIC_TOOL_NAMES | HISTORY_TOOL_NAMES:
        return result
    payload = result.get("structuredContent")
    if not isinstance(payload, dict):
        text = "".join(
            item.get("text", "") for item in result.get("content", [])
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str)
        )
        try:
            payload = json.loads(text)
        except (ValueError, TypeError):
            payload = None
    if result.get("isError") is True:
        if name in HISTORY_TOOL_NAMES and isinstance(payload, dict):
            code = payload.get("error")
            if isinstance(code, str) and code in HISTORY_ERROR_CODES:
                safe_error = {"error": code}
                if isinstance(payload.get("entity_id"), str):
                    safe_error["entity_id"] = payload["entity_id"]
                return _projected_result(safe_error, True, secrets)
        if isinstance(payload, dict) and (name.endswith("__get_logs") or name.endswith("__get_plugins")):
            projected_error = _project_logs(payload) if name.endswith("__get_logs") else _project_plugins(payload)
            return _projected_result(projected_error, True, secrets)
        return {"isError": True, "content": [{
            "type": "text", "text": "La source a refusé la lecture ou est indisponible.",
        }]}
    if not isinstance(payload, dict):
        return {"isError": True, "content": [{
            "type": "text", "text": "La réponse source n'a pas le format diagnostique attendu.",
        }]}
    if name.endswith("__get_status"):
        projected = _project_status(payload)
    elif name.endswith("__diagnose"):
        projected = _project_diagnose(payload)
    elif name in HISTORY_TOOL_NAMES:
        projected = _project_history(payload)
    elif name.endswith("__get_logs"):
        projected = _project_logs(payload)
    else:
        projected = _project_plugins(payload)
    return _projected_result(projected, False, secrets)


class MCPRequestScope:
    def __init__(self) -> None:
        self.selected_vtherm_id: str | None = None
        self.related_entity_ids: set[str] = set()

    def validate_live_context(self, arguments: dict[str, Any]) -> None:
        if not arguments:
            return
        if set(arguments) != {"name"} or not isinstance(arguments.get("name"), str):
            raise MCPToolDenied("GetLiveContext ciblé exige uniquement l'entity_id exact d'une entité liée")
        if arguments["name"] not in self.related_entity_ids:
            raise MCPToolDenied("Entité non liée au VTherm sélectionné")

    def clear_vtherm_selection(self) -> None:
        self.selected_vtherm_id = None
        self.related_entity_ids.clear()

    def capture_vtherm(self, tool_name: str, requested_entity_id: Any, result: CallToolResult) -> None:
        self.clear_vtherm_selection()
        payload = _tool_result_payload(result)
        if (
            not isinstance(requested_entity_id, str)
            or not requested_entity_id.startswith("climate.")
            or payload is None
            or payload.get("entity_id") != requested_entity_id
        ):
            return
        self.selected_vtherm_id = requested_entity_id
        sections = payload.get("sections") if tool_name.endswith("__diagnose") else payload.get("attributes")
        if not isinstance(sections, dict):
            return
        for section_name in ("vtherm_over_switch", "vtherm_over_valve", "vtherm_over_climate"):
            section = sections.get(section_name)
            if not isinstance(section, dict):
                continue
            self._add_entity_ids(section.get("underlying_entities"))
            if section_name == "vtherm_over_climate":
                synchronization = section.get("temp_synchronisation")
                if isinstance(synchronization, dict):
                    self._add_entity_ids(synchronization.get("sync_entity_ids"))

    def _add_entity_ids(self, values: Any) -> None:
        if not isinstance(values, list):
            return
        for value in values:
            if isinstance(value, str):
                domain, separator, object_id = value.partition(".")
                if separator and domain and object_id and not any(character.isspace() for character in value):
                    self.related_entity_ids.add(value)


class MCPTool(BaseTool):
    def __init__(self, client: "HomeAssistantMCP", user_id: str, tool: Tool,
                 additional_secrets: tuple[str, ...] = (), scope: MCPRequestScope | None = None) -> None:
        if tool.name in READ_ONLY_TOOL_DEFINITIONS:
            description, schema = READ_ONLY_TOOL_DEFINITIONS[tool.name]
            dynamic_tool = None
            read_only = True
        elif _is_vtherm_tool_name(tool.name):
            schema = _provider_tool_schema(_validate_dynamic_tool_schema(tool.inputSchema))
            description = tool.description or "Outil VTherm en lecture seule."
            dynamic_tool = tool
            read_only = _is_read_only_vtherm_tool(tool)
        else:
            raise MCPToolDenied("Outil MCP non autorisé")
        super().__init__(name=tool.name, description=description)
        self.client = client
        self.user_id = user_id
        self.input_schema = schema
        self.additional_secrets = additional_secrets
        self.scope = scope or MCPRequestScope()
        self.dynamic_tool = dynamic_tool
        self.read_only = read_only

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(name=self.name, description=self.description, parameters_json_schema=self.input_schema)

    async def run_async(self, *, args: dict[str, Any], tool_context: ToolContext) -> dict[str, Any]:
        if tool_context.user_id != self.user_id:
            raise MCPToolDenied("Utilisateur MCP non autorisé")
        secrets = list(self.client.secrets.values(self.user_id)) + list(self.additional_secrets)
        if redact_data(args, secrets) != args:
            raise MCPToolDenied("Les arguments contiennent un identifiant secret")
        if self.dynamic_tool is not None and not self.read_only:
            schema = _validate_dynamic_tool_schema(self.dynamic_tool.inputSchema)
            _validate_dynamic_tool_arguments(schema, args)
            confirmation = tool_context.tool_confirmation
            if confirmation is not None and not confirmation.confirmed:
                return {"status": "cancelled", "state_changed": False}
            try:
                await self.client.validate_vtherm_write_target(self.user_id, args, self.scope)
            except MCPToolDenied:
                return {"status": "confirmation_unavailable", "state_changed": False,
                        "reason": "Une cible climate VTherm unique et exposée est requise."}
            if confirmation is None:
                function_call_id = tool_context.function_call_id
                if not function_call_id:
                    raise MCPToolDenied("Confirmation de l'appel MCP indisponible")
                payload = {
                    "user_id": self.user_id,
                    "tool_name": self.name,
                    "arguments": args,
                    "function_call_id": function_call_id,
                    "expires_at": int(time.time()) + 600,
                    "nonce": token_secrets.token_urlsafe(24),
                }
                tool_context.request_confirmation(
                    hint="Cet outil peut modifier VTherm. Vérifiez la cible et les paramètres exacts.",
                    payload=payload,
                )
                return {"status": "confirmation_required", "tool_name": self.name, "arguments": args}
            function_call_id = tool_context.function_call_id
            payload = confirmation.payload
            if (
                not function_call_id
                or not isinstance(payload, dict)
                or set(payload) != {"user_id", "tool_name", "arguments", "function_call_id", "expires_at", "nonce"}
                or payload.get("user_id") != self.user_id
                or payload.get("tool_name") != self.name
                or payload.get("function_call_id") != function_call_id
                or payload.get("arguments") != args
                or type(payload.get("expires_at")) is not int
                or payload["expires_at"] <= int(time.time())
                or not isinstance(payload.get("nonce"), str)
                or len(payload["nonce"]) < 24
            ):
                raise MCPToolDenied("Confirmation MCP invalide ou expirée")
            result = await self.client.call_vtherm_tool(
                self.user_id, self.name, args, expected_tool=self.dynamic_tool, scope=self.scope,
            )
            return redact_data(result.model_dump(mode="json", exclude_none=True), secrets)
        if self.name in GLOBAL_CONTEXT_TOOL_NAMES:
            self.scope.validate_live_context(args)
        if self.name in HISTORY_TOOL_NAMES and args.get("entity_id") != self.scope.selected_vtherm_id:
            raise MCPToolDenied("L'historique est réservé au VTherm sélectionné")
        if self.name in VTherm_DIAGNOSTIC_TOOL_NAMES and args.get("entity_id") != self.scope.selected_vtherm_id:
            raise MCPToolDenied("La lecture VTherm est réservée au thermostat sélectionné")
        if self.name in VTHERM_STATE_TOOL_NAMES:
            self.scope.clear_vtherm_selection()
        if self.dynamic_tool is None:
            result = await self.client.call_read_only_tool(self.user_id, self.name, args)
        else:
            result = await self.client.call_read_only_tool(
                self.user_id, self.name, args, expected_tool=self.dynamic_tool,
            )
        if self.name in VTHERM_STATE_TOOL_NAMES:
            self.scope.capture_vtherm(self.name, args.get("entity_id"), result)
        result_data = result.model_dump(mode="json", exclude_none=True)
        projected_tools = VTHERM_STATE_TOOL_NAMES | VTherm_DIAGNOSTIC_TOOL_NAMES | HISTORY_TOOL_NAMES
        if self.name in projected_tools:
            return _project_mcp_result(self.name, result_data, tuple(secrets))
        return redact_data(result_data, secrets)


class HomeAssistantMCP:
    def __init__(self, base_url: str, secrets: SecretStore, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = _validate_base_url(base_url, public=False)
        self.url = self.base_url + "api/mcp"
        self.secrets = secrets
        self.transport = transport

    @asynccontextmanager
    async def _session(self, user_id: str) -> AsyncIterator[ClientSession]:
        token = self.secrets.get(user_id, "home_assistant")
        if not token:
            _LOGGER.error("operation=mcp.session stage=authentication category=missing_token")
            raise MCPConnectionError("Jeton Home Assistant manquant")
        stage = "authentication"

        async def record_response(response: httpx.Response) -> None:
            if response.is_error:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as error:
                    log_failure(_LOGGER, "mcp.http", error, stage=stage)

        try:
            if await current_admin_for_url(self.base_url, token) is None:
                _LOGGER.error("operation=mcp.session stage=authentication category=permission")
                raise MCPConnectionError("Jeton Home Assistant non autorisé")
            stage = "initialize"
            async with protect_logs(self.secrets.values(user_id)), httpx.AsyncClient(
                headers={"Authorization": f"Bearer {token}"},
                timeout=httpx.Timeout(10, read=30),
                follow_redirects=False,
                trust_env=False,
                transport=self.transport,
                event_hooks={"response": [record_response]},
            ) as client:
                async with streamable_http_client(self.url, http_client=client) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        stage = "operation"
                        yield session
        except MCPToolDenied as error:
            log_failure(_LOGGER, "mcp.session", error, stage=stage)
            raise
        except ExceptionGroup as error:
            log_failure(_LOGGER, "mcp.session", error, stage=stage)
            denied, other = error.split(MCPToolDenied)
            if denied is not None and other is None:
                exception = denied.exceptions[0]
                while isinstance(exception, BaseExceptionGroup):
                    exception = exception.exceptions[0]
                raise exception from None
            raise MCPConnectionError("Connexion au serveur MCP Home Assistant impossible") from None
        except Exception as error:
            log_failure(_LOGGER, "mcp.session", error, stage=stage)
            raise MCPConnectionError("Connexion au serveur MCP Home Assistant impossible") from None

    async def check_connection(self, user_id: str) -> None:
        async with self._session(user_id):
            pass

    async def _read_only_tools(self, session: ClientSession, *, include_writes: bool = False) -> list[Tool]:
        tools: dict[str, Tool] = {}
        cursor = None
        discovered = 0
        seen_cursors: set[str] = set()
        while True:
            page = await session.list_tools(cursor=cursor)
            discovered += len(page.tools)
            for tool in page.tools:
                if tool.name in READ_ONLY_TOOLS:
                    if tool.name in tools:
                        raise MCPToolDenied("Outil MCP ambigu")
                    tools[tool.name] = tool
                elif _is_vtherm_tool_name(tool.name) and (include_writes or _is_read_only_vtherm_tool(tool)):
                    try:
                        _validate_dynamic_tool_schema(tool.inputSchema)
                    except MCPToolDenied:
                        continue
                    if tool.name in tools:
                        raise MCPToolDenied("Outil MCP ambigu")
                    tools[tool.name] = tool
            cursor = page.nextCursor
            if cursor is None:
                if not tools:
                    _LOGGER.warning("operation=mcp.discover category=no_allowed_tools discovered=%s allowed=0", discovered)
                return list(tools.values())
            if cursor in seen_cursors or len(seen_cursors) >= 100:
                raise MCPToolDenied("Pagination MCP invalide")
            seen_cursors.add(cursor)

    async def list_read_only_tools(self, user_id: str) -> list[Tool]:
        async with self._session(user_id) as session:
            return await self._read_only_tools(session)

    async def list_tools(self, user_id: str) -> list[Tool]:
        async with self._session(user_id) as session:
            return await self._read_only_tools(session, include_writes=True)

    async def tools_for(self, user_id: str, additional_secrets: tuple[str, ...] = ()) -> list[MCPTool]:
        scope = MCPRequestScope()
        return [MCPTool(self, user_id, tool, additional_secrets, scope) for tool in await self.list_tools(user_id)]

    async def inventory_for(self, user_id: str) -> dict[str, Any]:
        if not self.secrets.get(user_id, "home_assistant"):
            raise MCPConnectionError("Jeton Home Assistant manquant")
        tools = await self.list_read_only_tools(user_id)
        candidates = [tool.name for tool in tools if tool.name in {
            "versatile_thermostat__list_vtherms", "assist__versatile_thermostat__list_vtherms",
        }]
        if len(candidates) != 1:
            raise MCPToolDenied("Outil de liste VTherm absent ou ambigu")
        result = await self.call_read_only_tool(user_id, candidates[0], {})
        if result.isError:
            raise MCPConnectionError("La lecture de l'inventaire VTherm a échoué")
        payload = result.structuredContent
        if payload is None:
            try:
                texts = [content.text for content in result.content if content.type == "text"]
                payload = json.loads("".join(texts))
            except (ValueError, TypeError):
                raise MCPConnectionError("Inventaire VTherm invalide") from None
        if not isinstance(payload, dict) or not isinstance(payload.get("thermostats"), list):
            raise MCPConnectionError("Inventaire VTherm invalide")
        if type(payload.get("count")) is not int or payload["count"] != len(payload["thermostats"]):
            raise MCPConnectionError("Compte de l'inventaire VTherm incohérent")
        thermostats = []
        seen = set()
        for entry in payload["thermostats"]:
            if not isinstance(entry, dict):
                raise MCPConnectionError("Inventaire VTherm invalide")
            entity_id = entry.get("entity_id")
            name = entry.get("name") or entry.get("friendly_name") or entity_id
            if not isinstance(entity_id, str) or not entity_id.startswith("climate.") or entity_id in seen or not isinstance(name, str):
                raise MCPConnectionError("Entité de l'inventaire VTherm invalide")
            seen.add(entity_id)
            thermostats.append({"entity_id": entity_id, "name": name})
        return redact_data({
            "count": len(thermostats), "thermostats": thermostats, "tool": candidates[0],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }, self.secrets.values(user_id))

    async def _validate_history_request(self, user_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        allowed = {"entity_id", "start_time", "end_time", "offset", "limit"}
        if not isinstance(arguments, dict) or set(arguments) - allowed:
            raise MCPToolDenied("Paramètres d'historique invalides")
        entity_id = arguments.get("entity_id")
        start_time = arguments.get("start_time")
        end_time = arguments.get("end_time")
        offset = arguments.get("offset", 0)
        limit = arguments.get("limit", HISTORY_MAX_PAGE_SIZE)
        if not isinstance(entity_id, str) or not entity_id.startswith("climate."):
            raise MCPToolDenied("L'historique est réservé aux climates VTherm exposés")
        if not isinstance(start_time, str) or not isinstance(end_time, str):
            raise MCPToolDenied("Une période d'historique explicite est requise")
        try:
            start = datetime.fromisoformat(start_time)
            end = datetime.fromisoformat(end_time)
        except ValueError:
            raise MCPToolDenied("La période d'historique doit être au format ISO 8601") from None
        if start.utcoffset() is None or end.utcoffset() is None or end <= start or end - start > HISTORY_MAX_PERIOD:
            raise MCPToolDenied("La période doit être zonée, positive et limitée à 14 jours")
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= HISTORY_MAX_PAGE_SIZE:
            raise MCPToolDenied("Pagination d'historique invalide")
        inventory = await self.inventory_for(user_id)
        thermostat_ids = {item["entity_id"] for item in inventory["thermostats"]}
        if entity_id not in thermostat_ids:
            raise MCPToolDenied("L'historique est réservé à un climate VTherm exposé")
        return {
            "entity_id": entity_id,
            "start_time": start_time,
            "end_time": end_time,
            "offset": offset,
            "limit": limit,
        }

    async def call_read_only_tool(
        self, user_id: str, name: str, arguments: dict[str, Any], *, expected_tool: Tool | None = None,
    ) -> CallToolResult:
        if name not in READ_ONLY_TOOLS and (
            expected_tool is None or expected_tool.name != name or not _is_read_only_vtherm_tool(expected_tool)
        ):
            raise MCPToolDenied("Outil MCP non autorisé")
        if name in HISTORY_TOOL_NAMES:
            arguments = await self._validate_history_request(user_id, arguments)
        if name in VTherm_DIAGNOSTIC_TOOL_NAMES:
            arguments = await self._validate_diagnostic_request(user_id, name, arguments)
        async with self._session(user_id) as session:
            tools = await self._read_only_tools(session)
            discovered = next((tool for tool in tools if tool.name == name), None)
            if discovered is None:
                raise MCPToolDenied("Outil MCP indisponible")
            if name not in READ_ONLY_TOOL_DEFINITIONS:
                if not _is_read_only_vtherm_tool(discovered) or discovered.inputSchema != expected_tool.inputSchema:
                    raise MCPToolDenied("Outil MCP indisponible")
                schema = _validate_dynamic_tool_schema(discovered.inputSchema)
                _validate_dynamic_tool_arguments(schema, arguments)
            result = await session.call_tool(name, arguments)
            if result.isError:
                _LOGGER.warning("operation=mcp.call category=tool_error tool=%s", name)
            return result

    async def validate_vtherm_write_target(
        self, user_id: str, arguments: dict[str, Any], scope: MCPRequestScope,
    ) -> str:
        entity_id = arguments.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id.startswith("climate."):
            raise MCPToolDenied("Une cible VTherm explicite est requise")
        if scope.selected_vtherm_id is not None and scope.selected_vtherm_id != entity_id:
            raise MCPToolDenied("La cible ne correspond pas au VTherm sélectionné")
        inventory = await self.inventory_for(user_id)
        if entity_id not in {item["entity_id"] for item in inventory["thermostats"]}:
            raise MCPToolDenied("La cible doit être un climate VTherm exposé")
        return entity_id

    async def call_vtherm_tool(
        self, user_id: str, name: str, arguments: dict[str, Any], *, expected_tool: Tool, scope: MCPRequestScope,
    ) -> CallToolResult:
        if (
            not _is_vtherm_tool_name(name)
            or expected_tool.name != name
            or _is_read_only_vtherm_tool(expected_tool)
        ):
            raise MCPToolDenied("Outil VTherm modifiant non autorisé")
        await self.validate_vtherm_write_target(user_id, arguments, scope)
        async with self._session(user_id) as session:
            tools = await self._read_only_tools(session, include_writes=True)
            discovered = next((tool for tool in tools if tool.name == name), None)
            if (
                discovered is None
                or discovered.inputSchema != expected_tool.inputSchema
                or discovered.annotations != expected_tool.annotations
                or _is_read_only_vtherm_tool(discovered)
            ):
                raise MCPToolDenied("Outil VTherm modifiant indisponible")
            schema = _validate_dynamic_tool_schema(discovered.inputSchema)
            _validate_dynamic_tool_arguments(schema, arguments)
            result = await session.call_tool(name, arguments)
            if result.isError:
                _LOGGER.warning("operation=mcp.call category=tool_error tool=%s", name)
            return result

    async def _validate_diagnostic_request(self, user_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise MCPToolDenied("Paramètres VTherm invalides")
        is_logs = name.endswith("__get_logs")
        allowed = {"entity_id", "start_time", "end_time", "min_level"} if is_logs else {"entity_id"}
        if set(arguments) - allowed:
            raise MCPToolDenied("Paramètres VTherm invalides")
        entity_id = arguments.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id.startswith("climate."):
            raise MCPToolDenied("La cible doit être un climate VTherm")
        if is_logs:
            min_level = arguments.get("min_level", "DEBUG")
            if not isinstance(min_level, str) or min_level not in LOG_LEVELS:
                raise MCPToolDenied("Niveau de journal invalide")
            timestamps = {}
            for field in ("start_time", "end_time"):
                if field not in arguments:
                    continue
                value = arguments[field]
                if not isinstance(value, str):
                    raise MCPToolDenied("Période de journaux invalide")
                try:
                    parsed = datetime.fromisoformat(value)
                except ValueError:
                    raise MCPToolDenied("Période de journaux invalide") from None
                if parsed.utcoffset() is None:
                    raise MCPToolDenied("La période de journaux doit inclure un fuseau horaire")
                timestamps[field] = parsed
            now = datetime.now(timezone.utc)
            start = timestamps.get("start_time", timestamps.get("end_time", now) - timedelta(hours=1))
            end = timestamps.get("end_time", now)
            if end <= start:
                raise MCPToolDenied("La période de journaux doit être positive")
        inventory = await self.inventory_for(user_id)
        thermostat_ids = {item["entity_id"] for item in inventory["thermostats"]}
        if entity_id not in thermostat_ids:
            raise MCPToolDenied("La cible doit être un climate VTherm exposé")
        return dict(arguments)