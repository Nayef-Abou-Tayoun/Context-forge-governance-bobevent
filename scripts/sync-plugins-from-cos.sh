#!/bin/bash
set -e

# IBM Cloud Object Storage Plugin Sync Script
# This script syncs plugins from COS bucket to local directory
# Designed to run as an init container in Code Engine

echo "=== IBM Cloud Object Storage Plugin Sync ==="
echo "Starting plugin sync from COS bucket..."

# Required environment variables
: "${COS_ENDPOINT:?COS_ENDPOINT is required}"
: "${COS_BUCKET:?COS_BUCKET is required}"
: "${HMAC_ACCESS_KEY_ID:?HMAC_ACCESS_KEY_ID is required}"
: "${HMAC_SECRET_ACCESS_KEY:?HMAC_SECRET_ACCESS_KEY is required}"

# Optional variables
PLUGIN_DIR="${PLUGIN_DIR:-/app/plugins/external}"
COS_PREFIX="${COS_PREFIX:-plugins/}"

echo "Configuration:"
echo "  COS Endpoint: $COS_ENDPOINT"
echo "  COS Bucket: $COS_BUCKET"
echo "  COS Prefix: $COS_PREFIX"
echo "  Plugin Directory: $PLUGIN_DIR"

# Install s3cmd if not present
if ! command -v s3cmd &> /dev/null; then
    echo "Installing s3cmd..."
    pip install --quiet s3cmd
fi

# Create s3cmd config
cat > /tmp/.s3cfg <<EOF
[default]
access_key = $HMAC_ACCESS_KEY_ID
secret_key = $HMAC_SECRET_ACCESS_KEY
host_base = $COS_ENDPOINT
host_bucket = %(bucket)s.$COS_ENDPOINT
use_https = True
signature_v2 = False
EOF

echo "Testing COS connection..."
if ! s3cmd -c /tmp/.s3cfg ls s3://$COS_BUCKET/ > /dev/null 2>&1; then
    echo "ERROR: Failed to connect to COS bucket"
    exit 1
fi
echo "✓ COS connection successful"

# Create plugin directory if it doesn't exist
mkdir -p "$PLUGIN_DIR"

# Sync plugins from COS
echo "Syncing plugins from s3://$COS_BUCKET/$COS_PREFIX to $PLUGIN_DIR..."
s3cmd -c /tmp/.s3cfg sync \
    --delete-removed \
    --skip-existing \
    s3://$COS_BUCKET/$COS_PREFIX \
    "$PLUGIN_DIR/"

# Count synced plugins
PLUGIN_COUNT=$(find "$PLUGIN_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l)
echo "✓ Synced $PLUGIN_COUNT plugin(s) from COS"

# List synced plugins
if [ $PLUGIN_COUNT -gt 0 ]; then
    echo "Synced plugins:"
    find "$PLUGIN_DIR" -mindepth 1 -maxdepth 1 -type d -exec basename {} \;
fi

# Verify plugin structure
echo "Verifying plugin structure..."
for plugin_dir in "$PLUGIN_DIR"/*; do
    if [ -d "$plugin_dir" ]; then
        plugin_name=$(basename "$plugin_dir")
        if [ ! -f "$plugin_dir/plugin.py" ]; then
            echo "WARNING: Plugin $plugin_name missing plugin.py"
        fi
        if [ ! -f "$plugin_dir/plugin-manifest.yaml" ]; then
            echo "WARNING: Plugin $plugin_name missing plugin-manifest.yaml"
        fi
    fi
done

# Clean up
rm -f /tmp/.s3cfg

echo "=== Plugin sync completed successfully ==="

# Made with Bob
