#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE USER monitoring WITH PASSWORD 'monitoring';
    CREATE DATABASE monitoring OWNER monitoring;
    CREATE DATABASE "cus-logs" OWNER monitoring;
    GRANT ALL PRIVILEGES ON DATABASE monitoring TO monitoring;
    GRANT ALL PRIVILEGES ON DATABASE "cus-logs" TO monitoring;
EOSQL
