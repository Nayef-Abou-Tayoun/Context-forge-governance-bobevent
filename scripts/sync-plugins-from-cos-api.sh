#!/bin/bash
set -e

# IBM Cloud Object Storage Plugin Sync Script (API-based)
# Uses IBM Cloud COS API with API key instead of S3 HMAC
# Downloads plugins to /tmp which is writable in Code Engine

echo "=== IBM Cloud Object Storage Plugin Sync (API) ==="
echo "Starting plugin sync from COS bucket..."

# Required environment variables
: "${COS_API_KEY:?COS_API_KEY is required}"
: "${COS_INSTANCE_ID:?COS_INSTANCE_ID is required}"
: "${COS_BUCKET:?COS_BUCKET is required}"
: "${COS_ENDPOINT:?COS_ENDPOINT is required}"

# Optional variables
PLUGIN_DIR="${PLUGIN_DIR:-/tmp/plugins}"
COS_PREFIX="${COS_PREFIX:-plugins/}"

echo "Configuration:"
echo "  COS Endpoint: $COS_ENDPOINT"
echo "  COS Bucket: $COS_BUCKET"
echo "  COS Prefix: $COS_PREFIX"
echo "  Plugin Directory: $PLUGIN_DIR"

# Install IBM Cloud CLI and COS plugin if not present
if ! command -v ibmcloud &> /dev/null; then
    echo "Installing IBM Cloud CLI..."
    curl -fsSL https://clis.cloud.ibm.com/install/linux | sh
fi

if ! ibmcloud plugin list | grep -q cloud-object-storage; then
    echo "Installing COS plugin..."
    ibmcloud plugin install cloud-object-storage -f
fi

# Login with API key
echo "Authenticating with IBM Cloud..."
ibmcloud login --apikey "$COS_API_KEY" -q

# Set COS configuration
ibmcloud cos config crn --crn "$COS_INSTANCE_ID" --force
ibmcloud cos config endpoint-url --url "https://$COS_ENDPOINT" --force

echo "Testing COS connection..."
if ! ibmcloud cos list-objects --bucket "$COS_BUCKET" --prefix "$COS_PREFIX" > /dev/null 2>&1; then
    echo "ERROR: Failed to connect to COS bucket"
    exit 1
fi
echo "✓ COS connection successful"

# Create plugin directory in /tmp (writable)
mkdir -p "$PLUGIN_DIR"
echo "✓ Created plugin directory: $PLUGIN_DIR"

# List and download plugins
echo "Listing plugins in COS..."
OBJECTS=$(ibmcloud cos list-objects --bucket "$COS_BUCKET" --prefix "$COS_PREFIX" --output json)

# Parse and download each plugin file
echo "$OBJECTS" | jq -r '.Contents[]?.Key' | while read -r key; do
    if [ -n "$key" ] && [ "$key" != "$COS_PREFIX" ]; then
        # Remove prefix to get relative path
        RELATIVE_PATH="${key#$COS_PREFIX}"
        LOCAL_PATH="$PLUGIN_DIR/$RELATIVE_PATH"
        
        # Create directory if needed
        LOCAL_DIR=$(dirname "$LOCAL_PATH")
        mkdir -p "$LOCAL_DIR"
        
        # Download file
        echo "  Downloading: $key -> $LOCAL_PATH"
        ibmcloud cos object-get --bucket "$COS_BUCKET" --key "$key" "$LOCAL_PATH"
    fi
done

# Count synced plugins
PLUGIN_COUNT=$(find "$PLUGIN_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
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

echo "=== Plugin sync completed successfully ==="
echo "Plugins are available at: $PLUGIN_DIR"

# Made with Bob
