# Hybrid Plugin Mounting Guide

This guide explains the **recommended hybrid approach** for mounting plugins in IBM Cloud Code Engine:
- **ConfigMap** for `plugins/config.yaml` (easy CLI updates)
- **Persistent Volume** for plugin code (no size limits)

## Why Hybrid Approach?

| Aspect | ConfigMap | Persistent Volume | Hybrid |
|--------|-----------|-------------------|--------|
| Config Updates | ✅ Easy CLI | ❌ File copy | ✅ Easy CLI |
| Plugin Code | ❌ 1MB limit | ✅ No limit | ✅ No limit |
| Complexity | Low | Medium | Medium |
| Best Use | Config files | Plugin code | **Both** |

## Architecture

```
┌─────────────────────────────────────────────┐
│   Code Engine Application                   │
│                                             │
│   ┌─────────────────────────────────────┐  │
│   │  /app/plugins/                      │  │
│   │                                     │  │
│   │  config.yaml ←──────────────────┐  │  │
│   │                                  │  │  │
│   │  external/                       │  │  │
│   │    ├── pii_filter/              │  │  │
│   │    ├── pii_filter_na/           │  │  │
│   │    └── token_cost_calculator/   │  │  │
│   │                                  │  │  │
│   └──────────────────────────────────┼──┘  │
│                                      │     │
└──────────────────────────────────────┼─────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    │                                     │
            ┌───────▼────────┐              ┌────────────▼─────────┐
            │   ConfigMap    │              │  Persistent Volume   │
            │ plugin-config  │              │   plugin-storage     │
            │                │              │                      │
            │ config.yaml    │              │ Plugin .py files     │
            └────────────────┘              └──────────────────────┘
```

## Quick Start

Run the hybrid setup script:

```bash
./scripts/setup-hybrid-plugins.sh
```

This will:
1. Create ConfigMap for `config.yaml`
2. Create Persistent Volume Claim (1GB)
3. Mount both to the application
4. Upload plugins to the PVC
5. Restart the application

## Manual Setup

### Step 1: Create ConfigMap for config.yaml

```bash
ibmcloud ce configmap create --name plugin-config \
  --from-file plugins/config.yaml
```

### Step 2: Create Persistent Volume Claim

```bash
# Create a 1GB persistent volume for plugins
ibmcloud ce pvc create --name plugin-storage --size 1G
```

### Step 3: Mount Both to Application

```bash
ibmcloud ce application update --name context-forge-0 \
  --mount-configmap /app/plugins/config.yaml=plugin-config \
  --mount-pvc /app/plugins/external=plugin-storage \
  --env PLUGINS_CONFIG_FILE=/app/plugins/config.yaml \
  --env PLUGINS_DIRECTORY=/app/plugins/external \
  --env PLUGINS_ENABLED=true \
  --force
```

### Step 4: Upload Plugins to PVC

**Option A: Using a Job (Recommended)**

```bash
# Create job to upload plugins
ibmcloud ce job create --name upload-plugins \
  --image us.icr.io/cr-itz-7f1ux51h/context-forge-0:latest \
  --mount-pvc /plugins=plugin-storage \
  --command "/bin/bash" \
  --argument "-c" \
  --argument "cp -r /app/plugins/* /plugins/"

# Run the job
ibmcloud ce jobrun submit --job upload-plugins --wait
```

**Option B: Using kubectl**

```bash
# Get pod name
POD=$(kubectl get pods -l app=context-forge-0 -o jsonpath='{.items[0].metadata.name}')

# Copy plugins to PVC
kubectl cp plugins/ $POD:/app/plugins/external/
```

## Usage

### Update Configuration Only

```bash
# 1. Edit config.yaml locally
vim plugins/config.yaml

# 2. Update ConfigMap
ibmcloud ce configmap update --name plugin-config \
  --from-file plugins/config.yaml

# 3. Restart application
ibmcloud ce application update --name context-forge-0 --force
```

### Update Plugin Code

**Method 1: Using Job (Recommended for bulk updates)**

```bash
# 1. Edit plugin files locally
vim plugins/token_cost_calculator/token_cost_calculator.py

# 2. Rebuild image with new plugins (or commit to Git)
# ... (if using Git-based job)

# 3. Run upload job
ibmcloud ce jobrun submit --job upload-plugins --wait

# 4. Restart application
ibmcloud ce application update --name context-forge-0 --force
```

**Method 2: Using kubectl (Recommended for quick updates)**

```bash
# 1. Edit plugin files locally
vim plugins/token_cost_calculator/token_cost_calculator.py

# 2. Get pod name
POD=$(kubectl get pods -l app=context-forge-0 -o jsonpath='{.items[0].metadata.name}')

# 3. Copy updated plugin to PVC
kubectl cp plugins/token_cost_calculator/ $POD:/app/plugins/external/token_cost_calculator/

# 4. Restart application
ibmcloud ce application update --name context-forge-0 --force
```

### Add New Plugin

```bash
# 1. Create plugin files locally
mkdir -p plugins/my_new_plugin
# ... create __init__.py, plugin.py, plugin-manifest.yaml

# 2. Update config.yaml to include new plugin
vim plugins/config.yaml
ibmcloud ce configmap update --name plugin-config \
  --from-file plugins/config.yaml

# 3. Copy new plugin to PVC
POD=$(kubectl get pods -l app=context-forge-0 -o jsonpath='{.items[0].metadata.name}')
kubectl cp plugins/my_new_plugin/ $POD:/app/plugins/external/my_new_plugin/

# 4. Restart application
ibmcloud ce application update --name context-forge-0 --force
```

## Complete Workflow Example

Here's a complete example of updating the Token Cost Calculator plugin:

```bash
# 1. Make changes locally
vim plugins/token_cost_calculator/token_cost_calculator.py

# 2. Get pod name
POD=$(kubectl get pods -l app=context-forge-0 -o jsonpath='{.items[0].metadata.name}')

# 3. Copy updated plugin
kubectl cp plugins/token_cost_calculator/ $POD:/app/plugins/external/token_cost_calculator/

# 4. Restart application
ibmcloud ce application update --name context-forge-0 --force

# 5. Verify deployment
ibmcloud ce application get --name context-forge-0

# 6. Check logs
ibmcloud ce application logs --name context-forge-0 --tail 50
```

## Advantages

✅ **Easy Config Updates** - Update config.yaml via CLI without file copying  
✅ **No Size Limits** - Store large plugins without ConfigMap 1MB limit  
✅ **Fast Iteration** - Copy individual plugin files for quick testing  
✅ **Flexible** - Use job for bulk updates or kubectl for quick changes  
✅ **Version Control** - Keep both config and code in Git  

## Troubleshooting

### Plugin Not Loading

Check if PVC is mounted correctly:

```bash
# Get pod name
POD=$(kubectl get pods -l app=context-forge-0 -o jsonpath='{.items[0].metadata.name}')

# List files in PVC
kubectl exec $POD -- ls -la /app/plugins/external/
```

### ConfigMap Not Applied

Ensure you restarted the application:

```bash
ibmcloud ce application update --name context-forge-0 --force
```

### PVC Empty

Run the upload job to populate the PVC:

```bash
ibmcloud ce jobrun submit --job upload-plugins --wait
```

### kubectl Not Working

Ensure you're connected to the correct cluster:

```bash
# Get cluster config
ibmcloud ce project select --name ce-itz-wxo-6a0f136da091f6cc912065
ibmcloud ce project current

# Get kubeconfig
ibmcloud ks cluster config --cluster <cluster-id>
```

## Best Practices

1. **Version Control**: Keep config.yaml and plugin code in Git
2. **Testing**: Test plugin changes in development before production
3. **Backup**: Keep backups of working plugin versions
4. **Documentation**: Document plugin dependencies and requirements
5. **Monitoring**: Monitor application logs after plugin updates
6. **Rollback**: Keep previous plugin versions for quick rollback

## Comparison with Other Approaches

| Approach | Config Updates | Plugin Updates | Complexity | Best For |
|----------|---------------|----------------|------------|----------|
| **Baked in Image** | Rebuild | Rebuild | Low | Production |
| **ConfigMap Only** | Easy | Limited (1MB) | Low | Small plugins |
| **PVC Only** | File copy | Easy | Medium | Large plugins |
| **Hybrid** | Easy | Easy | Medium | **Recommended** |

## Migration from Baked-in Plugins

If you're currently using plugins baked into the Docker image:

```bash
# 1. Run hybrid setup script
./scripts/setup-hybrid-plugins.sh

# 2. Verify plugins are loaded from PVC
POD=$(kubectl get pods -l app=context-forge-0 -o jsonpath='{.items[0].metadata.name}')
kubectl exec $POD -- ls -la /app/plugins/external/

# 3. Test plugin functionality
# ... (test your plugins)

# 4. Once verified, you can remove plugins from Dockerfile (optional)
```

## Additional Resources

- [External Plugin Mounting Guide](external-plugin-mounting.md)
- [Setup Script](../../scripts/setup-hybrid-plugins.sh)
- [IBM Cloud Code Engine PVCs](https://cloud.ibm.com/docs/codeengine?topic=codeengine-storage-pvc)
- [IBM Cloud Code Engine ConfigMaps](https://cloud.ibm.com/docs/codeengine?topic=codeengine-configmap)