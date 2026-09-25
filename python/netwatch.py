#!/usr/bin/env python3

import csv
import json
import os
import re
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime

EXIT_SUCCESS = 0
EXIT_WARNING = 1
EXIT_USAGE_ERROR = 2
EXIT_FATAL_ERROR = 3
EXIT_INTERRUPTED = 130

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_INVENTORY = os.path.join(BASE_DIR, "shell-script", "config", "inventory.csv")
DEFAULT_RESULTS_JSON = os.path.join(BASE_DIR, "data", "results.json")
DEFAULT_REPORTS_DIR = os.path.join(BASE_DIR, "reports")
DEFAULT_TIMEOUT = 2.0
DEFAULT_MODE = "concurrent"
DEFAULT_MAX_WORKERS = 10

VALID_MODES = ("sequential", "concurrent", "benchmark")

EXPECTED_FIELD_COUNT = 5  # hostname,ip_address,service,port,critical

IPV4_PATTERN = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")


# Data structures
@dataclass
class Target:
    hostname: str
    ip_address: str
    service: str
    port: int
    critical: bool


# Small helpers
def log_error(message):
    timestamp = datetime.now().isoformat(timespec="seconds")
    print(f"[{timestamp}] ERROR: {message}", file=sys.stderr)


def log_info(message):
    timestamp = datetime.now().isoformat(timespec="seconds")
    print(f"[{timestamp}] {message}")


def print_usage():
    usage = """
Usage: netwatch.py --mode {sequential|concurrent|benchmark} [options]

Options:
  -m, --mode <mode>       sequential | concurrent | benchmark (default: concurrent)
    -i, --inventory <path>  path to inventory CSV
  -t, --timeout <secs>    per-connection socket timeout in seconds (default: 2.0)
  -w, --workers <n>       max concurrent worker threads (default: 10)
    --output-dir <path>     directory for results.json
    --report-dir <path>     directory for Python CSV reports
  -h, --help              show this message and exit

Exit codes: 0 all open, 1 some closed/error, 2 usage error, 3 fatal error.
"""
    print(usage, file=sys.stderr)

# FR-P01 - CLI argument parsing

def parse_arguments(argv):
    config = {
        "mode": DEFAULT_MODE,
        "inventory": DEFAULT_INVENTORY,
        "timeout": DEFAULT_TIMEOUT,
        "workers": DEFAULT_MAX_WORKERS,
        "output_dir": os.path.dirname(DEFAULT_RESULTS_JSON),
        "report_dir": DEFAULT_REPORTS_DIR,
    }

    i = 0
    n = len(argv)
    while i < n:
        arg = argv[i]

        if arg in ("-h", "--help"):
            print_usage()
            sys.exit(EXIT_SUCCESS)

        elif arg in ("-m", "--mode"):
            value = _next_value(argv, i, arg)
            if value not in VALID_MODES:
                raise ValueError(
                    f"invalid mode '{value}' (expected one of {VALID_MODES})"
                )
            config["mode"] = value
            i += 1

        elif arg in ("-i", "--inventory"):
            config["inventory"] = _next_value(argv, i, arg)
            i += 1

        elif arg in ("-t", "--timeout"):
            value = _next_value(argv, i, arg)
            try:
                timeout = float(value)
            except ValueError:
                raise ValueError(f"--timeout must be numeric, got '{value}'")
            if timeout <= 0:
                raise ValueError("--timeout must be greater than 0")
            config["timeout"] = timeout
            i += 1

        elif arg in ("-w", "--workers"):
            value = _next_value(argv, i, arg)
            try:
                workers = int(value)
            except ValueError:
                raise ValueError(f"--workers must be an integer, got '{value}'")
            if workers <= 0:
                raise ValueError("--workers must be greater than 0")
            config["workers"] = workers
            i += 1

        elif arg == "--output-dir":
            config["output_dir"] = _next_value(argv, i, arg)
            i += 1

        elif arg == "--report-dir":
            config["report_dir"] = _next_value(argv, i, arg)
            i += 1

        else:
            raise ValueError(f"unknown option '{arg}'")

        i += 1

    return config


def _next_value(argv, i, flag):
    """Return the argument following argv[i], or raise if it is missing."""
    if i + 1 >= len(argv):
        raise ValueError(f"missing value for {flag}")
    return argv[i + 1]


# FR-P02 - Inventory loading / validation

def validate_ipv4(address):
    """Return True if address is a syntactically valid IPv4 address."""
    match = IPV4_PATTERN.match(address.strip())
    if not match:
        return False
    return all(0 <= int(octet) <= 255 for octet in match.groups())


def validate_port(port_str):
    port_str = port_str.strip()
    if not port_str.isdigit():
        raise ValueError(f"port '{port_str}' is not numeric")
    port = int(port_str)
    if not (1 <= port <= 65535):
        raise ValueError(f"port {port} is out of range (1-65535)")
    return port


def load_inventory(path):
    targets = []
    accepted = 0
    rejected = 0

    with open(path, "r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        rows = list(reader)

    if not rows:
        raise ValueError("inventory file is empty")

    expected_header = ["hostname", "ip_address", "service", "port", "critical"]
    if [field.strip() for field in rows[0]] != expected_header:
        raise ValueError("inventory header must be hostname,ip_address,service,port,critical")

    for line_number, row in enumerate(rows[1:], start=2):
        # Skip fully blank lines rather than rejecting them noisily.
        if not row or all(field.strip() == "" for field in row):
            continue

        if len(row) != EXPECTED_FIELD_COUNT:
            log_error(
                f"inventory line {line_number}: expected "
                f"{EXPECTED_FIELD_COUNT} fields, found {len(row)} - row skipped"
            )
            rejected += 1
            continue

        hostname, ip_address, service, port_raw, critical_raw = (
            field.strip() for field in row
        )

        if not hostname or not re.fullmatch(r"[A-Za-z0-9_.-]+", hostname):
            log_error(f"inventory line {line_number}: hostname is invalid - row skipped")
            rejected += 1
            continue

        if not service or not re.fullmatch(r"[A-Za-z0-9_.-]+", service):
            log_error(f"inventory line {line_number}: service is invalid - row skipped")
            rejected += 1
            continue

        if not validate_ipv4(ip_address):
            log_error(
                f"inventory line {line_number}: ip_address '{ip_address}' "
                "is invalid - row skipped"
            )
            rejected += 1
            continue

        try:
            port = validate_port(port_raw)
        except ValueError as exc:
            log_error(f"inventory line {line_number}: {exc} - row skipped")
            rejected += 1
            continue

        if critical_raw.lower() not in ("yes", "no"):
            log_error(
                f"inventory line {line_number}: critical field "
                f"'{critical_raw}' must be 'yes' or 'no' - row skipped"
            )
            rejected += 1
            continue

        targets.append(
            Target(
                hostname=hostname,
                ip_address=ip_address,
                service=service,
                port=port,
                critical=(critical_raw.lower() == "yes"),
            )
        )
        accepted += 1

    return targets, accepted, rejected


# FR-P03 - single service check

def check_service(target, timeout):
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    start = time.monotonic()
    state = "ERROR"
    error_detail = ""

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(timeout)
        # connect_ex returns an errno (0 = success) instead of raising,
        # which is what FR-P03 asks for: failure as a value.
        result = sock.connect_ex((target.ip_address, target.port))
        if result == 0:
            state = "OPEN"
        elif result in (111, 10061):
            state = "CLOSED"
            error_detail = "connection refused"
        elif result in (110, 10035, 10060):
            state = "TIMEOUT"
            error_detail = "connection timed out"
        else:
            state = "ERROR"
            error_detail = os.strerror(result)
    except socket.timeout:
        state = "TIMEOUT"
        error_detail = "connection timed out"
    except socket.gaierror as exc:
        state = "ERROR"
        error_detail = f"address resolution failed: {exc}"
    except OSError as exc:
        # Covers e.g. "Network is unreachable" and similar OS-level errors.
        if getattr(exc, "errno", None) in (111, 10061):
            state = "CLOSED"
            error_detail = "connection refused"
        else:
            state = "ERROR"
            error_detail = str(exc)
    finally:
        sock.close()

    response_time = round(time.monotonic() - start, 4)

    return {
        "timestamp": timestamp,
        "hostname": target.hostname,
        "ip_address": target.ip_address,
        "service": target.service,
        "port": target.port,
        "critical": "yes" if target.critical else "no",
        "state": state,
        "response_time": response_time,
        "error_detail": error_detail,
    }


# FR-P04 - sequential / concurrent scanning

def run_sequential(targets, timeout):
    start = time.monotonic()
    results = [check_service(target, timeout) for target in targets]
    duration = round(time.monotonic() - start, 4)
    return _sort_results(results), duration


def run_concurrent(targets, timeout, max_workers):
    start = time.monotonic()
    results = []
    workers = min(max_workers, len(targets)) or 1

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(check_service, target, timeout): target
            for target in targets
        }
        for future in as_completed(futures):
            target = futures[future]
            try:
                results.append(future.result())
            except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
                log_error(f"worker for {target.hostname} raised {exc!r}")
                results.append(
                    {
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "hostname": target.hostname,
                        "ip_address": target.ip_address,
                        "service": target.service,
                        "port": target.port,
                        "critical": "yes" if target.critical else "no",
                        "state": "ERROR",
                        "response_time": 0.0,
                        "error_detail": f"worker exception: {exc}",
                    }
                )

    duration = round(time.monotonic() - start, 4)
    return _sort_results(results), duration


def _sort_results(results):
    return sorted(results, key=lambda r: (r["hostname"], r["port"]))


# FR-P05 - persistence and change detection

def load_previous_results(path):
    if not os.path.exists(path):
        return None, "no previous results file found - this is the first run"

    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, list):
            raise ValueError("results.json did not contain a list")
        return data, "previous results loaded"
    except (json.JSONDecodeError, ValueError) as exc:
        log_error(f"previous results file was corrupt ({exc}) - treating as first run")
        return None, "previous results file was corrupt - treated as first run"


def detect_changes(current_results, previous_results):
    current = {(r["ip_address"], r["port"]): r["state"] for r in current_results}

    if previous_results is None:
        return {
            "newly_opened": sorted(key for key, state in current.items() if state == "OPEN"),
            "newly_closed": [],
            "unchanged": sorted(current),
            "other_changes": [],
            "added": sorted(current),
            "removed": [],
            "note": "no previous run to compare against",
        }

    previous = {(r["ip_address"], r["port"]): r.get("state", "ERROR") for r in previous_results}
    common = set(current) & set(previous)
    newly_opened = {key for key in common if previous[key] != "OPEN" and current[key] == "OPEN"}
    newly_closed = {key for key in common if previous[key] == "OPEN" and current[key] != "OPEN"}
    unchanged = {key for key in common if previous[key] == current[key]}
    other_changes = {key for key in common if previous[key] != current[key]} - newly_opened - newly_closed

    return {
        "newly_opened": sorted(newly_opened),
        "newly_closed": sorted(newly_closed),
        "unchanged": sorted(unchanged),
        "other_changes": sorted(other_changes),
        "added": sorted(set(current) - set(previous)),
        "removed": sorted(set(previous) - set(current)),
        "note": "compared against previous run",
    }


def persist_results(results, results_json_path):
    os.makedirs(os.path.dirname(results_json_path) or ".", exist_ok=True)
    with open(results_json_path, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)


def write_report_csv(results, reports_dir):
    """
    FR-P05: write reports/py_results_<timestamp>.csv for Part A to merge.

    DATA CONTRACT (confirm with Members 1 & 2 for INT-03):
      Field order : timestamp,hostname,ip_address,service,port,critical,state,response_time,error_detail
      Delimiter   : comma
      Quoting     : csv.QUOTE_MINIMAL (fields are only quoted if they
                    contain a comma, quote character or newline)
      Timestamp   : ISO 8601, seconds precision, e.g. 2026-09-25T14:30:00
    """
    os.makedirs(reports_dir, exist_ok=True)
    run_timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    report_path = os.path.join(reports_dir, f"py_results_{run_timestamp}.csv")

    fieldnames = [
        "timestamp", "hostname", "ip_address", "service", "port",
        "critical", "state", "response_time", "error_detail",
    ]

    with open(report_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    return report_path


# FR-P06 - summary and exit code

def compute_summary(results):
    counts = {"OPEN": 0, "CLOSED": 0, "TIMEOUT": 0, "ERROR": 0}
    for r in results:
        counts[r["state"]] = counts.get(r["state"], 0) + 1

    total = len(results) or 1 
    availability_pct = round((counts["OPEN"] / total) * 100, 1)

    return {"counts": counts, "total": len(results), "availability_pct": availability_pct}


def print_summary(results, summary, changes, seq_duration=None, conc_duration=None):
    """Aligned, human-readable summary ending in a single status line."""
    print()
    print(f"{'HOSTNAME':<16}{'SERVICE':<10}{'PORT':<8}{'STATE':<8}{'RESP(s)':<10}")
    print("-" * 52)
    for r in results:
        print(
            f"{r['hostname']:<16}{r['service']:<10}{r['port']:<8}"
            f"{r['state']:<8}{r['response_time']:<10}"
        )

    print()
    if not results:
        print("No targets were checked - nothing to report.")
    else:
        print(
            f"Checked {summary['total']} target(s): "
            f"{summary['counts']['OPEN']} open, "
            f"{summary['counts']['CLOSED']} closed, "
            f"{summary['counts']['ERROR']} error "
            f"({summary['availability_pct']}% available)"
        )

    if seq_duration is not None and conc_duration is not None:
        speedup = round(seq_duration / conc_duration, 2) if conc_duration > 0 else 0
        print(f"Sequential duration : {seq_duration}s")
        print(f"Concurrent duration : {conc_duration}s")
        print(f"Speed-up            : {speedup}x")

    print()
    print(f"Newly opened : {changes['newly_opened']}")
    print(f"Newly closed : {changes['newly_closed']}")
    print(f"Unchanged    : {len(changes['unchanged'])} service(s) ({changes['note']})")
    print(f"Other changes: {changes['other_changes']}")
    print()

    exit_code = determine_exit_code(results)
    status_word = "OK" if exit_code == EXIT_SUCCESS else "ISSUES DETECTED"
    print(f"STATUS: {status_word} (exit code {exit_code})")
    return exit_code


def determine_exit_code(results):
    """FR-P06: map the outcome to the shared exit-code scheme."""
    if not results:
        return EXIT_WARNING
    if any(r["state"] in ("CLOSED", "TIMEOUT", "ERROR") for r in results):
        return EXIT_WARNING
    return EXIT_SUCCESS


# Orchestration

def run(config):
    try:
        targets, accepted, rejected = load_inventory(config["inventory"])
    except FileNotFoundError:
        log_error(f"inventory file not found: {config['inventory']}")
        return EXIT_FATAL_ERROR
    except PermissionError:
        log_error(f"permission denied reading: {config['inventory']}")
        return EXIT_FATAL_ERROR
    except (OSError, ValueError) as exc:
        log_error(f"could not read inventory: {exc}")
        return EXIT_FATAL_ERROR

    log_info(f"inventory loaded: {accepted} accepted, {rejected} rejected")

    if not targets:
        log_error("no valid targets to check")
        summary = compute_summary([])
        changes = detect_changes([], None)
        try:
            persist_results([], config["results_json"])
            write_report_csv([], config["reports_dir"])
        except (PermissionError, OSError) as exc:
            log_error(f"could not write empty result files: {exc}")
            return EXIT_FATAL_ERROR
        exit_code = print_summary([], summary, changes)
        return exit_code

    seq_duration = conc_duration = None

    if config["mode"] == "sequential":
        results, seq_duration = run_sequential(targets, config["timeout"])
    elif config["mode"] == "concurrent":
        results, conc_duration = run_concurrent(
            targets, config["timeout"], config["workers"]
        )
    else: 
        results, seq_duration = run_sequential(targets, config["timeout"])
        _, conc_duration = run_concurrent(targets, config["timeout"], config["workers"])

    try:
        previous_results, note = load_previous_results(config["results_json"])
    except PermissionError:
        log_error(f"permission denied reading: {config['results_json']}")
        return EXIT_FATAL_ERROR
    log_info(note)
    changes = detect_changes(results, previous_results)

    try:
        persist_results(results, config["results_json"])
        report_path = write_report_csv(results, config["reports_dir"])
    except PermissionError:
        log_error(f"permission denied writing output under {config['reports_dir']}")
        return EXIT_FATAL_ERROR
    except OSError as exc:
        log_error(f"could not write output: {exc}")
        return EXIT_FATAL_ERROR

    log_info(f"report written: {report_path}")

    summary = compute_summary(results)
    exit_code = print_summary(results, summary, changes, seq_duration, conc_duration)
    return exit_code


def main(argv):
    try:
        config = parse_arguments(argv)
    except ValueError as exc:
        log_error(str(exc))
        print_usage()
        return EXIT_USAGE_ERROR

    config["results_json"] = os.path.join(config["output_dir"], "results.json")
    config["reports_dir"] = config["report_dir"]

    return run(config)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        print("\nInterrupted - shutting down cleanly.", file=sys.stderr)
        sys.exit(EXIT_INTERRUPTED)