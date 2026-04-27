from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

SchemaType = Literal["json_schema", "xsd", "manual"]
ProtocolType = Literal["rest", "soap", "sftp", "mq", "event_stream", "edi"]


@dataclass(slots=True)
class MessageDefinition:
    name: str
    version: str
    schema_type: SchemaType
    schema: dict[str, Any] | str
    description: str = ""


@dataclass(slots=True)
class Connectivity:
    name: str
    protocol: ProtocolType
    endpoint: str
    security: dict[str, Any] = field(default_factory=dict)
    priority: int = 100
    active: bool = True


@dataclass(slots=True)
class PartnerApplication:
    name: str
    partner_type: Literal["internal_app", "external_partner", "saas", "on_prem"]
    connectivities: list[Connectivity] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FieldMap:
    source_path: str
    target_path: str
    transform: str | None = None
    default_value: Any = None


@dataclass(slots=True)
class IntegrationMap:
    name: str
    source_message: str
    target_message: str
    mappings: list[FieldMap]
    source_app: str
    target_app: str
    version: str = "1.0"
    enabled: bool = True
