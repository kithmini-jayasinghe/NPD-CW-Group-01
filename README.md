# NetWatch — Network Programming Design Coursework (Group 1)

A small network monitoring toolkit for Serendib Logistics, built in two
parts: a Bash tool (Part A) for host reachability checks and reporting,
and a Python tool (Part B) for service-level socket checks, concurrency,
and status publishing.

## Group members and work allocation

| Member | Role | Requirements owned |
|---|---|---|
| Member 1 — Swetha | Part A Lead (Bash Core Engine & Library) | FR-S01, FR-S03, `lib/helpers.sh`, `set -euo pipefail` conflict resolution |
| Member 2 — Kendra | Part A & Integration Lead (CLI, Reporting, Pipeline) | FR-S02, FR-S04, FR-S05, INT-01–03, crontab evidence |
| Member 3 — Kithmini | Part B Lead (Python Core Engine & Concurrency) | FR-P01, FR-P02, FR-P03, FR-P04, FR-P05, FR-P06 |
| Member 4 — Dinol | Part B & Network Services Lead (Client-Server & Security) | FR-P07, FR-P08, estate simulation, security report section |

*(Full one-page work allocation table with contribution percentages is in
`Documentation/` per the submission structure — this table is a summary.)*

## Requirements

- Bash (tested on Ubuntu/WSL)
- Python 3 (standard library only — no packages to install)
- `shellcheck` (for verifying Part A — install with `sudo apt install shellcheck`)

No virtual machines, lab servers, or installed packages are needed.

## Repository structure

```
shell-script/
  netwatch.sh       — Part A entry point
  lib/helpers.sh     — shared Bash function library
  config/            — inventory.csv (shared with Part B)
  data/              — history.csv (generated, not committed)
  logs/              — netwatch.log, cron.log (generated, not committed)
  reports/           — generated CSV reports (generated, not committed)
  python/
    netwatch.py        — Part B entry point
    status_server.py   — publishes current status over HTTP
    status_client.py   — Group 1 socket client
  data/                — Part B results.json
  reports/             — Part B and consolidated reports
evidence/
  screenshots/       — test case evidence, named by test case ID
  crontab_evidence.txt
documentation/
  Coursework_Report.pdf
  Network_Architecture.png
  Program_Architecture.png
```

## Setting up your test estate

Before running the monitoring pipeline, start the background HTTP servers to simulate Serendib Logistics' services:

```bash
python3 -m http.server 8080 &
python3 -m http.server 8081 &
python3 -m http.server 9000 &
```

On Windows, use separate terminals and run `python -m http.server PORT`.
```

## Running Part A — netwatch.sh

```bash
cd shell-script
chmod +x netwatch.sh
./netwatch.sh
```

### CLI options

| Option | Description | Default |
|---|---|---|
| `-i PATH` | Path to inventory CSV | `config/inventory.csv` (relative to script) |
| `-o DIR` | Output directory for reports | `reports/` (relative to script) |
| `-t SECS` | Probe timeout in whole seconds | `2` |
| `-r` | Report-only mode — skip probing, regenerate report from existing history | off |
| `-h` | Show usage and exit | — |

Example:
```bash
./netwatch.sh -i config/inventory.csv -o reports/ -t 3
```

### Scheduled runs (crontab)

To run hourly:
```
0 * * * * /absolute/path/to/shell-script/netwatch.sh >> /absolute/path/to/shell-script/logs/cron.log 2>&1
```
Evidence of a scheduled run is in `evidence/crontab_evidence.txt` and
`evidence/screenshots/`.

## Running Part B — netwatch.py

Run from the repository root. The default inventory is the shared file under
`shell-script/config/`; results are written to `data/results.json` and reports
to `reports/`.

```bash
python3 python/netwatch.py --mode sequential --timeout 2
python3 python/netwatch.py --mode concurrent --timeout 2 --workers 10
python3 python/netwatch.py --mode benchmark --timeout 2 --workers 10
```

Useful options are `--inventory PATH`, `--output-dir PATH`, and
`--report-dir PATH`. Exit code 0 means all services are open, 1 means at least
one service is unavailable, 2 means invalid arguments, and 3 means a file or
data error.

## Running the status service

```bash
python3 python/status_server.py --host 127.0.0.1 --port 8888 --results data/results.json
```

The service listens on `http://127.0.0.1:8888` and logs each request.

To query it using the Group 1 socket client:

```bash
python3 python/status_client.py --host 127.0.0.1 --port 8888
```

## The inventory file

Both components read `shell-script/config/inventory.csv`:
```
hostname,ip_address,service,port,critical
intranet,127.0.0.1,http,8080,yes
warehouse-app,127.0.0.1,wms,9000,yes
...
```
See `shell-script/config/inventory.csv` for the current version. Both tools
reject malformed rows individually and continue with valid rows.

## Testing

Test cases are documented in `Documentation/Coursework_Report.pdf`
(Testing and Results section) with evidence in `evidence/screenshots/`.
To verify the shell script independently on Linux, WSL, or Git Bash:
```bash
cd shell-script
shellcheck -x netwatch.sh lib/helpers.sh
```

The submitted inventory deliberately contains six local targets: one open
service when the test server is running, several unused ports, and an
unavailable service. All targets are within the authorised `127.0.0.1` test
boundary.

## AI use declaration

See Appendix C of the report for each member's individual AI-use
declaration, per the coursework's academic integrity requirements.

## Authorisation note

This toolkit only targets `127.0.0.1`/localhost and any lab IP range
issued in writing. Do not point it at any other address.
