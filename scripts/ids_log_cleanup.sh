#!/bin/bash
#
# ids_log_cleanup.sh
# Мониторинг свободного места на /var и очистка старых записей ids_log
#
# Устанавливается в crontab на хосте с БД логов ЦУС:
#   */10 * * * * /opt/scripts/ids_log_cleanup.sh >> /var/log/ids_log_cleanup.log 2>&1
#
# Переменные окружения (или задать ниже):
#   DB_HOST, DB_PORT, DB_NAME, DB_USER, PGPASSWORD
#   THRESHOLD_PERCENT - порог свободного места (по умолчанию 20)
#   RETENTION_DAYS    - удалять записи старше N дней (по умолчанию 7)
#   PARTITION         - раздел для мониторинга (по умолчанию /var)

set -euo pipefail

# ── Настройки ────────────────────────────────────────────────────────
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-cus-logs}"
DB_USER="${DB_USER:-monitoring}"
PGPASSWORD="${PGPASSWORD:-monitoring}"
export PGPASSWORD

THRESHOLD_PERCENT="${THRESHOLD_PERCENT:-20}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
PARTITION="${PARTITION:-/var}"

LOG_PREFIX="[ids_log_cleanup]"

# ── Функции ──────────────────────────────────────────────────────────
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') ${LOG_PREFIX} $*"
}

get_free_percent() {
    df "${PARTITION}" | awk 'NR==2 {gsub(/%/,"",$5); print 100-$5}'
}

run_psql() {
    psql \
        -h "${DB_HOST}" \
        -p "${DB_PORT}" \
        -U "${DB_USER}" \
        -d "${DB_NAME}" \
        -t -A -c "$1" 2>&1
}

# ── Проверки ─────────────────────────────────────────────────────────
if ! command -v psql &>/dev/null; then
    log "ERROR: psql not found. Install postgresql-client."
    exit 1
fi

if ! df "${PARTITION}" &>/dev/null; then
    log "ERROR: Partition ${PARTITION} not found."
    exit 1
fi

# ── Основная логика ──────────────────────────────────────────────────
FREE_PERCENT=$(get_free_percent)
log "Free space on ${PARTITION}: ${FREE_PERCENT}% (threshold: ${THRESHOLD_PERCENT}%)"

if [ "${FREE_PERCENT}" -ge "${THRESHOLD_PERCENT}" ]; then
    log "OK: Free space is sufficient, no cleanup needed."
    exit 0
fi

log "WARNING: Free space ${FREE_PERCENT}% < ${THRESHOLD_PERCENT}%. Starting cleanup..."

# Статистика до очистки
COUNT_BEFORE=$(run_psql "SELECT count(*) FROM ids_log;")
COUNT_OLD=$(run_psql "SELECT count(*) FROM ids_log WHERE \"timestamp\" < NOW() - INTERVAL '${RETENTION_DAYS} days';")
log "Records total: ${COUNT_BEFORE}, older than ${RETENTION_DAYS} days: ${COUNT_OLD}"

if [ "${COUNT_OLD}" -eq 0 ] 2>/dev/null; then
    log "No old records to delete. Consider reducing RETENTION_DAYS or increasing disk space."
    exit 1
fi

# Удаление батчами по 10000 с паузой между батчами
# для снижения нагрузки и минимизации блокировок
log "Deleting records older than ${RETENTION_DAYS} days..."
TOTAL_DELETED=0
while true; do
    BATCH_DELETED=$(run_psql "
        WITH to_delete AS (
            SELECT id FROM ids_log
            WHERE \"timestamp\" < NOW() - INTERVAL '${RETENTION_DAYS} days'
            LIMIT 10000
            FOR UPDATE SKIP LOCKED
        ),
        deleted AS (
            DELETE FROM ids_log
            WHERE id IN (SELECT id FROM to_delete)
            RETURNING 1
        )
        SELECT count(*) FROM deleted;
    ")

    if [ "${BATCH_DELETED}" -eq 0 ] 2>/dev/null; then
        break
    fi

    TOTAL_DELETED=$((TOTAL_DELETED + BATCH_DELETED))
    log "  batch: ${BATCH_DELETED}, total: ${TOTAL_DELETED}"
    sleep 1
done

COUNT_AFTER=$(run_psql "SELECT count(*) FROM ids_log;")
log "Deleted: ${TOTAL_DELETED} records (${COUNT_BEFORE} -> ${COUNT_AFTER})"

# VACUUM (без FULL) — не блокирует таблицу, позволяет переиспользовать место
# Для полного возврата места на диск используйте pg_repack (без блокировки)
# или VACUUM FULL в окно обслуживания (блокирует таблицу)
log "Running VACUUM ANALYZE ids_log..."
run_psql "VACUUM ANALYZE ids_log;"
log "VACUUM ANALYZE completed."

# Результат
FREE_AFTER=$(get_free_percent)
log "Free space after cleanup: ${FREE_AFTER}% (was: ${FREE_PERCENT}%)"

if [ "${FREE_AFTER}" -ge "${THRESHOLD_PERCENT}" ]; then
    log "OK: Cleanup successful."
else
    log "WARNING: Free space still below threshold (${FREE_AFTER}% < ${THRESHOLD_PERCENT}%). Manual intervention required."
    exit 1
fi
