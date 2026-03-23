import logging
import threading
import time

logger = logging.getLogger('dashboard.cleanup')

_thread = None
_stop_event = threading.Event()


def _run_cleanup_cycle():
    """Execute one cleanup cycle for all configured tables."""
    import psycopg2
    from .models import CleanupSettings, CusDbSettings
    from django.utils import timezone

    cleanup = CleanupSettings.objects.first()
    if not cleanup or not cleanup.is_enabled or not cleanup.tables:
        return

    cus = CusDbSettings.get()
    if not cus or not cus.host:
        return

    try:
        conn = psycopg2.connect(
            host=cus.host, port=cus.port,
            dbname=cus.dbname, user=cus.user, password=cus.password,
            connect_timeout=5,
        )
    except Exception as e:
        logger.warning('Cleanup: CUS DB connection failed: %s', e)
        return

    allowed = {'ids_log', 'log', 'management_log'}
    results = {}

    try:
        cur = conn.cursor()
        for table in cleanup.tables:
            if table not in allowed:
                continue
            cur.execute("""
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s AND column_name = 'timestamp'
            """, [table])
            if not cur.fetchone():
                results[table] = 'skip'
                continue

            total_deleted = 0
            while True:
                cur.execute(f"""
                    WITH to_delete AS (
                        SELECT id FROM {table}
                        WHERE "timestamp" < NOW() - INTERVAL '{cleanup.retention_days} days'
                        LIMIT {cleanup.batch_size}
                        FOR UPDATE SKIP LOCKED
                    ),
                    deleted AS (
                        DELETE FROM {table}
                        WHERE id IN (SELECT id FROM to_delete)
                        RETURNING 1
                    )
                    SELECT count(*) FROM deleted
                """)
                batch = cur.fetchone()[0]
                conn.commit()
                if batch == 0:
                    break
                total_deleted += batch

            old_iso = conn.isolation_level
            conn.set_isolation_level(0)
            cur.execute(f"VACUUM ANALYZE {table}")
            conn.set_isolation_level(old_iso)

            results[table] = total_deleted

        cur.close()
        conn.close()

        summary = ', '.join(f"{t}: {r}" for t, r in results.items())
        cleanup.last_run = timezone.now()
        cleanup.last_result = summary
        cleanup.save(update_fields=['last_run', 'last_result'])
        logger.info('Cleanup completed: %s', summary)

    except Exception as e:
        logger.error('Cleanup error: %s', e)
        try:
            conn.close()
        except Exception:
            pass


def _scheduler_loop():
    """Background loop that runs cleanup on schedule."""
    from .models import CleanupSettings

    while not _stop_event.is_set():
        try:
            cleanup = CleanupSettings.objects.first()
            if cleanup and cleanup.is_enabled and cleanup.tables:
                interval = max(60, cleanup.interval_seconds)
                _run_cleanup_cycle()
                _stop_event.wait(interval)
            else:
                # Not enabled, check again in 30s
                _stop_event.wait(30)
        except Exception as e:
            logger.error('Scheduler error: %s', e)
            _stop_event.wait(60)


def start_scheduler():
    """Start the background cleanup scheduler (called from AppConfig.ready)."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_scheduler_loop, daemon=True, name='cleanup-scheduler')
    _thread.start()
    logger.info('Cleanup scheduler started')


def is_running():
    """Check if the scheduler thread is alive."""
    return _thread is not None and _thread.is_alive()
