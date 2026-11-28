#!/usr/bin/env python3
"""Minimal, dependency-free Linux telemetry agent for EII (P1-A7.3).

The credential binds this process to one asset. The client never sends tenant
or asset identifiers and never logs the bearer token.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
    urlopen,
)

LOG = logging.getLogger("eii-linux-agent")
TOKEN_PREFIX = "eii_agent_"
MIN_INTERVAL_SECONDS = 10
MAX_INTERVAL_SECONDS = 3600
MAX_RESPONSE_BYTES = 64 * 1024
MAX_NETWORK_INTERFACES = 40
CPU_SAMPLE_INTERVAL_SECONDS = 0.25
_INTERFACE_NAME = re.compile(r"^[a-z0-9_.-]{1,15}$")


def read_cpu_times(proc_root: Path = Path("/proc")) -> tuple[int, int]:
    """Return aggregate CPU (total, idle+iowait) jiffies from /proc/stat."""
    for line in (proc_root / "stat").read_text(encoding="ascii").splitlines():
        if line.startswith("cpu "):
            fields = line.split()[1:]
            if len(fields) < 4:
                break
            values = [int(value) for value in fields[:8]]
            idle = values[3] + (values[4] if len(values) > 4 else 0)
            return sum(values), idle
    raise ValueError("aggregate CPU counters are missing from /proc/stat")


def cpu_utilization(
    before: tuple[int, int], after: tuple[int, int]
) -> Decimal | None:
    """Calculate busy CPU percentage; return None for an invalid/first sample."""
    total_delta = after[0] - before[0]
    idle_delta = after[1] - before[1]
    if total_delta <= 0 or idle_delta < 0 or idle_delta > total_delta:
        return None
    busy_delta = total_delta - idle_delta
    return (Decimal(busy_delta) * Decimal(100) / Decimal(total_delta)).quantize(
        Decimal("0.01")
    )


def read_memory_bytes(proc_root: Path = Path("/proc")) -> tuple[int, int]:
    """Return (total bytes, available bytes) using Linux MemAvailable."""
    values: dict[str, int] = {}
    for line in (proc_root / "meminfo").read_text(encoding="ascii").splitlines():
        key, separator, raw_value = line.partition(":")
        if not separator or key not in {"MemTotal", "MemAvailable"}:
            continue
        fields = raw_value.split()
        if len(fields) < 2 or fields[1] != "kB":
            raise ValueError(f"unexpected /proc/meminfo unit for {key}")
        values[key] = int(fields[0]) * 1024
    if "MemTotal" not in values or "MemAvailable" not in values:
        raise ValueError("MemTotal or MemAvailable is missing from /proc/meminfo")
    total = values["MemTotal"]
    available = values["MemAvailable"]
    if total <= 0 or available < 0 or available > total:
        raise ValueError("invalid memory counters in /proc/meminfo")
    return total, available


def read_network_bytes(
    proc_root: Path = Path("/proc"),
) -> dict[str, tuple[int, int]]:
    """Return per-interface RX/TX counters, excluding loopback.

    Per-interface samples avoid summing bridges, bonds and their member
    interfaces together, which would double-count traffic on many Linux hosts.
    """
    interfaces: dict[str, tuple[int, int]] = {}
    lines = (proc_root / "net/dev").read_text(encoding="ascii").splitlines()
    for line in lines[2:]:
        interface, separator, raw_counters = line.partition(":")
        name = interface.strip().lower()
        if not separator or name == "lo":
            continue
        if not _INTERFACE_NAME.fullmatch(name):
            continue
        fields = raw_counters.split()
        if len(fields) < 9:
            raise ValueError("unexpected interface counters in /proc/net/dev")
        if name in interfaces:
            raise ValueError("duplicate interface name in /proc/net/dev")
        interfaces[name] = (int(fields[0]), int(fields[8]))
        if len(interfaces) > MAX_NETWORK_INTERFACES:
            raise ValueError(
                f"more than {MAX_NETWORK_INTERFACES} network interfaces; "
                "refusing to truncate telemetry"
            )
    return interfaces


def _sample(
    name: str, value: int | Decimal, unit: str, recorded_at: datetime
) -> dict[str, str]:
    return {
        "metric_name": name,
        "metric_value": str(value),
        "unit": unit,
        "recorded_at": recorded_at.isoformat(),
    }


def collect_metrics(
    *,
    proc_root: Path = Path("/proc"),
    filesystem_root: Path = Path("/"),
    cpu_interval: float = CPU_SAMPLE_INTERVAL_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> list[dict[str, str]]:
    """Collect host CPU, memory, root filesystem and per-interface network data."""
    if cpu_interval < 0 or cpu_interval > 5:
        raise ValueError("cpu_interval must be between 0 and 5 seconds")

    cpu_before = read_cpu_times(proc_root)
    if cpu_interval:
        sleep(cpu_interval)
    cpu_after = read_cpu_times(proc_root)
    total_memory, available_memory = read_memory_bytes(proc_root)
    disk = shutil.disk_usage(filesystem_root)
    interfaces = read_network_bytes(proc_root)
    observed_at = now()
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("collector clock must return a timezone-aware datetime")
    recorded_at = observed_at.astimezone(timezone.utc)

    used_memory = total_memory - available_memory
    used_disk = disk.used
    samples: list[dict[str, str]] = []
    cpu_percent = cpu_utilization(cpu_before, cpu_after)
    if cpu_percent is not None:
        samples.append(_sample("cpu.utilization", cpu_percent, "%", recorded_at))

    samples.extend(
        [
            _sample("memory.used_bytes", used_memory, "bytes", recorded_at),
            _sample(
                "memory.utilization",
                (Decimal(used_memory) * Decimal(100) / Decimal(total_memory)).quantize(
                    Decimal("0.01")
                ),
                "%",
                recorded_at,
            ),
            _sample("filesystem.root.used_bytes", used_disk, "bytes", recorded_at),
            _sample(
                "filesystem.root.utilization",
                (
                    Decimal(used_disk) * Decimal(100) / Decimal(disk.total)
                ).quantize(Decimal("0.01"))
                if disk.total
                else Decimal(0),
                "%",
                recorded_at,
            ),
        ]
    )
    for name, (received_bytes, transmitted_bytes) in sorted(interfaces.items()):
        samples.append(
            _sample(
                f"network.interface.{name}.rx_bytes_total",
                received_bytes,
                "bytes",
                recorded_at,
            )
        )
        samples.append(
            _sample(
                f"network.interface.{name}.tx_bytes_total",
                transmitted_bytes,
                "bytes",
                recorded_at,
            )
        )
    if not 1 <= len(samples) <= 100:
        raise ValueError("collected metric count is outside the API batch limit")
    return samples


def validate_api_url(value: str) -> str:
    """Require HTTPS except for explicit loopback development endpoints."""
    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise ValueError("EII_AGENT_API_URL must be an absolute HTTP(S) origin")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("EII_AGENT_API_URL must not contain credentials or query data")
    if parsed.path not in {"", "/"}:
        raise ValueError("EII_AGENT_API_URL must be an origin without a path")
    if parsed.scheme == "http" and parsed.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ValueError("HTTP is allowed only for loopback development endpoints")
    return f"{parsed.scheme}://{parsed.netloc}"


class _RejectRedirects(HTTPRedirectHandler):
    """Never forward an agent bearer token to a redirect target."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class AgentClient:
    """Small HTTPS client; no retries are made because ingestion is not idempotent."""

    def __init__(
        self,
        api_url: str,
        token: str,
        *,
        timeout: float = 10.0,
        opener: Callable[..., object] | None = None,
    ) -> None:
        if not token.startswith(TOKEN_PREFIX) or len(token) > 128:
            raise ValueError("EII_AGENT_TOKEN is not a valid EII agent token")
        if timeout <= 0 or timeout > 60:
            raise ValueError("request timeout must be between 0 and 60 seconds")
        self.api_url = validate_api_url(api_url)
        self._token = token
        self.timeout = timeout
        self._opener = opener or build_opener(_RejectRedirects()).open

    def _post(self, endpoint: str, payload: dict[str, object]) -> dict[str, object]:
        if endpoint not in {"heartbeat", "metrics"}:
            raise ValueError("unsupported agent endpoint")
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = Request(
            f"{self.api_url}/api/v1/agent/{endpoint}",
            data=body,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise RuntimeError("Agent API response exceeded the size limit")
        except HTTPError as exc:
            raise RuntimeError(f"Agent API returned HTTP {exc.code}") from None
        except URLError:
            raise RuntimeError("Agent API connection failed") from None

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise RuntimeError("Agent API returned an invalid JSON response") from None
        if not isinstance(decoded, dict):
            raise RuntimeError("Agent API returned an unexpected response")
        return decoded

    def heartbeat(self) -> dict[str, object]:
        return self._post("heartbeat", {})

    def submit_metrics(self, samples: list[dict[str, str]]) -> dict[str, object]:
        if not 1 <= len(samples) <= 100:
            raise ValueError("agent metric batch must contain between 1 and 100 samples")
        return self._post("metrics", {"samples": samples})


def run_forever(
    client: AgentClient,
    interval: int,
    *,
    stop_event: threading.Event | None = None,
) -> None:
    """Send one heartbeat and one metric batch per cycle; never retry a batch."""
    if not MIN_INTERVAL_SECONDS <= interval <= MAX_INTERVAL_SECONDS:
        raise ValueError(
            f"interval must be between {MIN_INTERVAL_SECONDS} and {MAX_INTERVAL_SECONDS} seconds"
        )
    stopping = stop_event or threading.Event()
    while not stopping.is_set():
        try:
            client.heartbeat()
            samples = collect_metrics()
            client.submit_metrics(samples)
            LOG.info("Submitted %d host metrics", len(samples))
        except (OSError, RuntimeError, ValueError) as exc:
            # Do not print request headers, credentials, or response bodies.
            LOG.error("Agent cycle failed: %s", exc)
        stopping.wait(interval)


def main() -> int:
    logging.basicConfig(
        level=os.getenv("EII_AGENT_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    api_url = os.getenv("EII_AGENT_API_URL", "")
    token = os.getenv("EII_AGENT_TOKEN", "")
    try:
        interval = int(os.getenv("EII_AGENT_INTERVAL_SECONDS", "60"))
        client = AgentClient(api_url, token)
        run_forever(client, interval)
    except (ValueError, KeyboardInterrupt) as exc:
        if isinstance(exc, ValueError):
            LOG.error("Invalid agent configuration: %s", exc)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
