#!/bin/bash
set -euo pipefail

# =============================================================================
# CONFIGURATION CONSTANTS
# =============================================================================

# Destination ownership settings
readonly DEST_UID=1000
readonly DEST_GID=140

# Rsync timeout in seconds (10 minutes)
readonly RSYNC_TIMEOUT=600

# =============================================================================
# ENVIRONMENT VARIABLES
# =============================================================================

# Map JOB_COMPLETION_INDEX (0-25) to letter (A-Z), index 26 = nonalpha
INDEX=${JOB_COMPLETION_INDEX:-0}
LETTERS=(A B C D E F G H I J K L M N O P Q R S T U V W X Y Z)

if [ "$INDEX" -eq 26 ]; then
    LETTER="nonalpha"
else
    LETTER=${LETTERS[$INDEX]}
fi

# Allow override via environment variables
SOURCE="${SOURCE:-/tower-2/movies}"
DEST="${DEST:-/destination/movies}"
LOG_DIR="/metrics"
LOG_FILE="${LOG_DIR}/migration-${LETTER}.log"
ERROR_LOG="${LOG_DIR}/errors-${LETTER}.log"
CHECKPOINT="${LOG_DIR}/completed-${LETTER}.txt"

# DRY RUN MODE: Set DRY_RUN=true to test without deleting source files
DRY_RUN="${DRY_RUN:-false}"

# Concurrency: Process N directories in parallel within single pod
PARALLEL_JOBS="${PARALLEL_JOBS:-4}"

# Ensure log directory and archive directory exist
mkdir -p "${LOG_DIR}"
mkdir -p "${LOG_DIR}/archive"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

# Retry settings for transient storage errors
readonly MAX_RETRIES=3
readonly RETRY_DELAY=2

# Check if running in dry-run mode
# Returns: 0 if dry-run, 1 if production mode
is_dry_run() {
    [ "${DRY_RUN}" = "true" ] || [ "${DRY_RUN}" = "1" ]
}

# Resilient file append - handles transient mount failures
# Args: $1 - Text to append, $2 - File path
# Usage: safe_append "message" "/path/to/file.log"
safe_append() {
    local text="$1"
    local file="$2"
    local retries=${MAX_RETRIES}
    while ! echo "$text" >> "$file" 2>/dev/null; do
        ((retries--)) || { echo "[WARN] Failed to append to $file after ${MAX_RETRIES} retries" >&2; return 1; }
        sleep ${RETRY_DELAY}
    done
    return 0
}

# Wrapper for tee -a with retry logic
# Args: $1 - Log file path
# Usage: echo "message" | safe_tee "/path/to/file.log"
safe_tee() {
    local file="$1"
    local line
    while IFS= read -r line; do
        echo "$line"
        safe_append "$line" "$file"
    done
}

# Archive old logs for this letter before starting new run
# Creates timestamped tar.gz archive and removes old log files
# Ensures fresh logs for each run while preserving history
archive_old_logs() {
    local timestamp
    timestamp=$(date +%Y-%m-%dT%H:%M:%S)
    local archive_name="${LOG_DIR}/archive/letter-${LETTER}-${timestamp}.tar.gz"

    # Collect files to archive using array (handles spaces in filenames)
    local -a files_to_archive=()

    # Main letter logs
    [ -f "${LOG_FILE}" ] && files_to_archive+=("${LOG_FILE}")
    [ -f "${ERROR_LOG}" ] && files_to_archive+=("${ERROR_LOG}")

    # Individual directory logs for this letter (properly quoted glob)
    while IFS= read -r -d '' logfile; do
        files_to_archive+=("$logfile")
    done < <(find "${LOG_DIR}" -maxdepth 1 -name "dir-${LETTER}-*.log" -print0 2>/dev/null || true)

    # Only archive if there are files to archive
    if [ ${#files_to_archive[@]} -gt 0 ]; then
        echo "[$(date)] Archiving previous run logs to ${archive_name}..." | safe_tee "${LOG_FILE}.new"
        tar -czf "${archive_name}" "${files_to_archive[@]}" 2>/dev/null || true

        # Remove archived files
        for file in "${files_to_archive[@]}"; do
            rm -f "${file}" 2>/dev/null || true
        done

        echo "[$(date)] ✓ Previous logs archived successfully" | safe_tee "${LOG_FILE}.new"
    fi
}

# Archive old logs before starting (to get fresh stats on re-runs)
archive_old_logs

# Rename temporary log file to actual log file
[ -f "${LOG_FILE}.new" ] && mv "${LOG_FILE}.new" "${LOG_FILE}"

# Build rsync options for transfer operations
# Returns: Space-separated string of rsync options
# Note: Adds --remove-source-files in production mode, --dry-run in dry-run mode
build_rsync_opts() {
    local opts=(
        --archive              # Preserve permissions, timestamps, etc
        --verbose              # Detailed output
        --human-readable       # Human-readable sizes
        --progress             # Show progress during transfer
        --stats                # Show transfer statistics
        --partial              # Keep partially transferred files
        --inplace              # Update files in-place
        --no-whole-file        # Use delta transfer algorithm
        --compress-level=0     # No compression (local network)
        --timeout="${RSYNC_TIMEOUT}"
    )

    # Add dry-run flag if DRY_RUN is enabled, otherwise add remove-source-files
    if is_dry_run; then
        opts+=(--dry-run)
    else
        opts+=(--remove-source-files)  # Delete source files after successful transfer
    fi

    echo "${opts[@]}"
}

# Store start time for duration calculation
START_TIME=$(date +%s)
START_TIMESTAMP=$(date)

# Display enhanced header with mode and configuration
echo "======================================" | safe_tee "${LOG_FILE}"
if [ "$LETTER" = "nonalpha" ]; then
    echo "MIGRATION JOB - Non-Alphabetic Directories (Index: ${INDEX})" | safe_tee "${LOG_FILE}"
else
    echo "MIGRATION JOB - Letter ${LETTER} (Index: ${INDEX})" | safe_tee "${LOG_FILE}"
fi
echo "======================================" | safe_tee "${LOG_FILE}"

if is_dry_run; then
    echo "Mode: DRY-RUN (no files will be deleted)" | safe_tee "${LOG_FILE}"
else
    echo "Mode: PRODUCTION (files will be deleted after transfer)" | safe_tee "${LOG_FILE}"
fi

echo "Source:      ${SOURCE}" | safe_tee "${LOG_FILE}"
echo "Destination: ${DEST}" | safe_tee "${LOG_FILE}"
echo "Parallel Workers: ${PARALLEL_JOBS}" | safe_tee "${LOG_FILE}"
echo "Started: ${START_TIMESTAMP}" | safe_tee "${LOG_FILE}"
echo "======================================" | safe_tee "${LOG_FILE}"
echo "" | safe_tee "${LOG_FILE}"

# Get list of directories to process
if [ "$LETTER" = "nonalpha" ]; then
    echo "[$(date)] Scanning source for directories starting with non-alphabetic chars..." | safe_tee "${LOG_FILE}"
else
    echo "[$(date)] Scanning source for directories starting with '${LETTER}'..." | safe_tee "${LOG_FILE}"
fi
TMPFILE=$(mktemp -t "migration-dirs-${LETTER}.XXXXXX")

# Use ls instead of find to avoid race conditions with parallel deletions
# Ignore errors from directories being deleted during scan
if [ "$LETTER" = "nonalpha" ]; then
    # Find directories NOT starting with A-Za-z (numbers, special chars, etc.)
    if ! (cd "${SOURCE}" && ls -1d */ 2>/dev/null | sed 's|/$||' | grep -v '^[A-Za-z]' | sort > "${TMPFILE}"); then
        touch "${TMPFILE}"
    fi
else
    # Standard: find directories starting with specific letter
    if ! (cd "${SOURCE}" && ls -1d "${LETTER}"* 2>/dev/null | sort > "${TMPFILE}"); then
        touch "${TMPFILE}"
    fi
fi

TOTAL_DIRS=$(wc -l < "${TMPFILE}")

# Load checkpoint file to see what's already been processed
touch "${CHECKPOINT}"
COMPLETED_COUNT=$(wc -l < "${CHECKPOINT}")

if [ ${TOTAL_DIRS} -eq 0 ]; then
    echo "[$(date)] ✓ Scan complete: 0 directories found" | safe_tee "${LOG_FILE}"
    echo "[$(date)] ℹ️  Nothing to migrate - all '${LETTER}' directories already processed or don't exist" | safe_tee "${LOG_FILE}"
    echo "" | safe_tee "${LOG_FILE}"

    # Print summary for empty job
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    echo "======================================" | safe_tee "${LOG_FILE}"
    echo "MIGRATION COMPLETE - Letter ${LETTER}" | safe_tee "${LOG_FILE}"
    echo "======================================" | safe_tee "${LOG_FILE}"
    echo "Started:  ${START_TIMESTAMP}" | safe_tee "${LOG_FILE}"
    echo "Finished: $(date)" | safe_tee "${LOG_FILE}"
    echo "Duration: ${DURATION} seconds" | safe_tee "${LOG_FILE}"
    echo "" | safe_tee "${LOG_FILE}"
    echo "Directories scanned:      ${TOTAL_DIRS}" | safe_tee "${LOG_FILE}"
    echo "Previously completed:     ${COMPLETED_COUNT}" | safe_tee "${LOG_FILE}"
    echo "" | safe_tee "${LOG_FILE}"
    echo "Status: ✓ SUCCESS - Nothing to migrate" | safe_tee "${LOG_FILE}"
    echo "======================================" | safe_tee "${LOG_FILE}"

    rm -f "${TMPFILE}"
    exit 0
fi

echo "[$(date)] ✓ Scan complete: ${TOTAL_DIRS} directories found" | safe_tee "${LOG_FILE}"
echo "[$(date)] Previously completed: ${COMPLETED_COUNT} directories" | safe_tee "${LOG_FILE}"
echo "" | safe_tee "${LOG_FILE}"

# Counters (shared via files for parallel access)
COUNTER_FILE=$(mktemp -t "migration-counter-${LETTER}.XXXXXX")
SUCCESS_FILE=$(mktemp -t "migration-success-${LETTER}.XXXXXX")
SKIP_FILE=$(mktemp -t "migration-skip-${LETTER}.XXXXXX")
FAIL_FILE=$(mktemp -t "migration-fail-${LETTER}.XXXXXX")
echo "0" > "${COUNTER_FILE}"
echo "0" > "${SUCCESS_FILE}"
echo "0" > "${SKIP_FILE}"
echo "0" > "${FAIL_FILE}"

# Atomically increment a counter file using flock
# Args: $1 - Path to counter file
# Uses file locking to prevent race conditions in parallel execution
increment_counter() {
    local file="$1"
    local lockfile="${file}.lock"
    (
        flock -x 200
        local val
        val=$(cat "$file")
        echo $((val + 1)) > "$file"
    ) 200>"$lockfile"
}

# Process a single movie directory (transfer, set ownership, cleanup)
# Args: $1 - Directory name to process
# Phases:
#   1. Transfer files with rsync (--remove-source-files in production)
#   2. Set ownership/permissions on destination
#   3. Clean up empty source directories
# Returns: 0 on success, 1 on failure
process_directory() {
    local dir_name="$1"
    local dir_log="${LOG_DIR}/dir-${LETTER}-${dir_name//[^a-zA-Z0-9]/_}.log"

    # Skip empty lines
    [ -z "${dir_name}" ] && return 0

    increment_counter "${COUNTER_FILE}"
    local counter=$(cat "${COUNTER_FILE}")

    # Check if already completed (with file locking)
    if grep -qFx "${dir_name}" "${CHECKPOINT}" 2>/dev/null; then
        echo "[$(date)] [${counter}/${TOTAL_DIRS}] SKIPPING ${dir_name} (already completed)" | safe_tee "${LOG_FILE}"
        increment_counter "${SKIP_FILE}"
        return 0
    fi

    echo "" | safe_tee "${LOG_FILE}"
    echo "======================================" | safe_tee "${LOG_FILE}"
    echo "[$(date)] [${counter}/${TOTAL_DIRS}] Processing: ${dir_name}" | safe_tee "${LOG_FILE}"
    echo "======================================" | safe_tee "${LOG_FILE}"

    # PHASE 1: Transfer and remove source files atomically
    echo "[$(date)] Transferring ${dir_name}..." | safe_tee "${LOG_FILE}"

    # Count files before transfer for logging
    SOURCE_COUNT=$(find "${SOURCE}/${dir_name}" -type f 2>/dev/null | wc -l)

    if [ "${SOURCE_COUNT}" -eq 0 ]; then
        echo "[$(date)] ℹ️  No files to transfer (already migrated)" | safe_tee "${LOG_FILE}"
    else
        echo "[$(date)] Found ${SOURCE_COUNT} files to transfer" | safe_tee "${LOG_FILE}"
    fi

    # Build rsync options as array
    # Note: --remove-source-files is added automatically (unless DRY_RUN=true)
    local rsync_opts
    read -ra rsync_opts <<< "$(build_rsync_opts)"

    # MERGE MODE: rsync will add source files to destination (destination may have more files from other sources)
    # With --remove-source-files, rsync will only delete source files after successful transfer
    # Capture stderr for resilient logging
    local rsync_stderr
    rsync_stderr=$(mktemp -t "rsync-stderr-${LETTER}.XXXXXX")
    if rsync "${rsync_opts[@]}" \
        --log-file="${dir_log}" \
        "${SOURCE}/${dir_name}/" \
        "${DEST}/${dir_name}/" 2>"${rsync_stderr}"; then

        if is_dry_run; then
            echo "[$(date)] ✓ DRY-RUN: Transfer simulated for ${dir_name}" | safe_tee "${LOG_FILE}"
        else
            echo "[$(date)] ✓ Transfer completed and source files removed for ${dir_name}" | safe_tee "${LOG_FILE}"
        fi
        rm -f "${rsync_stderr}"
    else
        rsync_exit=$?
        # Append captured stderr to error log with retry
        [ -s "${rsync_stderr}" ] && while IFS= read -r line; do safe_append "$line" "${ERROR_LOG}"; done < "${rsync_stderr}"
        rm -f "${rsync_stderr}"
        echo "ERROR: rsync failed for ${dir_name} (exit code: ${rsync_exit})" | safe_tee "${ERROR_LOG}"
        echo "SOURCE FILES NOT DELETED - rsync detected an error" | safe_tee "${ERROR_LOG}"
        increment_counter "${FAIL_FILE}"
        return 1
    fi

    # PHASE 2: Set ownership (SKIP IN DRY-RUN MODE)
    if is_dry_run; then
        echo "[$(date)] DRY-RUN: Skipping ownership changes for ${dir_name}" | safe_tee "${LOG_FILE}"
    else
        echo "[$(date)] Setting ownership for ${dir_name}..." | safe_tee "${LOG_FILE}"
        local chown_err
        chown_err=$(chown -R "${DEST_UID}:${DEST_GID}" "${DEST}/${dir_name}" 2>&1) || safe_append "${chown_err}" "${ERROR_LOG}"
        local chmod_err
        chmod_err=$(chmod -R u=rwX,g=rX,o=rX "${DEST}/${dir_name}" 2>&1) || safe_append "${chmod_err}" "${ERROR_LOG}"
    fi

    # PHASE 3: Clean up empty source directories (SKIP IN DRY-RUN MODE)
    # Note: --remove-source-files only removes files, not directories
    if is_dry_run; then
        echo "[$(date)] DRY-RUN: Skipping empty directory cleanup for ${dir_name}" | safe_tee "${LOG_FILE}"
    else
        if [ -d "${SOURCE}/${dir_name}" ]; then
            # Remove empty directories recursively (bottom-up)
            local find_err
            find_err=$(find "${SOURCE}/${dir_name}" -type d -empty -delete 2>&1) || safe_append "${find_err}" "${ERROR_LOG}"

            # Remove the parent directory if it's now empty
            if [ -d "${SOURCE}/${dir_name}" ]; then
                local rmdir_err
                rmdir_err=$(rmdir "${SOURCE}/${dir_name}" 2>&1) || {
                    safe_append "${rmdir_err}" "${ERROR_LOG}"
                    echo "[$(date)] ⚠ Source directory not empty (may contain subdirs or files): ${dir_name}" | safe_tee "${LOG_FILE}"
                }
            else
                echo "[$(date)] ✓ Empty source directory removed: ${dir_name}" | safe_tee "${LOG_FILE}"
            fi
        fi
    fi

    # Mark as complete (with file locking and retry)
    (
        flock -x 200
        safe_append "${dir_name}" "${CHECKPOINT}"
    ) 200>"${CHECKPOINT}.lock"

    increment_counter "${SUCCESS_FILE}"
    return 0
}

# Export functions and variables for parallel execution
export -f process_directory
export -f increment_counter
export -f build_rsync_opts
export -f is_dry_run
export -f safe_append
export -f safe_tee
export SOURCE DEST LOG_DIR LOG_FILE ERROR_LOG CHECKPOINT
export COUNTER_FILE SUCCESS_FILE SKIP_FILE FAIL_FILE TOTAL_DIRS LETTER DRY_RUN
export DEST_UID DEST_GID RSYNC_TIMEOUT MAX_RETRIES RETRY_DELAY
export PATH

# Process directories in parallel using xargs
echo "[$(date)] Starting parallel processing with ${PARALLEL_JOBS} workers..." | safe_tee "${LOG_FILE}"

# Note: Pass directory name as $1 to avoid shell expansion of special chars like $
cat "${TMPFILE}" | tr '\n' '\0' | xargs -0 -P "${PARALLEL_JOBS}" -I {} bash -c 'process_directory "$1"' _ {} || true

# Read final counters (xargs waits for all processes by default)
success_count=$(cat "${SUCCESS_FILE}")
skip_count=$(cat "${SKIP_FILE}")
fail_count=$(cat "${FAIL_FILE}")

# Calculate duration
END_TIME=$(date +%s)
END_TIMESTAMP=$(date)
DURATION=$((END_TIME - START_TIME))
DURATION_MIN=$((DURATION / 60))
DURATION_SEC=$((DURATION % 60))

# Cleanup temp files
rm -f "${TMPFILE}" "${COUNTER_FILE}" "${SUCCESS_FILE}" "${SKIP_FILE}" "${FAIL_FILE}"

# Enhanced completion summary
echo "" | safe_tee "${LOG_FILE}"
echo "======================================" | safe_tee "${LOG_FILE}"
echo "MIGRATION COMPLETE - Letter ${LETTER}" | safe_tee "${LOG_FILE}"
echo "======================================" | safe_tee "${LOG_FILE}"
echo "Started:  ${START_TIMESTAMP}" | safe_tee "${LOG_FILE}"
echo "Finished: ${END_TIMESTAMP}" | safe_tee "${LOG_FILE}"

if [ ${DURATION_MIN} -gt 0 ]; then
    echo "Duration: ${DURATION_MIN} minutes ${DURATION_SEC} seconds" | safe_tee "${LOG_FILE}"
else
    echo "Duration: ${DURATION_SEC} seconds" | safe_tee "${LOG_FILE}"
fi

echo "" | safe_tee "${LOG_FILE}"
echo "Directories scanned:      ${TOTAL_DIRS}" | safe_tee "${LOG_FILE}"
echo "Previously completed:     ${COMPLETED_COUNT}" | safe_tee "${LOG_FILE}"
echo "Newly migrated:           ${success_count}" | safe_tee "${LOG_FILE}"
echo "Skipped (already done):   ${skip_count}" | safe_tee "${LOG_FILE}"
echo "Failed:                   ${fail_count}" | safe_tee "${LOG_FILE}"
echo "" | safe_tee "${LOG_FILE}"

# Status indicator
if [ ${fail_count} -gt 0 ]; then
    echo "Status: ⚠ COMPLETED WITH ERRORS" | safe_tee "${LOG_FILE}"
    echo "See ${ERROR_LOG} for details" | safe_tee "${LOG_FILE}"
    echo "======================================" | safe_tee "${LOG_FILE}"
    exit 1
elif [ ${success_count} -gt 0 ]; then
    if is_dry_run; then
        echo "Status: ✓ DRY-RUN SUCCESS - ${success_count} directories simulated" | safe_tee "${LOG_FILE}"
    else
        echo "Status: ✓ SUCCESS - ${success_count} directories migrated" | safe_tee "${LOG_FILE}"
    fi
    echo "======================================" | safe_tee "${LOG_FILE}"
    exit 0
else
    echo "Status: ✓ SUCCESS - All directories already migrated" | safe_tee "${LOG_FILE}"
    echo "======================================" | safe_tee "${LOG_FILE}"
    exit 0
fi
