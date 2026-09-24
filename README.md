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
  status_client.py   — [Group 1 only] retrieves published status via socket
  data/, logs/, reports/  — generated, not committed
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

python3 -m http.server 8080 &
python3 -m http.server 8081 &
python3 -m http.server 9000 &

```bash
# Example — replace with actual startup commands
python3 -m http.server 8080 &
python3 -m http.server 8081 &
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

[Member 3 — add usage instructions here: modes, arguments, defaults]

```bash
cd python
python3 netwatch.py [TODO: add actual arguments]
```

## Running the status service

[Member 4 — add usage instructions here]

```bash
cd python
python3 status_server.py 

The service listens on http://127.0.0.1:8888.

To query the service status using the custom socket client
python3 status_client.py

To check status with the socket client (Group 1 only):
```bash
python3 status_client.py [TODO: add host/port arguments]

## The inventory file

Both components read `config/inventory.csv`:
```
hostname,ip_address,service,port,critical
intranet,127.0.0.1,http,8080,yes
warehouse-app,127.0.0.1,wms,9000,yes
...
```
See `config/inventory.csv` for the current version. **Note:** this is
currently a draft — see the team status document for an open question
about address diversity.

## Testing

Test cases are documented in `Documentation/Coursework_Report.pdf`
(Testing and Results section) with evidence in `evidence/screenshots/`.
To verify the shell script independently:
```bash
cd shell-script
shellcheck -x netwatch.sh lib/helpers.sh
```

## AI use declaration

See Appendix C of the report for each member's individual AI-use
declaration, per the coursework's academic integrity requirements.

## Authorisation note

This toolkit only targets `127.0.0.1`/localhost and any lab IP range
issued in writing. Do not point it at any other address.
