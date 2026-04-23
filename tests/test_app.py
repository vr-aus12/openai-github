import json
import socket
import threading
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from message_first_ipaas.app import MessageFirstAPIServer


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class APITests(unittest.TestCase):
    def setUp(self) -> None:
        self.port = _free_port()
        self.server = MessageFirstAPIServer(("127.0.0.1", self.port))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.05)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def test_health(self) -> None:
        with urlopen(self._url("/health")) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read().decode("utf-8"))["status"], "ok")

    def test_demo_route(self) -> None:
        req = Request(
            self._url("/demo/route"),
            method="POST",
            data=json.dumps({"orderId": "PO-77", "buyer": "acme", "amount": 99.5}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req) as response:
            body = json.loads(response.read().decode("utf-8"))
            self.assertEqual(response.status, 200)
            self.assertEqual(body["payload"]["header"]["customer_name"], "ACME")


if __name__ == "__main__":
    unittest.main()
