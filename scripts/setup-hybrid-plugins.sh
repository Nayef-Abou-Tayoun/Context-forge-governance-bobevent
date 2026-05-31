#!/bin/bash
# Hybrid Plugin Mounting Setup Script
# Uses ConfigMap for config.yaml + Persistent Volume for plugin code
# This provides the best of both worlds: easy config updates + no size limits for plugins

set -e

# Configuration
APP_NAME="context-forge-0"
PROJECT_NAME="ce-itz-wxo-6a0f136da091f6cc912065"
PVC_NAME="plugin-storage"
PVC_SIZE="1G"

echo "=== Hybrid Plugin Mounting Setup ==="
echo "Application: $APP_NAME"
echo "Project: $PROJECT_NAME"
echo "PVC: $PVC_NAME ($PVC_SIZE)"
echo ""

# Step 1: Create ConfigMap for config.yaml
echo "Step 1: Creating ConfigMap for plugins/config.yaml..."
ibmcloud ce configmap create --name plugin-config \
  --from-file plugins/config.yaml \
  2>/dev/null || ibmcloud ce configmap update --name plugin-config \
     --from-file plugins/config.yaml

echo "✓ ConfigMap 'plugin-config' created/updated"
echo ""

# Step 2: Create Persistent Volume Claim
echo "Step 2: Creating Persistent Volume Claim for plugin code..."
ibmcloud ce pvc create --name $PVC_NAME --size $PVC_SIZE \
  2>/dev/null || echo "  ℹ PVC '$PVC_NAME' already exists"

echo "✓ PVC '$PVC_NAME' ready"
echo ""

# Step 3: Mount both ConfigMap and PVC to application
echo "Step 3: Mounting ConfigMap and PVC to application..."
ibmcloud ce application update --name $APP_NAME \
  --mount-configmap /app/plugins/config.yaml=plugin-config \
  --mount-pvc /app/plugins/external=plugin-storage \
  --env PLUGINS_CONFIG_FILE=/app/plugins/config.yaml \
  --env PLUGINS_DIRECTORY=/app/plugins/external \
  --env PLUGINS_ENABLED=true \
  --force

echo "✓ ConfigMap and PVC mounted to application"
echo ""

# Step 4: Create job to upload plugins to PVC
echo "Step 4: Creating job to upload plugins to PVC..."
ibmcloud ce job create --name upload-plugins \
  --image us.icr.io/cr-itz-7f1ux51h/context-forge-0:latest \
  --mount-pvc /plugins=plugin-storage \
  --command "/bin/bash" \
  --argument "-c" \
  --argument "cp -r /app/plugins/* /plugins/ && ls -la /plugins/" \
  2>/dev/null || ibmcloud ce job update --name upload-plugins \
     --image us.icr.io/cr-itz-7f1ux51h/context-forge-0:latest \
     --mount-pvc /plugins=plugin-storage \
     --command "/bin/bash" \
     --argument "-c" \
     --argument "cp -r /app/plugins/* /plugins/ && ls -la /plugins/"

echo "✓ Job 'upload-plugins' created/updated"
echo ""

# Step 5: Run the job to upload plugins
echo "Step 5: Running job to upload plugins..."
ibmcloud ce jobrun submit --job upload-plugins --wait --wait-timeout 300

echo "✓ Plugins uploaded to PVC"
echo ""

# Step 6: Verify deployment
echo "Step 6: Verifying deployment..."
sleep 5
ibmcloud ce application get --name $APP_NAME

echo ""
echo "=== Hybrid Setup Complete ==="
echo ""
echo "Configuration:"
echo "  - config.yaml: ConfigMap (easy CLI updates)"
echo "  - Plugin code: Persistent Volume (no size limits)"
echo ""
echo "To update config.yaml:"
echo "  ibmcloud ce configmap update --name plugin-config --from-file plugins/config.yaml"
echo "  ibmcloud ce application update --name $APP_NAME --force"
echo ""
echo "To update plugin code:"
echo "  1. Edit plugin files locally"
echo "  2. Run: ibmcloud ce jobrun submit --job upload-plugins --wait"
echo "  3. Run: ibmcloud ce application update --name $APP_NAME --force"
echo ""
echo "Or use kubectl to copy files directly:"
echo "  POD=\$(kubectl get pods -l app=$APP_NAME -o jsonpath='{.items[0].metadata.name}')"
echo "  kubectl cp plugins/my_plugin/ \$POD:/app/plugins/external/my_plugin/"
echo "  ibmcloud ce application update --name $APP_NAME --force"
echo ""

# Made with Bob
