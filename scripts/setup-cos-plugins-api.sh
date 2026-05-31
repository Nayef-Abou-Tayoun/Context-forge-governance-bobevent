#!/bin/bash
set -e

# IBM Cloud Code Engine - COS Plugin Integration Setup (API-based)
# Uses IBM Cloud COS API with API key and downloads to /tmp

echo "=== IBM Cloud Code Engine - COS Plugin Setup (API) ==="

# Configuration
APP_NAME="${APP_NAME:-context-forge-0}"
SECRET_NAME="cos-api-credentials"
CONFIGMAP_NAME="plugin-config"

# COS Configuration (from provided credentials)
COS_API_KEY="wlm0CZNVSCYcHfWrNTOV3RTPDClLoZNJhCyFLHO7hYFj"
COS_INSTANCE_ID="crn:v1:bluemix:public:cloud-object-storage:global:a/a11ac9a4e11b4f2ea5316197cbef1878:dcd0fbf6-d48d-4217-b3f3-58e34695220f::"
COS_BUCKET="contextforge-plugins"
COS_ENDPOINT="s3.us-south.cloud-object-storage.appdomain.cloud"

echo "Configuration:"
echo "  Application: $APP_NAME"
echo "  COS Bucket: $COS_BUCKET"
echo "  COS Endpoint: $COS_ENDPOINT"
echo ""

# Step 1: Create secret for COS API credentials
echo "Step 1: Creating COS API credentials secret..."
if ibmcloud ce secret get --name $SECRET_NAME &>/dev/null; then
    echo "Secret $SECRET_NAME already exists, updating..."
    ibmcloud ce secret update --name $SECRET_NAME \
        --from-literal COS_API_KEY="$COS_API_KEY" \
        --from-literal COS_INSTANCE_ID="$COS_INSTANCE_ID" \
        --from-literal COS_ENDPOINT="$COS_ENDPOINT" \
        --from-literal COS_BUCKET="$COS_BUCKET" \
        --from-literal COS_PREFIX="plugins/" \
        --from-literal PLUGIN_DIR="/tmp/plugins"
else
    ibmcloud ce secret create --name $SECRET_NAME \
        --from-literal COS_API_KEY="$COS_API_KEY" \
        --from-literal COS_INSTANCE_ID="$COS_INSTANCE_ID" \
        --from-literal COS_ENDPOINT="$COS_ENDPOINT" \
        --from-literal COS_BUCKET="$COS_BUCKET" \
        --from-literal COS_PREFIX="plugins/" \
        --from-literal PLUGIN_DIR="/tmp/plugins"
fi
echo "✓ Secret created/updated"

# Step 2: Create ConfigMap for plugin config.yaml
echo ""
echo "Step 2: Creating ConfigMap for plugin configuration..."
if [ ! -f "plugins/config.yaml" ]; then
    echo "ERROR: plugins/config.yaml not found"
    exit 1
fi

if ibmcloud ce configmap get --name $CONFIGMAP_NAME &>/dev/null; then
    echo "ConfigMap $CONFIGMAP_NAME already exists, updating..."
    ibmcloud ce configmap update --name $CONFIGMAP_NAME \
        --from-file plugins/config.yaml
else
    ibmcloud ce configmap create --name $CONFIGMAP_NAME \
        --from-file plugins/config.yaml
fi
echo "✓ ConfigMap created/updated"

# Step 3: Update application with API-based sync
echo ""
echo "Step 3: Updating application with COS API sync..."

# Update application with API-based sync command
ibmcloud ce application update --name $APP_NAME \
    --env-from-secret $SECRET_NAME \
    --env PLUGINS_ENABLED=true \
    --env PLUGINS_CONFIG_FILE=/tmp/config.yaml \
    --mount-configmap /tmp/config=$CONFIGMAP_NAME \
    --command /bin/bash \
    --argument "-c" \
    --argument "bash /app/scripts/sync-plugins-from-cos-api.sh && exec python -m mcpgateway.main"

echo "✓ Application updated with COS API sync"

# Step 4: Wait for application to be ready
echo ""
echo "Step 4: Waiting for application to be ready..."
echo "This may take a few minutes..."

MAX_WAIT=300
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    STATUS=$(ibmcloud ce app get --name $APP_NAME --output json | jq -r '.status.conditions[] | select(.type=="Ready") | .status')
    if [ "$STATUS" = "True" ]; then
        echo "✓ Application is ready!"
        break
    fi
    echo "  Waiting... ($ELAPSED seconds elapsed)"
    sleep 10
    ELAPSED=$((ELAPSED + 10))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo "WARNING: Application did not become ready within $MAX_WAIT seconds"
    echo "Check application logs with: ibmcloud ce app logs --name $APP_NAME"
fi

# Step 5: Display application URL
echo ""
echo "Step 5: Getting application URL..."
APP_URL=$(ibmcloud ce app get --name $APP_NAME --output json | jq -r '.status.url')
echo "✓ Application URL: $APP_URL"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Your application is now configured to sync plugins from COS using API key!"
echo ""
echo "Plugins are downloaded to /tmp/plugins (writable directory)"
echo ""
echo "To update plugins:"
echo "1. Upload plugin files to COS bucket: s3://$COS_BUCKET/plugins/"
echo "2. Restart the application: ibmcloud ce app update --name $APP_NAME --force"
echo ""
echo "To update config.yaml:"
echo "1. Update local plugins/config.yaml"
echo "2. Run: ibmcloud ce configmap update --name $CONFIGMAP_NAME --from-file plugins/config.yaml"
echo "3. Restart: ibmcloud ce app update --name $APP_NAME --force"
echo ""
echo "View logs: ibmcloud ce app logs --name $APP_NAME --follow"

# Made with Bob
