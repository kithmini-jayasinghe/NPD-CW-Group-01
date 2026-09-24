#!/usr/bin/env bash
#
# netwatch.sh — NetWatch Part A: reads a device inventory, checks host
#               reachability, records history, and produces a report.
#
# Authors: Kendra, Kithmini, Swetha, Dinol
# Date:    2026-09-24
#
# Usage:
#   ./netwatch.sh [-i inventory_path] [-o output_dir] [-t timeout] [-r] [-h]
#
#   -i PATH   Path to inventory CSV (default: config/inventory.csv, relative to this script)
#   -o DIR    Output directory for reports (default: reports/, relative to this script)
#   -t SECS   Probe timeout in whole seconds (default: 2)
#   -r        Report-only mode: skip probing, regenerate the report from existing history
#   -h        Show this help message and exit
#
set -euo pipefail

# --- Script-relative paths (never rely on the caller's working directory) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=lib/helpers.sh
source "${SCRIPT_DIR}/lib/helpers.sh"

# --- Defaults (documented above in the usage block) ---
INVENTORY_PATH="${SCRIPT_DIR}/config/inventory.csv"
OUTPUT_DIR="${SCRIPT_DIR}/reports"
PROBE_TIMEOUT=2
REPORT_ONLY=0

HISTORY_FILE="${SCRIPT_DIR}/data/history.csv"
LOG_FILE="${SCRIPT_DIR}/logs/netwatch.log"

usage() {
    cat <<EOF
Usage: $(basename "$0") [-i inventory_path] [-o output_dir] [-t timeout] [-r] [-h]

  -i PATH   Path to inventory CSV (default: ${INVENTORY_PATH})
  -o DIR    Output directory for reports (default: ${OUTPUT_DIR})
  -t SECS   Probe timeout in whole seconds (default: ${PROBE_TIMEOUT})
  -r        Report-only mode: skip probing, regenerate the report from existing history
  -h        Show this help message and exit
EOF
}

# --- Parse options ---
while getopts ":i:o:t:rh" opt; do
    case "${opt}" in
        i) INVENTORY_PATH="${OPTARG}" ;;
        o) OUTPUT_DIR="${OPTARG}" ;;
        t) PROBE_TIMEOUT="${OPTARG}" ;;
        r) REPORT_ONLY=1 ;;
        h) usage; exit 0 ;;
        \?)
            echo "Error: unknown option -${OPTARG}" >&2
            usage >&2
            exit 2
            ;;
        :)
            echo "Error: option -${OPTARG} requires an argument" >&2
            usage >&2
            exit 2
            ;;
    esac
done
shift $((OPTIND - 1))

# --- Validate timeout: must be a positive whole number ---
if ! [[ "${PROBE_TIMEOUT}" =~ ^[0-9]+$ ]]; then
    echo "Error: timeout must be a non-negative integer, got '${PROBE_TIMEOUT}'" >&2
    usage >&2
    exit 2
fi

# --- Validate / prepare output directory ---
if [[ ! -d "${OUTPUT_DIR}" ]]; then
    if ! mkdir -p "${OUTPUT_DIR}" 2>/dev/null; then
        echo "Error: output directory '${OUTPUT_DIR}' does not exist and could not be created" >&2
        exit 2
    fi
fi
if [[ ! -w "${OUTPUT_DIR}" ]]; then
    echo "Error: output directory '${OUTPUT_DIR}' is not writable" >&2
    exit 2
fi

# --- Main run ---
log_info "netwatch.sh starting — inventory=${INVENTORY_PATH} timeout=${PROBE_TIMEOUT}s report_only=${REPORT_ONLY}" | tee -a "${LOG_FILE}"

# TODO (Member 1): replace this block with real FR-S01 inventory validation
#                   + FR-S03 reachability probing, producing one write_history
#                   call per validated target.
write_history "${HISTORY_FILE}" "test-host" "127.0.0.1" "http" "8080" "UP" "12ms"

log_info "Run complete — 1 record written to ${HISTORY_FILE}" | tee -a "${LOG_FILE}"

# TODO (Member 2): FR-S05 — invoke netwatch.py (INT-02), then read
#                   data/history.csv + Python's results and produce the
#                   merged on-screen table + reports/ CSV (INT-03).