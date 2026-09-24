#!/usr/bin/env bash
#
# helpers.sh — Shared function library for NetWatch (Part A)
#
# STATUS: STUB — placeholder implementations for Member 2 (Ken) to test
#         FR-S04 against, pending Member 1's real FR-S01/FR-S03 + library work.
#         Function names/signatures below are a proposal, not final —
#         confirm with Member 1 before relying on them long-term.
#
# Author: <Member 1 name> (stub by Ken, pending real implementation)
#

# log_info MESSAGE
#   Writes an informational message to stdout, timestamped.
log_info() {
    local message="$1"
    printf '[%s] INFO: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "${message}"
}

# log_error MESSAGE
#   Writes an error message to stderr, timestamped.
log_error() {
    local message="$1"
    printf '[%s] ERROR: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "${message}" >&2
}

# write_history HISTORY_FILE HOSTNAME ADDRESS SERVICE PORT STATUS [RTT]
#   Appends one timestamped record to the history CSV.
#   Format: timestamp,hostname,address,service,port,status,rtt
write_history() {
    local history_file="$1"
    local hostname="$2"
    local address="$3"
    local service="$4"
    local port="$5"
    local status="$6"
    local rtt="${7:-}"
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"

    printf '%s,%s,%s,%s,%s,%s,%s\n' \
        "${timestamp}" "${hostname}" "${address}" "${service}" "${port}" "${status}" "${rtt}" \
        >> "${history_file}"
}