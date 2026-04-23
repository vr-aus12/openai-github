from __future__ import annotations

import json
import threading
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .exceptions import IPaaSError
from .models import Connectivity, FieldMap, IntegrationMap, MessageDefinition, PartnerApplication
from .platform import EnterpriseIPaaSPlatform


class MessageFirstAPIServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int]):
        self.platform = self._build_demo_platform()
        self._stats_lock = threading.Lock()
        self._route_requests = 0
        self._route_success = 0
        self._route_errors = 0
        self._execution_history: deque[dict[str, Any]] = deque(maxlen=100)
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

    def record_success(self, result: dict[str, Any]) -> None:
        with self._stats_lock:
            self._route_requests += 1
            self._route_success += 1
            self._execution_history.appendleft({"status": "success", "result": result})

    def record_error(self, error: str, message: str, payload: dict[str, Any]) -> None:
        with self._stats_lock:
            self._route_requests += 1
            self._route_errors += 1
            self._execution_history.appendleft(
                {"status": "error", "error": error, "message": message, "payload": payload}
            )

    def metrics(self) -> dict[str, Any]:
        with self._stats_lock:
            return {
                "route_requests": self._route_requests,
                "route_success": self._route_success,
                "route_errors": self._route_errors,
                "recent_executions": list(self._execution_history)[:20],
            }


class MessageFirstRequestHandler(BaseHTTPRequestHandler):
    server: MessageFirstAPIServer

    def do_GET(self) -> None:
        if self.path == "/health":
            self._write_json(HTTPStatus.OK, {"status": "ok"})
            return

        if self.path == "/summary":
            self._write_json(HTTPStatus.OK, self.server.platform.summary())
            return

        if self.path == "/metrics":
            self._write_json(HTTPStatus.OK, self.server.metrics())
            return

        if self.path == "/dashboard":
            self._write_html(HTTPStatus.OK, _dashboard_html())
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
            self.server.record_success(result)
        except IPaaSError as exc:
            self.server.record_error(exc.__class__.__name__, str(exc), payload)
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

    def _write_html(self, status: HTTPStatus, html: str) -> None:
        encoded = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def _dashboard_html() -> str:
    return """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Message-first iPaaS Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; }
    .cards { display: grid; grid-template-columns: repeat(3, minmax(120px, 1fr)); gap: 12px; }
    .card { border: 1px solid #ddd; border-radius: 8px; padding: 12px; }
    pre { background: #f6f8fa; padding: 12px; border-radius: 8px; overflow: auto; }
    button { padding: 10px 14px; }
  </style>
</head>
<body>
  <h1>Message-first iPaaS Dashboard</h1>
  <p>Monitoring + execution UI for demo routes.</p>

  <div class=\"cards\">
    <div class=\"card\"><strong>Requests</strong><div id=\"req\">0</div></div>
    <div class=\"card\"><strong>Success</strong><div id=\"ok\">0</div></div>
    <div class=\"card\"><strong>Errors</strong><div id=\"err\">0</div></div>
  </div>

  <h2>Execute Demo Route</h2>
  <button id=\"run\">Run Demo Execution</button>
  <pre id=\"run-output\"></pre>

  <h2>Recent Executions</h2>
  <pre id=\"exec\"></pre>

<script>
async function refreshMetrics() {
  const res = await fetch('/metrics');
  const data = await res.json();
  document.getElementById('req').textContent = data.route_requests;
  document.getElementById('ok').textContent = data.route_success;
  document.getElementById('err').textContent = data.route_errors;
  document.getElementById('exec').textContent = JSON.stringify(data.recent_executions, null, 2);
}

async function runDemo() {
  const res = await fetch('/demo/route', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({orderId: 'PO-' + Date.now(), buyer: 'acme', amount: 300})
  });
  const data = await res.json();
  document.getElementById('run-output').textContent = JSON.stringify(data, null, 2);
  await refreshMetrics();
}

document.getElementById('run').addEventListener('click', runDemo);
refreshMetrics();
setInterval(refreshMetrics, 5000);
</script>
</body>
</html>
"""


def run(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = MessageFirstAPIServer((host, port))
    print(f"Message-first iPaaS demo API running on http://{host}:{port}")
    print(f"Dashboard: http://{host}:{port}/dashboard")
    server.serve_forever()
