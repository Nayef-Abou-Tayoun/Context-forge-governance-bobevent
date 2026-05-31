#!/usr/bin/env bash
#───────────────────────────────────────────────────────────────────────────────
#  Script : docker-entrypoint.sh
#  Purpose: Container entrypoint that allows switching between HTTP servers
#
#  Environment Variables:
#    HTTP_SERVER : Which HTTP server to use (default: gunicorn)
#                  - gunicorn : Python-based with Uvicorn workers (default)
#                  - granian  : Rust-based HTTP server (alternative)
#    SYNC_PLUGINS_FROM_COS : Enable plugin syncing from IBM Cloud Object Storage
#                            (default: false)
#
#  Usage:
#    # Run with Gunicorn (default)
#    docker run -e HTTP_SERVER=gunicorn mcpgateway
#
#    # Run with Granian
#    docker run -e HTTP_SERVER=granian mcpgateway
#
#    # Run with COS plugin syncing
#    docker run -e SYNC_PLUGINS_FROM_COS=true mcpgateway
#───────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# Sync plugins from COS if enabled
SYNC_PLUGINS_FROM_COS="${SYNC_PLUGINS_FROM_COS:-false}"

if [[ "${SYNC_PLUGINS_FROM_COS}" == "true" ]]; then
    echo "🔄 Syncing plugins from IBM Cloud Object Storage..."
    
    # Check if sync script exists
    if [[ -f "./scripts/sync-plugins-from-cos-python.py" ]]; then
        # Run the Python sync script
        python3 ./scripts/sync-plugins-from-cos-python.py
        
        if [[ $? -eq 0 ]]; then
            echo "✅ Plugin sync completed successfully"
        else
            echo "⚠️  WARNING: Plugin sync failed, continuing with built-in plugins"
        fi
    else
        echo "⚠️  WARNING: COS sync script not found, continuing with built-in plugins"
    fi
else
    echo "ℹ️  COS plugin syncing disabled (set SYNC_PLUGINS_FROM_COS=true to enable)"
fi

HTTP_SERVER="${HTTP_SERVER:-gunicorn}"

case "${HTTP_SERVER}" in
    granian)
        echo "Starting ContextForge with Granian (Rust-based HTTP server)..."
        exec ./run-granian.sh "$@"
        ;;
    gunicorn)
        echo "Starting ContextForge with Gunicorn + Uvicorn..."
        exec ./run-gunicorn.sh "$@"
        ;;
    *)
        echo "ERROR: Unknown HTTP_SERVER value: ${HTTP_SERVER}"
        echo "Valid options: granian, gunicorn"
        exit 1
        ;;
esac
