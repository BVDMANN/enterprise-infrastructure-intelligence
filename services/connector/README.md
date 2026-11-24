# Connector service — Enterprise Infrastructure Intelligence

Data Plane connectors (see `docs/api/CONNECTOR_SPECIFICATION.md`).

## Current state (PHASE 0)

Only the **simulation connector** exists (`app/connector.py`). It implements
the common connector contract with explicitly simulated data
(`simulated: true` everywhere). It is used for demos, tests and
development — **never present its data as a real infrastructure**.

Real connectors (Proxmox, Debian, AWS) arrive in PHASE 1 (Proxmox and
Debian, read-only first) and PHASE 3 (AWS).

## Run locally

```bash
pip install -r requirements.txt
python -m app.main
```
