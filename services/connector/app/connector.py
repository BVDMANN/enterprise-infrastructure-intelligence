"""Simulation connector (PHASE 0 skeleton).

Implements the common connector contract (see
docs/api/CONNECTOR_SPECIFICATION.md) with EXPLICITLY SIMULATED data.

WARNING — SIMULATION: every record returned here is fake by design and
carries ``simulated: True``. It must NEVER be presented as a real
infrastructure. The UI must show a SIMULATED badge for these records.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field

# The whole connector is simulated. Real connectors (Proxmox, Debian, AWS)
# set this to False and implement the same interface.
SIMULATED = True


class ConnectorMessage(BaseModel):
    """Envelope sent by every connector to the Control Plane."""

    connector_id: str
    protocol_version: str = "1"
    organization_id: str
    sent_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    nonce: str
    payload: dict
    simulated: bool = True


class SimulationConnector:
    """Simulated connector: same contract as real connectors, fake inventory.

    Used for demos, tests and development without a real infrastructure.
    """

    connector_type = "simulation"

    def __init__(
        self, organization_id: str, connector_id: str | None = None
    ) -> None:
        self.organization_id = organization_id
        self.connector_id = connector_id or str(uuid.uuid4())

    def health_check(self) -> dict[str, object]:
        """Connector liveness (real: this connector process is running)."""
        return {
            "connector_id": self.connector_id,
            "type": self.connector_type,
            "status": "ok",
            "simulated": SIMULATED,
        }

    def discover(self) -> list[dict[str, object]]:
        """Return a SIMULATED inventory (2 hosts, 3 VMs)."""
        return [
            {
                "external_id": "sim-host-01",
                "kind": "host",
                "name": "sim-host-01",
                "status": "online",
                "simulated": True,
            },
            {
                "external_id": "sim-vm-01",
                "kind": "vm",
                "name": "sim-vm-01",
                "status": "online",
                "simulated": True,
            },
            {
                "external_id": "sim-vm-02",
                "kind": "vm",
                "name": "sim-vm-02",
                "status": "offline",
                "simulated": True,
            },
        ]

    def sync_inventory(self) -> dict[str, object]:
        """Simulate one inventory sync run."""
        resources = self.discover()
        return {
            "connector_id": self.connector_id,
            "status": "completed",
            "resources_seen": len(resources),
            "resources_added": len(resources),
            "resources_removed": 0,
            "simulated": True,
        }

    def collect_metrics(self) -> list[dict[str, object]]:
        """Return SIMULATED metric points (fixed values, clearly fake)."""
        now = datetime.now(timezone.utc).isoformat()
        return [
            {
                "resource_id": "sim-vm-01",
                "metric": "cpu_usage_percent",
                "value": 42.0,
                "timestamp": now,
                "simulated": True,
            },
            {
                "resource_id": "sim-vm-01",
                "metric": "memory_usage_percent",
                "value": 61.0,
                "timestamp": now,
                "simulated": True,
            },
        ]

    def envelope(self, payload: dict) -> ConnectorMessage:
        """Wrap a payload in the standard connector envelope."""
        return ConnectorMessage(
            connector_id=self.connector_id,
            organization_id=self.organization_id,
            nonce=str(uuid.uuid4()),
            payload=payload,
            simulated=SIMULATED,
        )
