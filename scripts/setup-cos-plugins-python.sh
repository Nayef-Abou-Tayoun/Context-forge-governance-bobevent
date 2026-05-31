#!/bin/bash
set -e

# IBM Cloud Object Storage Plugin Setup Script (Python-based)
# Uses Python boto3 library instead of IBM Cloud CLI
# This approach works in minimal containers without tar/curl

echo "=== IBM Cloud Object Storage Plugin Setup (Python) ==="
echo "This script will configure your Code Engine application to sync plugins from COS"

# Embedded COS credentials
COS_API_KEY="wlm0CZNVSCYcHfWrNTOV3RTPDClLoZNJhCyFLHO7hYFj"
COS_INSTANCE_ID="crn:v1:bluemix:public:cloud-object-storage:global:a/a11ac9a4e11b4f2ea5316197cbef1878:dcd0fbf6-d48d-4217-b3f3-58e34695220f::"
COS_BUCKET="contextforge-plugins"
COS_ENDPOINT="s3.us-south.cloud-object-storage.appdomain.cloud"
COS_PREFIX="plugins/"

APP_NAME="context-forge-0"
SECRET_NAME="cos-credentials"
CONFIGMAP_NAME="plugin-config"

echo "Configuration:"
echo "  Application: $APP_NAME"
echo "  COS Bucket: $COS_BUCKET"
echo "  COS Endpoint: $COS_ENDPOINT"
echo ""

# Step 1: Create or update secret with COS credentials
echo "Step 1: Creating/updating COS credentials secret..."
if ibmcloud ce secret get --name "$SECRET_NAME" &>/dev/null; then
    echo "  Secret exists, updating..."
    ibmcloud ce secret update --name "$SECRET_NAME" \
        --from-literal COS_API_KEY="$COS_API_KEY" \
        --from-literal COS_INSTANCE_ID="$COS_INSTANCE_ID" \
        --from-literal COS_BUCKET="$COS_BUCKET" \
        --from-literal COS_ENDPOINT="$COS_ENDPOINT" \
        --from-literal COS_PREFIX="$COS_PREFIX"
else
    echo "  Creating new secret..."
    ibmcloud ce secret create --name "$SECRET_NAME" \
        --from-literal COS_API_KEY="$COS_API_KEY" \
        --from-literal COS_INSTANCE_ID="$COS_INSTANCE_ID" \
        --from-literal COS_BUCKET="$COS_BUCKET" \
        --from-literal COS_ENDPOINT="$COS_ENDPOINT" \
        --from-literal COS_PREFIX="$COS_PREFIX"
fi
echo "✓ Secret configured"

# Step 2: Create or update ConfigMap with plugin config
echo ""
echo "Step 2: Creating/updating plugin configuration ConfigMap..."
if ibmcloud ce configmap get --name "$CONFIGMAP_NAME" &>/dev/null; then
    echo "  ConfigMap exists, updating..."
    ibmcloud ce configmap update --name "$CONFIGMAP_NAME" \
        --from-file plugins/config.yaml
else
    echo "  Creating new ConfigMap..."
    ibmcloud ce configmap create --name "$CONFIGMAP_NAME" \
        --from-file plugins/config.yaml
fi
echo "✓ ConfigMap configured"

# Step 3: Update application with COS sync
echo ""
echo "Step 3: Updating application to sync plugins from COS..."
ibmcloud ce app update --name "$APP_NAME" \
    --env-from-secret "$SECRET_NAME" \
    --env PLUGIN_DIR=/tmp/plugins \
    --env PLUGINS_ENABLED=true \
    --env PLUGINS_CONFIG_FILE=/tmp/config/config.yaml \
    --mount-configmap /tmp/config="$CONFIGMAP_NAME" \
    --cmd "python3" \
    --args "/app/scripts/sync-plugins-from-cos-python.py && exec ./docker-entrypoint.sh"

echo "✓ Application updated"

# Step 4: Wait for deployment
echo ""
echo "Step 4: Waiting for application to be ready..."
echo "This may take a few minutes..."

MAX_WAIT=300
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    STATUS=$(ibmcloud ce app get --name "$APP_NAME" --output json 2>/dev/null | jq -r '.status' || echo "unknown")
    
    if [ "$STATUS" = "ready" ]; then
        echo "✓ Application is ready!"
        break
    fi
    
    echo "  Status: $STATUS (waiting...)"
    sleep 10
    ELAPSED=$((ELAPSED + 10))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo "⚠️  Timeout waiting for application to be ready"
    echo "Check application logs with: ibmcloud ce app logs --name $APP_NAME"
    exit 1
fi

# Step 5: Get application URL
echo ""
echo "Step 5: Getting application URL..."
APP_URL=$(ibmcloud ce app get --name "$APP_NAME" --output json | jq -r '.status.url')
echo "✓ Application URL: $APP_URL"

# Step 6: Verify plugin sync
echo ""
echo "Step 6: Verifying plugin sync..."
echo "Checking application logs for plugin sync messages..."
sleep 5
ibmcloud ce app logs --name "$APP_NAME" --tail 30 | grep -E "(COS|plugin|sync)" || true

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Your application is now configured to sync plugins from IBM Cloud Object Storage!"
echo ""
echo "Key Information:"
echo "  - Application URL: $APP_URL"
echo "  - COS Bucket: $COS_BUCKET"
echo "  - Plugin Directory: /tmp/plugins"
echo "  - Config File: /tmp/config/config.yaml"
echo ""
echo "To update plugins:"
echo "  1. Upload plugin files to COS bucket: $COS_BUCKET"
echo "  2. Restart the application: ibmcloud ce app update --name $APP_NAME --force"
echo ""
echo "To view logs:"
echo "  ibmcloud ce app logs --name $APP_NAME --follow"
echo ""

# Made with Bob