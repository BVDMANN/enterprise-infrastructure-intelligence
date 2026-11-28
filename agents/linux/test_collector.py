"""Unit tests for the dependency-free Linux EII agent collector."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collector import (
    AgentClient,
    _RejectRedirects,
    collect_metrics,
    cpu_utilization,
    read_memory_bytes,
    read_network_bytes,
    validate_api_url,
)

TOKEN = "eii_agent_test-token-never-a-real-secret"


class _Response:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


class CpuTests(unittest.TestCase):
    def test_cpu_utilization_uses_idle_and_iowait_deltas(self) -> None:
        self.assertEqual(
            cpu_utilization((100, 50), (200, 70)),
            80,
        )

    def test_cpu_utilization_omits_first_or_invalid_sample(self) -> None:
        self.assertIsNone(cpu_utilization((100, 50), (100, 50)))
        self.assertIsNone(cpu_utilization((100, 50), (200, 210)))


class ProcfsTests(unittest.TestCase):
    def _write_proc_fixture(self, root: Path) -> None:
        (root / "net").mkdir()
        (root / "stat").write_text(
            "cpu 100 0 50 200 10 0 0 0\n", encoding="ascii"
        )
        (root / "meminfo").write_text(
            "MemTotal: 1024 kB\nMemAvailable: 256 kB\n", encoding="ascii"
        )
        (root / "net" / "dev").write_text(
            "Inter-| Receive | Transmit\n"
            " face |bytes packets errs drop fifo frame compressed multicast|bytes packets errs drop fifo colls carrier compressed\n"
            "    lo: 999 0 0 0 0 0 0 0 888 0 0 0 0 0 0 0\n"
            "  eth0: 100 0 0 0 0 0 0 0 200 0 0 0 0 0 0 0\n"
            " vmbr0: 300 0 0 0 0 0 0 0 400 0 0 0 0 0 0 0\n",
            encoding="ascii",
        )

    def test_memory_uses_memavailable_and_converts_kib_to_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "meminfo").write_text(
                "MemTotal: 1024 kB\nMemAvailable: 256 kB\n", encoding="ascii"
            )
            self.assertEqual(read_memory_bytes(root), (1_048_576, 262_144))

    def test_network_counters_are_per_interface_and_exclude_loopback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "net").mkdir()
            (root / "net" / "dev").write_text(
                "Inter-| Receive | Transmit\n"
                " face |bytes packets errs drop fifo frame compressed multicast|bytes packets errs drop fifo colls carrier compressed\n"
                "    lo: 999 0 0 0 0 0 0 0 888 0 0 0 0 0 0 0\n"
                "  eth0: 100 0 0 0 0 0 0 0 200 0 0 0 0 0 0 0\n"
                " vmbr0: 300 0 0 0 0 0 0 0 400 0 0 0 0 0 0 0\n",
                encoding="ascii",
            )
            self.assertEqual(
                read_network_bytes(root),
                {"eth0": (100, 200), "vmbr0": (300, 400)},
            )

    def test_collector_emits_bounded_tenant_neutral_samples(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proc_root = root / "proc"
            proc_root.mkdir()
            self._write_proc_fixture(proc_root)
            filesystem_root = root / "filesystem"
            filesystem_root.mkdir()

            samples = collect_metrics(
                proc_root=proc_root,
                filesystem_root=filesystem_root,
                cpu_interval=0,
                now=lambda: datetime(2026, 11, 28, tzinfo=timezone.utc),
            )

        names = {sample["metric_name"] for sample in samples}
        self.assertEqual(
            names,
            {
                "memory.used_bytes",
                "memory.utilization",
                "filesystem.root.used_bytes",
                "filesystem.root.utilization",
                "network.interface.eth0.rx_bytes_total",
                "network.interface.eth0.tx_bytes_total",
                "network.interface.vmbr0.rx_bytes_total",
                "network.interface.vmbr0.tx_bytes_total",
            },
        )
        self.assertEqual(len(samples), 8)
        self.assertTrue(all(sample["recorded_at"].endswith("+00:00") for sample in samples))
        self.assertEqual(
            next(s for s in samples if s["metric_name"] == "memory.utilization")[
                "metric_value"
            ],
            "75.00",
        )
        self.assertTrue(all("organization_id" not in sample for sample in samples))
        self.assertTrue(all("asset_id" not in sample for sample in samples))


class ClientTests(unittest.TestCase):
    def test_url_requires_https_except_for_loopback(self) -> None:
        self.assertEqual(
            validate_api_url("https://control.example/"),
            "https://control.example",
        )
        self.assertEqual(
            validate_api_url("http://127.0.0.1:8000"),
            "http://127.0.0.1:8000",
        )
        for url in (
            "http://control.example",
            "https://user:password@control.example",
            "https://control.example/api",
            "https://control.example?token=bad",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_api_url(url)

    def test_heartbeat_sends_bearer_header_without_tenant_selector(self) -> None:
        captured = {}

        def opener(request, *, timeout):
            captured["url"] = request.full_url
            captured["authorization"] = request.get_header("Authorization")
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return _Response(b'{"asset_id":"asset","received_at":"now"}')

        client = AgentClient(
            "https://control.example",
            TOKEN,
            timeout=3,
            opener=opener,
        )
        self.assertEqual(client.heartbeat()["asset_id"], "asset")
        self.assertEqual(
            captured,
            {
                "url": "https://control.example/api/v1/agent/heartbeat",
                "authorization": f"Bearer {TOKEN}",
                "body": {},
                "timeout": 3,
            },
        )

    def test_client_rejects_invalid_tokens_and_empty_or_oversized_batches(self) -> None:
        with self.assertRaises(ValueError):
            AgentClient("https://control.example", "not-a-token")
        client = AgentClient("https://control.example", TOKEN)
        with self.assertRaises(ValueError):
            client.submit_metrics([])
        with self.assertRaises(ValueError):
            client.submit_metrics([{}] * 101)

    def test_redirects_are_not_followed(self) -> None:
        handler = _RejectRedirects()
        self.assertIsNone(
            handler.redirect_request(None, None, 302, "Found", {}, "https://other.example")
        )


if __name__ == "__main__":
    unittest.main()
