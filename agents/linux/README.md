# EII Linux agent — P1-A7.3

This is a small, dependency-free Linux host collector for the authenticated
agent endpoints introduced by PR #72. It is an actual collector for the host
where it runs; it is not a Proxmox cluster API integration and does not
discover guests, VMs, containers or cluster membership.

## Requirements

- Linux with `/proc/stat`, `/proc/meminfo` and `/proc/net/dev`.
- Python 3.10 or newer; the collector uses only the Python standard library.
- A credential created for the target infrastructure asset through the EII
  operator UI/API.
- HTTPS access to the EII control plane. Plain HTTP is accepted only for
  explicit loopback development endpoints.

## Metrics collected

- `cpu.utilization`: aggregate busy CPU percentage from two `/proc/stat`
  samples; omitted if the counters did not advance.
- `memory.used_bytes` and `memory.utilization`: based on
  `MemTotal - MemAvailable`.
- `filesystem.root.used_bytes` and `filesystem.root.utilization`: usage of
  the filesystem containing `/`.
- `network.interface.<name>.rx_bytes_total` and
  `network.interface.<name>.tx_bytes_total`: per-interface byte counters,
  excluding loopback.

Network counters are emitted per interface rather than summed: adding a
bridge/bond and its member interfaces together can double-count traffic.
Interface names that cannot safely form metric names are skipped. More than
40 eligible interfaces is an explicit collection error rather than silent
truncation. A collection contains at most 86 samples, below the API limit of
100.

## Configuration

Create a root-owned environment file readable only by root:

```ini
EII_AGENT_API_URL=https://control-plane.example
EII_AGENT_TOKEN=eii_agent_REPLACE_WITH_THE_ONE_TIME_TOKEN
EII_AGENT_INTERVAL_SECONDS=60
EII_AGENT_LOG_LEVEL=INFO
```

Do not put a real token in command-line arguments, shell history, source
control, service unit contents or logs. The example above is a placeholder,
not a credential. Keep the environment file mode `0600`.

The agent sends:
1. `POST /api/v1/agent/heartbeat`;
2. one `POST /api/v1/agent/metrics` batch.

The credential determines the organization and asset. The collector never
sends tenant, asset or actor IDs.

## Manual smoke run

From this directory, with the environment variables set in a protected
environment:

```sh
python3 collector.py
```

The interval must be between 10 and 3600 seconds. Request timeouts are bounded
to 10 seconds. HTTPS certificate verification remains enabled by Python's
default TLS context. Redirects are rejected so the bearer token is not
forwarded to another URL.

## systemd installation

Review the service unit and paths for the target distribution before
installing. The following is an example procedure; it is not executed by CI
or by this repository change:

```sh
sudo useradd --system --home /nonexistent --shell /usr/sbin/nologin eii-agent
sudo install -d -o root -g root -m 0755 /opt/eii-agent
sudo install -o root -g root -m 0644 collector.py /opt/eii-agent/collector.py
sudo install -d -o root -g root -m 0750 /etc/eii-agent
sudo install -o root -g root -m 0600 agent.env /etc/eii-agent/agent.env
sudo install -o root -g root -m 0644 eii-agent.service /etc/systemd/system/eii-agent.service
sudo systemctl daemon-reload
sudo systemctl enable --now eii-agent.service
sudo systemctl status eii-agent.service
```

Create `agent.env` locally with the actual control-plane URL and the
one-time token before the `install` command. Do not commit that file.

## Delivery and operational limitations

- The collector reports the host on which it runs; no Proxmox API, guest
  discovery or hypervisor inventory is implemented.
- It has no offline spool, batch idempotency key or automatic retry. A
  connection loss after the server commits but before the response arrives
  can cause duplicate samples on a later cycle. This is intentionally not
  hidden; retry semantics need a server-side idempotency contract first.
- A failed cycle is logged without printing the token or response body; the
  next scheduled cycle tries again.
- It does not change the operator-managed asset status to healthy.
- No mTLS, automatic credential rotation, rate limiter, alert engine or
  systemd installer is included.
- Run the agent under a dedicated unprivileged account. It needs read access
  to procfs and filesystem usage only; it does not need root or Linux
  capabilities.
