# External Plugin Mounting for ContextForge

This document explains how to use external plugin mounting to update plugins and configuration without rebuilding the Docker image.

## Recommended: Hybrid Approach

The **hybrid approach** combines the best of both worlds:
- **ConfigMap** for `plugins/config.yaml` (easy CLI updates)
- **Persistent Volume** for plugin code (no size limits)

### Quick Start

Run the hybrid setup script:

```bash
./scripts/setup-hybrid-plugins.sh
```

This will:
1. Create ConfigMap for `plugins/config.yaml`
2. Create Persistent Volume Claim (1GB)
3. Mount both to the application
4. Upload plugins to the PVC
5. Restart the application

**See [Hybrid Plugin Mounting Guide](docs/deployment/hybrid-plugin-mounting.md) for full documentation.**

## Alternative: ConfigMap-Only Approach

For smaller plugins (under 1MB), you can use ConfigMaps only:

```bash
./scripts/setup-external-plugins.sh
```

This will:
1. Create ConfigMaps for `plugins/config.yaml`
2. Create ConfigMaps for each plugin
3. Mount them to the Code Engine application
4. Restart the application

## What is External Plugin Mounting?

External plugin mounting allows you to:
- Update plugin configuration (`config.yaml`) without rebuilding
- Add new plugins without rebuilding
- Modify existing plugin code without rebuilding
- Quickly iterate on plugin development

## How It Works

### Architecture

```
┌─────────────────────────────────────┐
│   Code Engine Application           │
│                                     │
│   ┌─────────────────────────────┐  │
│   │  /app/plugins/              │  │
│   │                             │  │
│   │  config.yaml ←─────────────┼──┼─── ConfigMap: plugin-config
│   │                             │  │
│   │  pii_filter/ ←─────────────┼──┼─── ConfigMap: pii-filter
│   │  pii_filter_na/ ←──────────┼──┼─── ConfigMap: pii-filter-na
│   │  token_cost_calculator/ ←──┼──┼─── ConfigMap: token-cost-calculator
│   │                             │  │
│   └─────────────────────────────┘  │
└─────────────────────────────────────┘
```

### ConfigMaps Created

1. **plugin-config**: Contains `plugins/config.yaml`
2. **pii-filter**: Contains PII Filter plugin files
3. **pii-filter-na**: Contains PII Filter NA plugin files
4. **token-cost-calculator**: Contains Token Cost Calculator plugin files

## Usage

### Update Plugin Configuration

To enable/disable plugins or change settings:

```bash
# 1. Edit plugins/config.yaml locally
vim plugins/config.yaml

# 2. Update the ConfigMap
ibmcloud ce configmap update --name plugin-config \
  --from-file plugins/config.yaml

# 3. Restart the application
ibmcloud ce application update --name context-forge-0 --force
```

### Update Plugin Code

To modify an existing plugin:

```bash
# 1. Edit plugin files locally
vim plugins/token_cost_calculator/token_cost_calculator.py

# 2. Update the ConfigMap
ibmcloud ce configmap update --name token-cost-calculator \
  --from-file plugins/token_cost_calculator/__init__.py \
  --from-file plugins/token_cost_calculator/token_cost_calculator.py \
  --from-file plugins/token_cost_calculator/plugin-manifest.yaml \
  --from-file plugins/token_cost_calculator/README.md

# 3. Restart the application
ibmcloud ce application update --name context-forge-0 --force
```

### Add New Plugin

To add a completely new plugin:

```bash
# 1. Create plugin files locally
mkdir -p plugins/my_new_plugin
# ... create __init__.py, plugin.py, plugin-manifest.yaml, README.md

# 2. Create ConfigMap for new plugin
ibmcloud ce configmap create --name my-new-plugin \
  --from-file plugins/my_new_plugin/__init__.py \
  --from-file plugins/my_new_plugin/plugin.py \
  --from-file plugins/my_new_plugin/plugin-manifest.yaml \
  --from-file plugins/my_new_plugin/README.md

# 3. Update config.yaml to include new plugin
vim plugins/config.yaml
ibmcloud ce configmap update --name plugin-config \
  --from-file plugins/config.yaml

# 4. Mount new plugin and restart
ibmcloud ce application update --name context-forge-0 \
  --mount-configmap /app/plugins/my_new_plugin=my-new-plugin \
  --force
```

## Advantages

✅ **Fast Updates**: No Docker image rebuild required  
✅ **Quick Iteration**: Test plugin changes in seconds  
✅ **Easy Rollback**: Revert ConfigMap to previous version  
✅ **Version Control**: ConfigMap definitions can be versioned  
✅ **Separation of Concerns**: Plugin code separate from application image

## Limitations

⚠️ **ConfigMap Size**: Maximum 1MB per ConfigMap  
⚠️ **Restart Required**: Application must restart to pick up changes  
⚠️ **File Structure**: Each ConfigMap key becomes a file  
⚠️ **Complex Plugins**: Very large or complex plugins may need image rebuild

## When to Use Image Rebuild vs. External Mounting

### Use External Mounting When:
- Developing and testing plugins
- Updating plugin configuration frequently
- Making small code changes to existing plugins
- Adding simple new plugins

### Use Image Rebuild When:
- Deploying to production
- Plugin has many dependencies
- Plugin size exceeds ConfigMap limits
- Need guaranteed consistency across deployments

## Troubleshooting

### Plugin Not Loading

Check if ConfigMap is mounted correctly:

```bash
ibmcloud ce application get --name context-forge-0
```

Look for the mounted ConfigMaps in the output.

### Changes Not Applied

Ensure you restarted the application:

```bash
ibmcloud ce application update --name context-forge-0 --force
```

### Import Errors

Verify all required files are in the ConfigMap:

```bash
ibmcloud ce configmap get --name token-cost-calculator
```

## Complete Example

Here's a complete workflow for updating the Token Cost Calculator plugin:

```bash
# 1. Make changes locally
vim plugins/token_cost_calculator/token_cost_calculator.py

# 2. Update ConfigMap
ibmcloud ce configmap update --name token-cost-calculator \
  --from-file plugins/token_cost_calculator/__init__.py \
  --from-file plugins/token_cost_calculator/token_cost_calculator.py \
  --from-file plugins/token_cost_calculator/plugin-manifest.yaml \
  --from-file plugins/token_cost_calculator/README.md

# 3. Restart application
ibmcloud ce application update --name context-forge-0 --force

# 4. Verify deployment
ibmcloud ce application get --name context-forge-0

# 5. Check logs
ibmcloud ce application logs --name context-forge-0 --tail 50
```

## Additional Resources

- [Full Documentation](docs/deployment/external-plugin-mounting.md)
- [Setup Script](scripts/setup-external-plugins.sh)
- [IBM Cloud Code Engine ConfigMaps](https://cloud.ibm.com/docs/codeengine?topic=codeengine-configmap)

## Support

For issues or questions, please refer to the main project documentation or create an issue in the repository.