import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from message_first_ipaas.exceptions import RegistrationError, RoutingError, ValidationError
from message_first_ipaas.models import Connectivity, FieldMap, IntegrationMap, MessageDefinition, PartnerApplication
from message_first_ipaas.platform import EnterpriseIPaaSPlatform


class PlatformTests(unittest.TestCase):
    def setUp(self) -> None:
        self.platform = EnterpriseIPaaSPlatform()

        source_key = self.platform.register_message(
            MessageDefinition(
                name="PurchaseOrder",
                version="1.0",
                schema_type="json_schema",
                schema={"required": ["orderId", "buyer", "amount"]},
                description="Canonical purchase order message",
            )
        )
        target_key = self.platform.register_message(
            MessageDefinition(
                name="ERPOrder",
                version="1.0",
                schema_type="manual",
                schema={"required_fields": ["header.id", "header.customer_name", "financials.total"]},
            )
        )

        self.platform.register_application(PartnerApplication(name="Salesforce", partner_type="saas"))
        self.platform.add_connectivity(
            "Salesforce",
            Connectivity(name="sf-rest", protocol="rest", endpoint="https://api.salesforce.com", priority=50),
        )

        self.platform.register_application(PartnerApplication(name="SAP", partner_type="on_prem"))
        self.platform.add_connectivity(
            "SAP",
            Connectivity(name="sap-rest", protocol="rest", endpoint="https://sap.internal/api", priority=20, active=False),
        )
        self.platform.add_connectivity(
            "SAP",
            Connectivity(name="sap-mq", protocol="mq", endpoint="mq://sap.internal:1414", priority=10),
        )

        self.platform.register_map(
            IntegrationMap(
                name="sf-to-sap-order",
                source_message=source_key,
                target_message=target_key,
                source_app="Salesforce",
                target_app="SAP",
                mappings=[
                    FieldMap("orderId", "header.id"),
                    FieldMap("buyer", "header.customer_name", transform="uppercase"),
                    FieldMap("amount", "financials.total", transform="string"),
                ],
            )
        )

    def test_route_applies_mapping_transform_and_connectivity_resolution(self) -> None:
        result = self.platform.route(
            "sf-to-sap-order",
            {"orderId": "PO-42", "buyer": "acme", "amount": 1500.25},
        )

        self.assertEqual(result["payload"]["header"]["id"], "PO-42")
        self.assertEqual(result["payload"]["header"]["customer_name"], "ACME")
        self.assertEqual(result["payload"]["financials"]["total"], "1500.25")
        self.assertEqual(result["target_connectivity"]["name"], "sap-mq")

    def test_missing_required_field_raises(self) -> None:
        with self.assertRaises(ValidationError):
            self.platform.route(
                "sf-to-sap-order",
                {"orderId": "PO-42", "buyer": "acme"},
            )

    def test_duplicate_registration_raises(self) -> None:
        with self.assertRaises(RegistrationError):
            self.platform.register_application(PartnerApplication(name="SAP", partner_type="on_prem"))

    def test_unknown_transform_raises(self) -> None:
        self.platform.register_map(
            IntegrationMap(
                name="sf-to-sap-order-bad-transform",
                source_message="PurchaseOrder:1.0",
                target_message="ERPOrder:1.0",
                source_app="Salesforce",
                target_app="SAP",
                mappings=[FieldMap("buyer", "header.customer_name", transform="not-real")],
            )
        )
        with self.assertRaises(RoutingError):
            self.platform.route(
                "sf-to-sap-order-bad-transform",
                {"orderId": "PO-42", "buyer": "acme", "amount": 10},
            )


if __name__ == "__main__":
    unittest.main()
