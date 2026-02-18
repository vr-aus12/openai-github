from __future__ import annotations

import copy
import re
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Callable

from .exceptions import RegistrationError, RoutingError, ValidationError
from .models import Connectivity, FieldMap, IntegrationMap, MessageDefinition, PartnerApplication


class EnterpriseIPaaSPlatform:
    """Message-first iPaaS platform focused on enterprise integration complexity."""

    def __init__(self) -> None:
        self._messages: dict[str, MessageDefinition] = {}
        self._applications: dict[str, PartnerApplication] = {}
        self._maps: dict[str, IntegrationMap] = {}
        self._transformers: dict[str, Callable[[Any], Any]] = {
            "uppercase": lambda value: value.upper() if isinstance(value, str) else value,
            "lowercase": lambda value: value.lower() if isinstance(value, str) else value,
            "string": lambda value: "" if value is None else str(value),
        }

    @staticmethod
    def _message_key(name: str, version: str) -> str:
        return f"{name}:{version}"

    @staticmethod
    def _map_key(name: str, version: str) -> str:
        return f"{name}:{version}"

    def register_transform(self, name: str, func: Callable[[Any], Any]) -> None:
        self._transformers[name] = func

    def register_message(self, message: MessageDefinition, *, overwrite: bool = False) -> str:
        key = self._message_key(message.name, message.version)
        if key in self._messages and not overwrite:
            raise RegistrationError(f"Message already exists: {key}")
        self._messages[key] = message
        return key

    def register_application(self, app: PartnerApplication, *, overwrite: bool = False) -> None:
        if app.name in self._applications and not overwrite:
            raise RegistrationError(f"Application already exists: {app.name}")
        self._applications[app.name] = app

    def add_connectivity(self, app_name: str, connectivity: Connectivity) -> None:
        app = self._applications.get(app_name)
        if app is None:
            raise RegistrationError(f"Unknown application: {app_name}")
        app.connectivities.append(connectivity)
        app.connectivities.sort(key=lambda item: item.priority)

    def resolve_connectivity(self, app_name: str, protocol: str | None = None) -> Connectivity:
        app = self._applications.get(app_name)
        if app is None:
            raise RoutingError(f"Unknown application: {app_name}")

        candidates = [c for c in app.connectivities if c.active]
        if protocol is not None:
            candidates = [c for c in candidates if c.protocol == protocol]

        if not candidates:
            raise RoutingError(f"No active connectivity found for app={app_name} protocol={protocol}")
        return sorted(candidates, key=lambda item: item.priority)[0]

    def register_map(self, integration_map: IntegrationMap, *, overwrite: bool = False) -> str:
        key = self._map_key(integration_map.name, integration_map.version)
        if key in self._maps and not overwrite:
            raise RegistrationError(f"Integration map already exists: {key}")
        if integration_map.source_message not in self._messages:
            raise RegistrationError(f"Unknown source message: {integration_map.source_message}")
        if integration_map.target_message not in self._messages:
            raise RegistrationError(f"Unknown target message: {integration_map.target_message}")
        if integration_map.source_app not in self._applications:
            raise RegistrationError(f"Unknown source application: {integration_map.source_app}")
        if integration_map.target_app not in self._applications:
            raise RegistrationError(f"Unknown target application: {integration_map.target_app}")

        self._maps[key] = integration_map
        return key

    def validate_message_payload(self, message_key: str, payload: dict[str, Any]) -> None:
        message = self._messages[message_key]
        required = self._required_fields(message)
        missing = [field for field in required if self._extract_value(payload, field) is None]
        if missing:
            raise ValidationError(f"Payload is missing required fields: {missing}")

    def _required_fields(self, message: MessageDefinition) -> list[str]:
        if message.schema_type == "json_schema":
            if not isinstance(message.schema, dict):
                raise ValidationError("json_schema message must provide dictionary schema")
            return list(message.schema.get("required", []))

        if message.schema_type == "manual":
            if not isinstance(message.schema, dict):
                raise ValidationError("manual message must provide dictionary schema")
            return list(message.schema.get("required_fields", []))

        if message.schema_type == "xsd":
            if not isinstance(message.schema, str):
                raise ValidationError("xsd message must provide schema as string")
            return re.findall(r'name="([a-zA-Z0-9_.-]+)"', message.schema)

        return []

    def route(self, map_name: str, payload: dict[str, Any], *, map_version: str = "1.0") -> dict[str, Any]:
        map_key = self._map_key(map_name, map_version)
        integration_map = self._maps.get(map_key)
        if integration_map is None:
            raise RoutingError(f"Unknown integration map: {map_key}")
        if not integration_map.enabled:
            raise RoutingError(f"Integration map is disabled: {map_key}")

        source = self._messages[integration_map.source_message]
        self.validate_message_payload(self._message_key(source.name, source.version), payload)

        output: dict[str, Any] = {}
        for mapping in integration_map.mappings:
            self._apply_mapping(payload, output, mapping)

        self.validate_message_payload(integration_map.target_message, output)

        target_connectivity = self.resolve_connectivity(integration_map.target_app)
        return {
            "map": map_key,
            "target_app": integration_map.target_app,
            "target_connectivity": asdict(target_connectivity),
            "routed_at": datetime.now(timezone.utc).isoformat(),
            "payload": output,
        }

    def _apply_mapping(self, source: dict[str, Any], target: dict[str, Any], mapping: FieldMap) -> None:
        value = self._extract_value(source, mapping.source_path)
        if value is None and mapping.default_value is not None:
            value = copy.deepcopy(mapping.default_value)

        if mapping.transform:
            transformer = self._transformers.get(mapping.transform)
            if transformer is None:
                raise RoutingError(f"Unknown transform: {mapping.transform}")
            value = transformer(value)

        self._insert_value(target, mapping.target_path, value)

    @staticmethod
    def _extract_value(doc: dict[str, Any], path: str) -> Any:
        node: Any = doc
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return copy.deepcopy(node)

    @staticmethod
    def _insert_value(doc: dict[str, Any], path: str, value: Any) -> None:
        parts = path.split(".")
        node = doc
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    def summary(self) -> dict[str, Any]:
        return {
            "messages": [asdict(v) for v in self._messages.values()],
            "applications": [asdict(v) for v in self._applications.values()],
            "maps": [asdict(v) for v in self._maps.values()],
            "transformers": sorted(self._transformers.keys()),
        }
