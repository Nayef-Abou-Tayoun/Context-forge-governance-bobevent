#!/bin/bash
# Setup script for external plugin mounting in IBM Cloud Code Engine
# This script creates ConfigMaps for plugins and mounts them to the application

set -e

# Configuration
APP_NAME="context-forge-0"
PROJECT_NAME="ce-itz-wxo-6a0f136da091f6cc912065"

echo "=== External Plugin Mounting Setup ==="
echo "Application: $APP_NAME"
echo "Project: $PROJECT_NAME"
echo ""

# Step 1: Create ConfigMap for config.yaml
echo "Step 1: Creating ConfigMap for plugins/config.yaml..."
ibmcloud ce configmap create --name plugin-config \
  --from-file plugins/config.yaml \
  || ibmcloud ce configmap update --name plugin-config \
     --from-file plugins/config.yaml

echo "✓ ConfigMap 'plugin-config' created/updated"
echo ""

# Step 2: Create ConfigMaps for plugins
echo "Step 2: Creating ConfigMaps for plugins..."

# PII Filter Plugin
echo "  - Creating ConfigMap for pii_filter plugin..."
ibmcloud ce configmap create --name pii-filter \
  --from-file plugins/pii_filter/__init__.py \
  --from-file plugins/pii_filter/plugin.py \
  --from-file plugins/pii_filter/plugin-manifest.yaml \
  --from-file plugins/pii_filter/README.md \
  || ibmcloud ce configmap update --name pii-filter \
     --from-file plugins/pii_filter/__init__.py \
     --from-file plugins/pii_filter/plugin.py \
     --from-file plugins/pii_filter/plugin-manifest.yaml \
     --from-file plugins/pii_filter/README.md

echo "  ✓ ConfigMap 'pii-filter' created/updated"

# PII Filter NA Plugin
echo "  - Creating ConfigMap for pii_filter_na plugin..."
ibmcloud ce configmap create --name pii-filter-na \
  --from-file plugins/pii_filter_na/__init__.py \
  --from-file plugins/pii_filter_na/pii_filter_na.py \
  --from-file plugins/pii_filter_na/plugin-manifest.yaml \
  --from-file plugins/pii_filter_na/README.md \
  || ibmcloud ce configmap update --name pii-filter-na \
     --from-file plugins/pii_filter_na/__init__.py \
     --from-file plugins/pii_filter_na/pii_filter_na.py \
     --from-file plugins/pii_filter_na/plugin-manifest.yaml \
     --from-file plugins/pii_filter_na/README.md

echo "  ✓ ConfigMap 'pii-filter-na' created/updated"

# Token Cost Calculator Plugin
echo "  - Creating ConfigMap for token_cost_calculator plugin..."
ibmcloud ce configmap create --name token-cost-calculator \
  --from-file plugins/token_cost_calculator/__init__.py \
  --from-file plugins/token_cost_calculator/token_cost_calculator.py \
  --from-file plugins/token_cost_calculator/plugin-manifest.yaml \
  --from-file plugins/token_cost_calculator/README.md \
  || ibmcloud ce configmap update --name token-cost-calculator \
     --from-file plugins/token_cost_calculator/__init__.py \
     --from-file plugins/token_cost_calculator/token_cost_calculator.py \
     --from-file plugins/token_cost_calculator/plugin-manifest.yaml \
     --from-file plugins/token_cost_calculator/README.md

echo "  ✓ ConfigMap 'token-cost-calculator' created/updated"
echo ""

# Step 3: Mount ConfigMaps to application
echo "Step 3: Mounting ConfigMaps to application..."
ibmcloud ce application update --name $APP_NAME \
  --mount-configmap /app/plugins/config.yaml=plugin-config \
  --mount-configmap /app/plugins/pii_filter=pii-filter \
  --mount-configmap /app/plugins/pii_filter_na=pii-filter-na \
  --mount-configmap /app/plugins/token_cost_calculator=token-cost-calculator \
  --env PLUGINS_ENABLED=true \
  --env PLUGINS_CONFIG_FILE=/app/plugins/config.yaml \
  --force

echo "✓ ConfigMaps mounted to application"
echo ""

# Step 4: Verify deployment
echo "Step 4: Verifying deployment..."
sleep 5
ibmcloud ce application get --name $APP_NAME

echo ""
echo "=== Setup Complete ==="
echo "Plugins are now mounted externally via ConfigMaps"
echo ""
echo "To update plugins in the future:"
echo "  1. Update config.yaml: ibmcloud ce configmap update --name plugin-config --from-file plugins/config.yaml"
echo "  2. Update plugin code: ibmcloud ce configmap update --name <plugin-name> --from-file plugins/<plugin-dir>/"
echo "  3. Restart app: ibmcloud ce application update --name $APP_NAME --force"
echo ""

# Made with Bob
