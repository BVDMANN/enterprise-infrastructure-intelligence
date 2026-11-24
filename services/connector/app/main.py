"""Simulation connector entrypoint (PHASE 0).

Runs one discovery + sync cycle and prints a JSON summary.
In PHASE 1 this will POST to the Control Plane ingest endpoints over mTLS.
"""

import json
import os
import sys

from app.connector import SIMULATED, SimulationConnector


def main() -> int:
    print("=== SIMULATION CONNECTOR — SIMULATED DATA ONLY ===", flush=True)
    print(
        "All records below are fake by design and marked simulated: true.",
        flush=True,
    )
    organization_id = os.environ.get(
        "EII_ORGANIZATION_ID", "00000000-0000-0000-0000-000000000000"
    )
    connector = SimulationConnector(organization_id=organization_id)
    print(json.dumps(connector.health_check(), indent=2), flush=True)
    print(json.dumps(connector.sync_inventory(), indent=2), flush=True)
    print(json.dumps(connector.collect_metrics(), indent=2), flush=True)
    print(f"SIMULATED={SIMULATED} — never present as real infrastructure.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
