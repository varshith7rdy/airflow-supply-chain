#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export AIRFLOW_HOME="$SCRIPT_DIR"
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

source "$SCRIPT_DIR/.venv/bin/activate"

# Sync/reserialize DAGs if running airflow commands
if [ "$1" = "standalone" ] || [ "$1" = "scheduler" ] || [ "$1" = "webserver" ]; then
    echo "Syncing Airflow DAGs..."
    airflow dags reserialize > /dev/null 2>&1 || true
fi

exec airflow "$@"
