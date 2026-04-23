# Message-First Enterprise iPaaS

This repository provides an **enterprise-focused, message-first iPaaS foundation**.
Instead of starting from workflow orchestration, integrations start with **message contracts** and then attach partner/application connectivity and mapping runtime.

## Enterprise problem this solves

Most SMB-first iPaaS products optimize for lightweight point integrations. Enterprise programs require:

- Contract governance (versioned message definitions).
- Mixed standards support (JSON Schema, XSD, and manual canonical contracts).
- Multiple connectivity endpoints per app/partner with failover/priority behavior.
- Reusable integration maps with explicit source/target contract ownership.
- Validation and auditable routing metadata for operations teams.

## Core platform capabilities

### 1) Message-first contract registry
`MessageDefinition` supports:
- `json_schema`
- `xsd`
- `manual`

The platform validates source payloads before transformation and validates target payloads before delivery.

### 2) Application/partner onboarding with multi-connectivity
`PartnerApplication` can hold many `Connectivity` entries (REST, SOAP, SFTP, MQ, Event Stream, EDI) with:
- `priority`
- `active`

The runtime resolves the best active target connectivity automatically.

### 3) Integration maps as governed assets
`IntegrationMap` links:
- source app + source message
- target app + target message
- field-level mappings with optional defaults and transforms
- map versioning (`name:version`)

### 4) Extensible transform engine
Built-in transforms:
- `uppercase`
- `lowercase`
- `string`

Custom transform functions can be registered at runtime.

### 5) Enterprise-safe error model
Domain errors are separated as:
- `RegistrationError`
- `ValidationError`
- `RoutingError`

## Access the application (demo API)

The project now includes a runnable HTTP API so you can interact with the platform directly.

### Start server

From repository root:

```bash
PYTHONPATH=src python run_app.py
```

Server starts on: `http://127.0.0.1:8080`.

### Endpoints

- `GET /health` → health check
- `GET /summary` → current message/app/map registry
- `GET /metrics` → monitoring counters + recent executions
- `GET /dashboard` → execution + monitoring UI
- `POST /demo/route` → route a sample purchase order through demo integration map

### Example calls

```bash
curl http://127.0.0.1:8080/health
```

```bash
curl http://127.0.0.1:8080/summary
```

```bash
curl http://127.0.0.1:8080/metrics
```

Open UI dashboard in browser:

```text
http://127.0.0.1:8080/dashboard
```

```bash
curl -X POST http://127.0.0.1:8080/demo/route \
  -H 'Content-Type: application/json' \
  -d '{"orderId":"PO-100","buyer":"acme","amount":300}'
```

Expected payload section in response:

```json
{
  "header": {
    "id": "PO-100",
    "customer_name": "ACME"
  },
  "financials": {
    "total": "300"
  }
}
```

## Project layout

- `src/message_first_ipaas/models.py` – contract, connectivity, app, and map models.
- `src/message_first_ipaas/platform.py` – registration, validation, routing, connectivity resolution.
- `src/message_first_ipaas/exceptions.py` – domain exceptions.
- `src/message_first_ipaas/app.py` – runnable demo HTTP API.
- `run_app.py` – local server launcher.
- `examples/schemas/` – JSON Schema + XSD examples.
- `tests/test_platform.py` – unit tests for mapping, validation, and errors.

## Quick in-code example

```python
from message_first_ipaas.models import MessageDefinition, PartnerApplication, Connectivity, IntegrationMap, FieldMap
from message_first_ipaas.platform import EnterpriseIPaaSPlatform

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
platform.add_connectivity("CRM", Connectivity(name="crm-rest", protocol="rest", endpoint="https://crm.example.com", priority=10))

platform.register_application(PartnerApplication(name="ERP", partner_type="on_prem"))
platform.add_connectivity("ERP", Connectivity(name="erp-mq", protocol="mq", endpoint="mq://erp.internal:1414", priority=10))

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

result = platform.route("crm-to-erp-order", {"orderId": "PO-100", "buyer": "acme", "amount": 300})
print(result)
```

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Recommended next enterprise steps

- Persist contracts/maps/apps in a governance repository + approval workflow.
- Add proper JSON Schema and XSD validator libraries for strict conformance.
- Introduce environment promotion (`dev -> test -> prod`) with immutable versions.
- Add policy controls for PII masking, field encryption, and signed audit trails.
- Add runtime adapters for SAP/Oracle/Workday/Kafka/MQ/EDI/file gateways.
- Add observability for retries, dead-letter queues, and SLA dashboards.
