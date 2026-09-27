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

TMP_REPORT=""
# shellcheck disable=SC2329
cleanup_on_signal() {
    echo "" >&2
    echo "Interrupted — cleaning up..." >&2
    [[ -n "${TMP_REPORT}" && -f "${TMP_REPORT}" ]] && rm -f "${TMP_REPORT}"
    exit 130
}
trap cleanup_on_signal INT TERM

# --- Defaults (documented above in the usage block) ---
INVENTORY_PATH="${SCRIPT_DIR}/config/inventory.csv"
OUTPUT_DIR="${SCRIPT_DIR}/reports"
PROBE_TIMEOUT=2
REPORT_ONLY=0

HISTORY_FILE="${SCRIPT_DIR}/data/history.csv"
LOG_FILE="${SCRIPT_DIR}/logs/netwatch.log"
PYTHON_SCRIPT="${SCRIPT_DIR}/../python/netwatch.py"
PYTHON_REPORT_DIR="${SCRIPT_DIR}/../reports"

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

if [[ "$#" -gt 0 ]]; then
    echo "Error: unexpected argument '${1}'" >&2
    usage >&2
    exit 2
fi

# --- Validate timeout: must be a positive whole number ---
if ! [[ "${PROBE_TIMEOUT}" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: timeout must be a positive integer, got '${PROBE_TIMEOUT}'" >&2
    usage >&2
    exit 2
fi

# --- Validate / prepare output directory ---
if [[ ! -d "${OUTPUT_DIR}" ]]; then
    if ! mkdir -p "${OUTPUT_DIR}" 2>/dev/null; then
        echo "Error: output directory '${OUTPUT_DIR}' could not be created" >&2
        exit 2
    fi
fi
if [[ ! -w "${OUTPUT_DIR}" ]]; then
    echo "Error: output directory '${OUTPUT_DIR}' is not writable" >&2
    exit 2
fi

mkdir -p "${SCRIPT_DIR}/data" "${SCRIPT_DIR}/logs" "${SCRIPT_DIR}/reports"
touch "${HISTORY_FILE}" "${LOG_FILE}"
log_info "netwatch.sh starting — inventory=${INVENTORY_PATH} timeout=${PROBE_TIMEOUT}s report_only=${REPORT_ONLY}" | tee -a "${LOG_FILE}"

if [[ ! -r "${INVENTORY_PATH}" ]]; then
    echo "Error: inventory '${INVENTORY_PATH}' is missing or unreadable" >&2
    exit 3
fi
if [[ ! -s "${INVENTORY_PATH}" ]]; then
    echo "Error: inventory '${INVENTORY_PATH}' is empty" >&2
    exit 3
fi

if [[ "${REPORT_ONLY}" -eq 0 ]]; then
    line_number=1
    accepted=0
    rejected=0
    IFS= read -r header < "${INVENTORY_PATH}" || true
    header="$(trim "${header}")"
    if [[ "${header}" != "hostname,ip_address,service,port,critical" ]]; then
        echo "Error: inventory header is invalid; expected hostname,ip_address,service,port,critical" >&2
        exit 3
    fi
    while IFS= read -r line || [[ -n "${line}" ]]; do
        line_number=$((line_number + 1))
        [[ "${line_number}" -eq 2 ]] && continue
        if [[ -z "${line//[[:space:]]/}" ]]; then
            log_error "Rejected inventory line ${line_number}: blank row"
            rejected=$((rejected + 1))
            continue
        fi

        IFS=',' read -r hostname address service port critical extra <<< "${line}"
        hostname="$(trim "${hostname}")"
        address="$(trim "${address}")"
        service="$(trim "${service}")"
        port="$(trim "${port}")"
        critical="$(trim "${critical}")"
        extra="$(trim "${extra:-}")"
        if [[ -n "${extra}" || -z "${hostname}" || -z "${address}" || -z "${service}" || -z "${port}" || -z "${critical}" ]]; then
            log_error "Rejected inventory line ${line_number}: expected five fields"
            rejected=$((rejected + 1))
            continue
        fi
        if ! [[ "${address}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
            log_error "Rejected inventory line ${line_number}: invalid IPv4 address '${address}'"
            rejected=$((rejected + 1))
            continue
        fi
        valid_address=1
        IFS='.' read -r octet1 octet2 octet3 octet4 <<< "${address}"
        for octet in "${octet1}" "${octet2}" "${octet3}" "${octet4}"; do
            if ((10#${octet} > 255)); then valid_address=0; fi
        done
        if [[ "${valid_address}" -eq 0 ]]; then
            log_error "Rejected inventory line ${line_number}: invalid IPv4 address '${address}'"
            rejected=$((rejected + 1))
            continue
        fi
        if ! [[ "${port}" =~ ^[0-9]+$ ]] || ((port < 1 || port > 65535)); then
            log_error "Rejected inventory line ${line_number}: invalid port '${port}'"
            rejected=$((rejected + 1))
            continue
        fi
        if ! [[ "${critical}" == "yes" || "${critical}" == "no" ]]; then
            log_error "Rejected inventory line ${line_number}: critical must be yes or no"
            rejected=$((rejected + 1))
            continue
        fi

        probe_result="$(ping_host "${address}" "${PROBE_TIMEOUT}")"
        status="${probe_result%%|*}"
        rtt="${probe_result#*|}"
        write_history "${HISTORY_FILE}" "${hostname}" "${address}" "${service}" "${port}" "${status}" "${rtt}"
        log_info "${hostname} (${address}) is ${status}"
        accepted=$((accepted + 1))
    done < "${INVENTORY_PATH}"
    log_info "Inventory: ${accepted} accepted, ${rejected} rejected"

    if [[ -f "${PYTHON_SCRIPT}" ]]; then
        python3 "${PYTHON_SCRIPT}" --mode concurrent --inventory "${INVENTORY_PATH}" \
            --timeout "${PROBE_TIMEOUT}" \
            --output-dir "${SCRIPT_DIR}/../data" --report-dir "${SCRIPT_DIR}/../reports" || python_status=$?
        python_status="${python_status:-0}"
        if [[ "${python_status}" -gt 1 ]]; then
            log_error "Python service scan failed with exit code ${python_status}"
        fi
        python_report="$(find "${PYTHON_REPORT_DIR}" -maxdepth 1 -name 'py_results_*.csv' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -n 1 | cut -d' ' -f2-)"
    fi
else
    log_info "Report-only mode: existing history will be reported"
fi

# --- Main run ---
report_path="${OUTPUT_DIR}/netwatch_$(date '+%Y%m%dT%H%M%S').csv"
TMP_REPORT="${report_path}.tmp"
printf 'timestamp,hostname,ip_address,service,port,status,rtt,python_state,python_response_time\n' > "${TMP_REPORT}"
if [[ -s "${HISTORY_FILE}" ]]; then
    while IFS=',' read -r timestamp hostname address service port status rtt; do
        python_state=""
        python_time=""
        if [[ -n "${python_report:-}" ]]; then
            python_row="$(awk -F',' -v host="${hostname}" -v wanted_port="${port}" 'NR > 1 && $2 == host && $5 == wanted_port {print; exit}' "${python_report}")"
            if [[ -n "${python_row}" ]]; then
                IFS=',' read -r _ _ _ _ _ _ python_state python_time _ <<< "${python_row}"
            fi
        fi
        printf '%s,%s,%s,%s,%s,%s,%s,%s,%s\n' "${timestamp}" "${hostname}" "${address}" "${service}" "${port}" "${status}" "${rtt}" "${python_state}" "${python_time}" >> "${TMP_REPORT}"
    done < "${HISTORY_FILE}"
fi
mv "${TMP_REPORT}" "${report_path}"
TMP_REPORT=""
printf '\n%-22s %-16s %-8s %-8s %-8s\n' 'HOSTNAME' 'ADDRESS' 'STATUS' 'SERVICE' 'PORT'
if [[ -s "${HISTORY_FILE}" ]]; then
    tail -n 6 "${HISTORY_FILE}" | while IFS=',' read -r timestamp hostname address service port status rtt; do
        printf '%-22s %-16s %-8s %-8s %-8s\n' "${hostname}" "${address}" "${status}" "${service}" "${port}"
    done
else
    printf '%s\n' 'No history records yet.'
fi
if [[ -s "${HISTORY_FILE}" ]]; then
    total_checks="$(awk 'END {print NR}' "${HISTORY_FILE}")"
    up_checks="$(awk -F',' '$6 == "UP" {count++} END {print count + 0}' "${HISTORY_FILE}")"
    down_checks="$(awk -F',' '$6 == "DOWN" {count++} END {print count + 0}' "${HISTORY_FILE}")"
    printf '\nChecks: %s | UP: %s | DOWN: %s | Availability: %.1f%%\n' \
        "${total_checks}" "${up_checks}" "${down_checks}" \
        "$(awk -v up="${up_checks}" -v total="${total_checks}" 'BEGIN {if (total == 0) print 0; else print 100 * up / total}')"
    printf '%s\n' 'Availability by host:'
    awk -F',' '{total[$2]++; if ($6 == "UP") up[$2]++} END {for (host in total) printf "  %-22s %.1f%% (%d/%d)\n", host, 100 * up[host] / total[host], up[host] + 0, total[host]}' "${HISTORY_FILE}" | sort
    printf '%s\n' 'Most frequent failing services:'
    awk -F',' '$6 == "DOWN" {fail[$4]++} END {for (service in fail) print fail[service], service}' "${HISTORY_FILE}" | sort -rn | head -n 3 | awk '{printf "  %-18s %s failures\n", $2, $1}'
fi
log_info "Run complete — report written to ${report_path}" | tee -a "${LOG_FILE}"

if [[ "${python_status:-0}" -eq 3 ]]; then
    exit 3
elif [[ "${python_status:-0}" -eq 1 ]]; then
    exit 1
fi
exit 0
