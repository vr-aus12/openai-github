from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .exceptions import IPaaSError
from .models import Connectivity, FieldMap, IntegrationMap, MessageDefinition, PartnerApplication
from .platform import EnterpriseIPaaSPlatform


class MessageFirstAPIServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int]):
        self.platform = self._build_demo_platform()
        super().__init__(server_address, MessageFirstRequestHandler)

    @staticmethod
    def _build_demo_platform() -> EnterpriseIPaaSPlatform:
        platform = EnterpriseIPaaSPlatform()

        source_key = platform.register_message(
            MessageDefinition(
                name="PurchaseOrder",
                version="1.0",
                schema_type="json_schema",
                schema={"required": ["orderId", "buyer", "amount"]},
            )
        )
        target_key = platform.register_message(
            MessageDefinition(
                name="ERPOrder",
                version="1.0",
                schema_type="manual",
                schema={"required_fields": ["header.id", "header.customer_name", "financials.total"]},
            )
        )

        platform.register_application(PartnerApplication(name="CRM", partner_type="saas"))
        platform.add_connectivity(
            "CRM",
            Connectivity(name="crm-rest", protocol="rest", endpoint="https://crm.example.com", priority=10),
        )

        platform.register_application(PartnerApplication(name="ERP", partner_type="on_prem"))
        platform.add_connectivity(
            "ERP",
            Connectivity(name="erp-mq", protocol="mq", endpoint="mq://erp.internal:1414", priority=10),
        )

        platform.register_map(
            IntegrationMap(
                name="crm-to-erp-order",
                source_message=source_key,
                target_message=target_key,
                source_app="CRM",
                target_app="ERP",
                mappings=[
                    FieldMap("orderId", "header.id"),
                    FieldMap("buyer", "header.customer_name", transform="uppercase"),
                    FieldMap("amount", "financials.total", transform="string"),
                ],
            )
        )

        return platform


class MessageFirstRequestHandler(BaseHTTPRequestHandler):
    server: MessageFirstAPIServer

    def do_GET(self) -> None:
        if self.path == "/health":
            self._write_json(HTTPStatus.OK, {"status": "ok"})
            return

        if self.path == "/summary":
            self._write_json(HTTPStatus.OK, self.server.platform.summary())
            return

        self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path != "/demo/route":
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        payload = self._read_json_body()
        if payload is None:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
            return

        try:
            result = self.server.platform.route("crm-to-erp-order", payload)
        except IPaaSError as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": exc.__class__.__name__, "message": str(exc)})
            return

        self._write_json(HTTPStatus.OK, result)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def _read_json_body(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

        if not isinstance(data, dict):
            return None
        return data

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def run(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = MessageFirstAPIServer((host, port))
    print(f"Message-first iPaaS demo API running on http://{host}:{port}")
    server.serve_forever()
