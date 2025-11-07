#!/bin/bash
set -euo pipefail

# Map JOB_COMPLETION_INDEX (0-25) to letter (A-Z)
INDEX=${JOB_COMPLETION_INDEX:-0}
LETTERS=(A B C D E F G H I J K L M N O P Q R S T U V W X Y Z)
LETTER=${LETTERS[$INDEX]}

# Allow override via environment variables
SOURCE="${SOURCE:-/tower-2/movies}"
DEST="${DEST:-/destination/movies}"
LOG_DIR="/metrics"
LOG_FILE="${LOG_DIR}/migration-${LETTER}.log"
ERROR_LOG="${LOG_DIR}/errors-${LETTER}.log"
CHECKPOINT="${LOG_DIR}/completed-${LETTER}.txt"
VERIFICATION_LOG="${LOG_DIR}/verify-${LETTER}.log"

# DRY RUN MODE: Set DRY_RUN=true to test without deleting source files
DRY_RUN="${DRY_RUN:-false}"

# Concurrency: Process N directories in parallel within single pod
# NFS mount constraint: Only 1 pod allowed, but can use internal parallelism
PARALLEL_JOBS="${PARALLEL_JOBS:-4}"

# Ensure log directory exists
mkdir -p "${LOG_DIR}"

# Build rsync options function (called in subshells)
build_rsync_opts() {
    local opts=(
        --archive
        --verbose
        --human-readable
        --progress
        --stats
        --partial
        --inplace
        --no-whole-file
        --compress-level=0
        --timeout=600
    )

    # Add dry-run flag if DRY_RUN is enabled, otherwise add remove-source-files
    if [ "${DRY_RUN}" = "true" ] || [ "${DRY_RUN}" = "1" ]; then
        opts+=(--dry-run)
    else
        opts+=(--remove-source-files)
    fi

    echo "${opts[@]}"
}

# Display dry-run warning if enabled
if [ "${DRY_RUN}" = "true" ] || [ "${DRY_RUN}" = "1" ]; then
    echo "========== DRY RUN MODE ENABLED ==========" | tee -a "${LOG_FILE}"
    echo "WARNING: Source files will NOT be deleted!" | tee -a "${LOG_FILE}"
    echo "==========================================" | tee -a "${LOG_FILE}"
fi

echo "======================================" | tee -a "${LOG_FILE}"
echo "Job Index: ${INDEX}" | tee -a "${LOG_FILE}"
echo "Processing Letter: ${LETTER}" | tee -a "${LOG_FILE}"
echo "Parallel Jobs: ${PARALLEL_JOBS}" | tee -a "${LOG_FILE}"
echo "Started at: $(date)" | tee -a "${LOG_FILE}"
echo "======================================" | tee -a "${LOG_FILE}"

# Get list of all directories starting with this letter
echo "[$(date)] Scanning for directories starting with ${LETTER}..." | tee -a "${LOG_FILE}"
TMPFILE="/tmp/dirs-${LETTER}.txt"

# Use ls instead of find to avoid race conditions with parallel deletions
# Ignore errors from directories being deleted during scan
if ! (cd "${SOURCE}" && ls -1d "${LETTER}"* 2>/dev/null | sort > "${TMPFILE}"); then
    # If ls fails completely (e.g., no matches), create empty file
    touch "${TMPFILE}"
fi

TOTAL_DIRS=$(wc -l < "${TMPFILE}")

if [ ${TOTAL_DIRS} -eq 0 ]; then
    echo "[$(date)] No directories found for letter ${LETTER}, skipping..." | tee -a "${LOG_FILE}"
    rm -f "${TMPFILE}"
    exit 0
fi

echo "[$(date)] Found ${TOTAL_DIRS} directories for letter ${LETTER}" | tee -a "${LOG_FILE}"

# Load checkpoint file if exists
touch "${CHECKPOINT}"
COMPLETED_COUNT=$(wc -l < "${CHECKPOINT}")
echo "[$(date)] Previously completed: ${COMPLETED_COUNT} directories" | tee -a "${LOG_FILE}"

# Counters (shared via files for parallel access)
COUNTER_FILE="/tmp/counter-${LETTER}.txt"
SUCCESS_FILE="/tmp/success-${LETTER}.txt"
SKIP_FILE="/tmp/skip-${LETTER}.txt"
FAIL_FILE="/tmp/fail-${LETTER}.txt"
echo "0" > "${COUNTER_FILE}"
echo "0" > "${SUCCESS_FILE}"
echo "0" > "${SKIP_FILE}"
echo "0" > "${FAIL_FILE}"

# Function to increment counter atomically
increment_counter() {
    local file="$1"
    local lockfile="${file}.lock"
    (
        flock -x 200
        local val=$(cat "$file")
        echo $((val + 1)) > "$file"
    ) 200>"$lockfile"
}

# Function to process a single directory
process_directory() {
    local dir_name="$1"
    local dir_log="${LOG_DIR}/dir-${LETTER}-${dir_name//[^a-zA-Z0-9]/_}.log"

    # Skip empty lines
    [ -z "${dir_name}" ] && return 0

    increment_counter "${COUNTER_FILE}"
    local counter=$(cat "${COUNTER_FILE}")

    # Check if already completed (with file locking)
    if grep -qFx "${dir_name}" "${CHECKPOINT}" 2>/dev/null; then
        echo "[$(date)] [${counter}/${TOTAL_DIRS}] SKIPPING ${dir_name} (already completed)" | tee -a "${LOG_FILE}"
        increment_counter "${SKIP_FILE}"
        return 0
    fi

    echo "" | tee -a "${LOG_FILE}"
    echo "======================================" | tee -a "${LOG_FILE}"
    echo "[$(date)] [${counter}/${TOTAL_DIRS}] Processing: ${dir_name}" | tee -a "${LOG_FILE}"
    echo "======================================" | tee -a "${LOG_FILE}"

    # PHASE 1: Transfer and remove source files atomically
    echo "[$(date)] Transferring ${dir_name}..." | tee -a "${LOG_FILE}"

    # Count files before transfer for logging
    SOURCE_COUNT=$(find "${SOURCE}/${dir_name}" -type f 2>/dev/null | wc -l || echo 0)

    if [ "${SOURCE_COUNT}" -eq 0 ]; then
        echo "[$(date)] ℹ️  No files to transfer (already migrated)" | tee -a "${LOG_FILE}"
    else
        echo "[$(date)] Found ${SOURCE_COUNT} files to transfer" | tee -a "${LOG_FILE}"
    fi

    # Build rsync options as array
    # Note: --remove-source-files is added automatically (unless DRY_RUN=true)
    local rsync_opts
    read -ra rsync_opts <<< "$(build_rsync_opts)"

    # MERGE MODE: rsync will add source files to destination (destination may have more files from other sources)
    # With --remove-source-files, rsync will only delete source files after successful transfer
    if rsync "${rsync_opts[@]}" \
        --log-file="${dir_log}" \
        "${SOURCE}/${dir_name}/" \
        "${DEST}/${dir_name}/" 2>> "${ERROR_LOG}"; then

        if [ "${DRY_RUN}" = "true" ] || [ "${DRY_RUN}" = "1" ]; then
            echo "[$(date)] ✓ DRY-RUN: Transfer simulated for ${dir_name}" | tee -a "${LOG_FILE}"
        else
            echo "[$(date)] ✓ Transfer completed and source files removed for ${dir_name}" | tee -a "${LOG_FILE}"
        fi
    else
        rsync_exit=$?
        echo "ERROR: rsync failed for ${dir_name} (exit code: ${rsync_exit})" | tee -a "${ERROR_LOG}"
        echo "SOURCE FILES NOT DELETED - rsync detected an error" | tee -a "${ERROR_LOG}"
        increment_counter "${FAIL_FILE}"
        return 1
    fi

    # PHASE 2: Set ownership (SKIP IN DRY-RUN MODE)
    if [ "${DRY_RUN}" = "true" ] || [ "${DRY_RUN}" = "1" ]; then
        echo "[$(date)] DRY-RUN: Skipping ownership changes for ${dir_name}" | tee -a "${LOG_FILE}"
    else
        echo "[$(date)] Setting ownership for ${dir_name}..." | tee -a "${LOG_FILE}"
        chown -R 1000:140 "${DEST}/${dir_name}" 2>> "${ERROR_LOG}" || true
        chmod -R u=rwX,g=rX,o=rX "${DEST}/${dir_name}" 2>> "${ERROR_LOG}" || true
    fi

    # PHASE 3: Clean up empty source directories (SKIP IN DRY-RUN MODE)
    # Note: --remove-source-files only removes files, not directories
    if [ "${DRY_RUN}" = "true" ] || [ "${DRY_RUN}" = "1" ]; then
        echo "[$(date)] DRY-RUN: Skipping empty directory cleanup for ${dir_name}" | tee -a "${LOG_FILE}"
    else
        if [ -d "${SOURCE}/${dir_name}" ]; then
            # Remove empty directories recursively (bottom-up)
            find "${SOURCE}/${dir_name}" -type d -empty -delete 2>> "${ERROR_LOG}" || true

            # Remove the parent directory if it's now empty
            if [ -d "${SOURCE}/${dir_name}" ]; then
                rmdir "${SOURCE}/${dir_name}" 2>> "${ERROR_LOG}" || {
                    echo "[$(date)] ⚠ Source directory not empty (may contain subdirs or files): ${dir_name}" | tee -a "${LOG_FILE}"
                }
            else
                echo "[$(date)] ✓ Empty source directory removed: ${dir_name}" | tee -a "${LOG_FILE}"
            fi
        fi
    fi

    # Mark as complete (with file locking)
    (
        flock -x 200
        echo "${dir_name}" >> "${CHECKPOINT}"
    ) 200>"${CHECKPOINT}.lock"

    increment_counter "${SUCCESS_FILE}"
    return 0
}

# Export functions and variables for parallel execution
export -f process_directory
export -f increment_counter
export -f build_rsync_opts
export SOURCE DEST LOG_DIR LOG_FILE ERROR_LOG CHECKPOINT VERIFICATION_LOG
export COUNTER_FILE SUCCESS_FILE SKIP_FILE FAIL_FILE TOTAL_DIRS LETTER DRY_RUN
export PATH

# Process directories in parallel using xargs
echo "[$(date)] Starting parallel processing with ${PARALLEL_JOBS} workers..." | tee -a "${LOG_FILE}"

cat "${TMPFILE}" | tr '\n' '\0' | xargs -0 -I {} -P "${PARALLEL_JOBS}" bash -c 'process_directory "{}"' || true

# Read final counters (xargs waits for all processes by default)
success_count=$(cat "${SUCCESS_FILE}")
skip_count=$(cat "${SKIP_FILE}")
fail_count=$(cat "${FAIL_FILE}")

# Cleanup temp files
rm -f "${TMPFILE}" "${COUNTER_FILE}" "${SUCCESS_FILE}" "${SKIP_FILE}" "${FAIL_FILE}"

echo "" | tee -a "${LOG_FILE}"
echo "======================================" | tee -a "${LOG_FILE}"
echo "Letter ${LETTER} completed at: $(date)" | tee -a "${LOG_FILE}"
echo "Summary:" | tee -a "${LOG_FILE}"
echo "  Total directories: ${TOTAL_DIRS}" | tee -a "${LOG_FILE}"
echo "  Successful: ${success_count}" | tee -a "${LOG_FILE}"
echo "  Skipped: ${skip_count}" | tee -a "${LOG_FILE}"
echo "  Failed: ${fail_count}" | tee -a "${LOG_FILE}"
echo "======================================" | tee -a "${LOG_FILE}"

# Exit with error if any failures
if [ ${fail_count} -gt 0 ]; then
    echo "Job completed with ${fail_count} failures" | tee -a "${ERROR_LOG}"
    exit 1
fi

exit 0
