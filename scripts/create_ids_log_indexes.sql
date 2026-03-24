-- Indexes for CUS log tables
-- Run manually: psql -U monitoring -d cus-logs -f create_ids_log_indexes.sql
-- Or they will be created automatically on first dashboard connection.

CREATE INDEX IF NOT EXISTS ids_log_timestamp_idx
    ON ids_log ("timestamp");

CREATE INDEX IF NOT EXISTS ids_log_event_type_timestamp_idx
    ON ids_log (event_type, "timestamp");

CREATE INDEX IF NOT EXISTS ids_log_rule_name_idx
    ON ids_log (rule_name);

CREATE INDEX IF NOT EXISTS ids_log_timestamp_id_idx
    ON ids_log ("timestamp", id);

CREATE INDEX IF NOT EXISTS management_log_timestamp_idx
    ON management_log ("timestamp");
