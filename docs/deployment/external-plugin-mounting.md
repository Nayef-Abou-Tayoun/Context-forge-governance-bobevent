# External Plugin Mounting Guide

This guide explains how to mount plugins and configuration externally in IBM Cloud Code Engine without rebuilding the Docker image.

## Overview

This approach uses ConfigMaps to mount:
1. `plugins/config.yaml` - Plugin configuration
2. Plugin directories - Individual plugin code

## Prerequisites

- IBM Cloud CLI with Code Engine plugin
- Logged into IBM Cloud
- Existing Code Engine application

## Setup Instructions

### Step 1: Create ConfigMap for config.yaml

```bash
# Create ConfigMap from your config file
ibmcloud ce configmap create --name plugin-config \
  --from-file plugins/config.yaml
```

### Step 2: Create ConfigMap for Each Plugin

For each plugin you want to mount externally:

```bash
# Example: Token Cost Calculator Plugin
ibmcloud ce configmap create --name token-cost-calculator \
  --from-file plugins/token_cost_calculator/__init__.py \
  --from-file plugins/token_cost_calculator/plugin.py \
  --from-file plugins/token_cost_calculator/plugin-manifest.yaml \
  --from-file plugins/token_cost_calculator/README.md
```

### Step 3: Mount ConfigMaps to Application

```bash
# Mount config.yaml and plugin directories
ibmcloud ce application update --name context-forge-0 \
  --mount-configmap /app/plugins/config.yaml=plugin-config \
  --mount-configmap /app/plugins/token_cost_calculator=token-cost-calculator
```

### Step 4: Configure Environment Variables

```bash
# Ensure plugins are enabled
ibmcloud ce application update --name context-forge-0 \
  --env PLUGINS_ENABLED=true \
  --env PLUGINS_CONFIG_FILE=/app/plugins/config.yaml
```

## Updating Plugins

### Update Configuration Only

```bash
# Update the config.yaml ConfigMap
ibmcloud ce configmap update --name plugin-config \
  --from-file plugins/config.yaml

# Restart application to pick up changes
ibmcloud ce application update --name context-forge-0 --force
```

### Update Plugin Code

```bash
# Update the plugin ConfigMap
ibmcloud ce configmap update --name token-cost-calculator \
  --from-file plugins/token_cost_calculator/__init__.py \
  --from-file plugins/token_cost_calculator/plugin.py \
  --from-file plugins/token_cost_calculator/plugin-manifest.yaml

# Restart application
ibmcloud ce application update --name context-forge-0 --force
```

### Add New Plugin

```bash
# 1. Create ConfigMap for new plugin
ibmcloud ce configmap create --name my-new-plugin \
  --from-file plugins/my_new_plugin/__init__.py \
  --from-file plugins/my_new_plugin/plugin.py \
  --from-file plugins/my_new_plugin/plugin-manifest.yaml

# 2. Update config.yaml to include new plugin
ibmcloud ce configmap update --name plugin-config \
  --from-file plugins/config.yaml

# 3. Mount new plugin
ibmcloud ce application update --name context-forge-0 \
  --mount-configmap /app/plugins/my_new_plugin=my-new-plugin \
  --force
```

## Complete Example

Here's a complete example mounting multiple plugins:

```bash
# Create ConfigMaps
ibmcloud ce configmap create --name plugin-config --from-file plugins/config.yaml
ibmcloud ce configmap create --name pii-filter --from-file plugins/pii_filter/
ibmcloud ce configmap create --name token-calculator --from-file plugins/token_cost_calculator/

# Mount all ConfigMaps
ibmcloud ce application update --name context-forge-0 \
  --mount-configmap /app/plugins/config.yaml=plugin-config \
  --mount-configmap /app/plugins/pii_filter=pii-filter \
  --mount-configmap /app/plugins/token_cost_calculator=token-calculator \
  --env PLUGINS_ENABLED=true \
  --force
```

## Limitations

1. **ConfigMap Size**: Maximum 1MB per ConfigMap
2. **File Structure**: Each key in ConfigMap becomes a file
3. **Restart Required**: Application must be restarted after ConfigMap updates
4. **Python Imports**: Plugin framework must support dynamic loading from mounted paths

## Troubleshooting

### Plugin Not Loading

Check if the plugin directory is correctly mounted:

```bash
# Get application details
ibmcloud ce application get --name context-forge-0

# Check logs
ibmcloud ce application logs --name context-forge-0 --tail 100
```

### ConfigMap Update Not Applied

Ensure you restart the application after updating ConfigMaps:

```bash
ibmcloud ce application update --name context-forge-0 --force
```

### Import Errors

Verify the plugin structure matches the expected format and all required files are included in the ConfigMap.

## Best Practices

1. **Version Control**: Keep ConfigMap definitions in version control
2. **Testing**: Test ConfigMap updates in a development environment first
3. **Backup**: Keep backups of working ConfigMaps
4. **Documentation**: Document which plugins are mounted externally vs. baked into the image
5. **Monitoring**: Monitor application logs after ConfigMap updates

## Alternative: Persistent Volumes

For larger plugins or more complex setups, consider using persistent volumes instead of ConfigMaps:

```bash
# Create persistent volume claim
ibmcloud ce pvc create --name plugin-storage --size 1G

# Mount to application
ibmcloud ce application update --name context-forge-0 \
  --mount-pvc /app/plugins/external=plugin-storage
```

Then use a job or init container to populate the volume with plugin files.