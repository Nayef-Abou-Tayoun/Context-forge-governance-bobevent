# IBM Cloud Object Storage (COS) Plugin Integration

This guide explains how to configure ContextForge to automatically sync plugins from IBM Cloud Object Storage (COS) at startup.

## Overview

The COS integration allows you to:
- Store plugins centrally in an IBM Cloud Object Storage bucket
- Automatically sync plugins to your Code Engine application at startup
- Update plugins without rebuilding Docker images
- Share plugins across multiple deployments
- Version control plugins in COS

## Architecture

```
┌─────────────────────────────┐
│  IBM Cloud Object Storage   │
│  Bucket: contextforge-plugins│
│                             │
│  plugins/                   │
│  ├── pii_filter_na/         │
│  │   ├── plugin.py          │
│  │   ├── plugin-manifest.yaml│
│  │   └── __init__.py        │
│  ├── token_cost_calculator/ │
│  │   ├── plugin.py          │
│  │   ├── plugin-manifest.yaml│
│  │   └── __init__.py        │
│  └── config.yaml            │
└──────────────┬──────────────┘
               │
               │ Init Container
               │ (s3cmd sync)
               ▼
┌─────────────────────────────┐
│  Code Engine Application    │
│  context-forge-0            │
│                             │
│  Init Container:            │
│  - Install s3cmd           │
│  - Sync from COS           │
│  - Verify plugins          │
│                             │
│  Main Container:            │
│  - /app/plugins/external/  │
│    (synced from COS)       │
│  - /app/plugins/config.yaml│
│    (from ConfigMap)        │
└─────────────────────────────┘
```

## Prerequisites

1. **IBM Cloud Object Storage instance** with HMAC credentials
2. **COS bucket** (e.g., `contextforge-plugins`)
3. **IBM Cloud CLI** with Code Engine plugin
4. **Logged in** to IBM Cloud and Code Engine project

## Quick Start

### 1. Upload Plugins to COS

Upload your plugin directories to the COS bucket under the `plugins/` prefix:

```bash
# Using IBM Cloud CLI
ibmcloud cos upload --bucket contextforge-plugins \
    --key plugins/pii_filter_na/plugin.py \
    --file plugins/pii_filter_na/plugin.py

# Or use the web console to upload entire plugin directories
```

Your COS bucket structure should look like:
```
contextforge-plugins/
└── plugins/
    ├── pii_filter_na/
    │   ├── plugin.py
    │   ├── plugin-manifest.yaml
    │   └── __init__.py
    └── token_cost_calculator/
        ├── plugin.py
        ├── plugin-manifest.yaml
        └── __init__.py
```

### 2. Run Setup Script

```bash
# Make script executable
chmod +x scripts/setup-cos-plugins.sh

# Run setup (uses credentials from script)
./scripts/setup-cos-plugins.sh
```

The script will:
1. Create a secret with COS credentials
2. Create a ConfigMap for `plugins/config.yaml`
3. Update the application with init container for COS sync
4. Wait for application to be ready

### 3. Verify Deployment

```bash
# Check application status
ibmcloud ce app get --name context-forge-0

# View logs to see plugin sync
ibmcloud ce app logs --name context-forge-0 --follow
```

You should see output like:
```
=== IBM Cloud Object Storage Plugin Sync ===
Starting plugin sync from COS bucket...
✓ COS connection successful
Syncing plugins from s3://contextforge-plugins/plugins/ to /app/plugins/external/...
✓ Synced 2 plugin(s) from COS
Synced plugins:
pii_filter_na
token_cost_calculator
=== Plugin sync completed successfully ===
```

## Manual Setup

If you prefer manual setup or need to customize:

### 1. Create COS Credentials Secret

```bash
ibmcloud ce secret create --name cos-credentials \
    --from-literal HMAC_ACCESS_KEY_ID="your-access-key-id" \
    --from-literal HMAC_SECRET_ACCESS_KEY="your-secret-access-key" \
    --from-literal COS_ENDPOINT="s3.us-south.cloud-object-storage.appdomain.cloud" \
    --from-literal COS_BUCKET="contextforge-plugins" \
    --from-literal COS_PREFIX="plugins/"
```

### 2. Create ConfigMap for Plugin Configuration

```bash
ibmcloud ce configmap create --name plugin-config \
    --from-file plugins/config.yaml
```

### 3. Update Application

```bash
ibmcloud ce application update --name context-forge-0 \
    --env-from-secret cos-credentials \
    --env PLUGINS_ENABLED=true \
    --env PLUGINS_CONFIG_FILE=/app/plugins/config.yaml \
    --mount-configmap /app/plugins=plugin-config \
    --command /bin/bash \
    --argument "-c" \
    --argument "pip install s3cmd && bash /app/scripts/sync-plugins-from-cos.sh && exec python -m mcpgateway.main"
```

## Updating Plugins

### Update Plugin Code

1. **Upload new plugin files to COS**:
   ```bash
   ibmcloud cos upload --bucket contextforge-plugins \
       --key plugins/my_plugin/plugin.py \
       --file plugins/my_plugin/plugin.py
   ```

2. **Restart application** to sync changes:
   ```bash
   ibmcloud ce app update --name context-forge-0 --force
   ```

### Update Plugin Configuration

1. **Update local `plugins/config.yaml`**

2. **Update ConfigMap**:
   ```bash
   ibmcloud ce configmap update --name plugin-config \
       --from-file plugins/config.yaml
   ```

3. **Restart application**:
   ```bash
   ibmcloud ce app update --name context-forge-0 --force
   ```

### Update Both Code and Config

```bash
# 1. Upload plugin files to COS
ibmcloud cos upload --bucket contextforge-plugins \
    --key plugins/my_plugin/plugin.py \
    --file plugins/my_plugin/plugin.py

# 2. Update ConfigMap
ibmcloud ce configmap update --name plugin-config \
    --from-file plugins/config.yaml

# 3. Restart application
ibmcloud ce app update --name context-forge-0 --force
```

## Configuration

### Environment Variables

The sync script uses these environment variables (set via secret):

| Variable | Description | Example |
|----------|-------------|---------|
| `COS_ENDPOINT` | COS S3 endpoint | `s3.us-south.cloud-object-storage.appdomain.cloud` |
| `COS_BUCKET` | Bucket name | `contextforge-plugins` |
| `COS_PREFIX` | Prefix for plugins | `plugins/` |
| `HMAC_ACCESS_KEY_ID` | HMAC access key | `b0b913488dff45bf...` |
| `HMAC_SECRET_ACCESS_KEY` | HMAC secret key | `ba2549209412a4f3...` |
| `PLUGIN_DIR` | Local plugin directory | `/app/plugins/external` |

### COS Bucket Structure

Recommended structure:
```
contextforge-plugins/
├── plugins/                    # Plugin code (synced to /app/plugins/external/)
│   ├── pii_filter_na/
│   │   ├── plugin.py
│   │   ├── plugin-manifest.yaml
│   │   ├── __init__.py
│   │   └── README.md
│   └── token_cost_calculator/
│       ├── plugin.py
│       ├── plugin-manifest.yaml
│       ├── __init__.py
│       └── README.md
└── config/                     # Optional: versioned configs
    ├── config-v1.yaml
    └── config-v2.yaml
```

## Troubleshooting

### Check Sync Logs

```bash
# View application logs
ibmcloud ce app logs --name context-forge-0 --follow

# Look for sync output
ibmcloud ce app logs --name context-forge-0 | grep "Plugin Sync"
```

### Verify COS Connection

```bash
# Test COS access manually
ibmcloud cos list-objects --bucket contextforge-plugins --prefix plugins/
```

### Common Issues

#### 1. Plugins Not Loading

**Symptom**: Application starts but plugins don't appear

**Solution**:
```bash
# Check if plugins were synced
ibmcloud ce app logs --name context-forge-0 | grep "Synced.*plugin"

# Verify plugin structure in COS
ibmcloud cos list-objects --bucket contextforge-plugins --prefix plugins/
```

#### 2. COS Connection Failed

**Symptom**: `ERROR: Failed to connect to COS bucket`

**Solution**:
```bash
# Verify credentials
ibmcloud ce secret get --name cos-credentials

# Test credentials manually
s3cmd --access_key=YOUR_KEY --secret_key=YOUR_SECRET \
    --host=s3.us-south.cloud-object-storage.appdomain.cloud \
    ls s3://contextforge-plugins/
```

#### 3. Init Container Fails

**Symptom**: Application stuck in "Deploying" state

**Solution**:
```bash
# Check pod events
kubectl get pods -l app=context-forge-0
kubectl describe pod <pod-name>

# View init container logs
kubectl logs <pod-name> -c init-sync-plugins
```

## Security Considerations

1. **HMAC Credentials**: Stored as Code Engine secrets (encrypted at rest)
2. **Bucket Access**: Use IAM policies to restrict bucket access
3. **Plugin Validation**: Sync script verifies plugin structure
4. **Network Security**: COS access uses HTTPS

## Performance

- **Sync Time**: ~5-10 seconds for typical plugin sets
- **Storage**: Minimal (plugins stored in COS, not in container image)
- **Startup**: Adds ~10-15 seconds to application startup time

## Comparison with Other Approaches

| Approach | Pros | Cons |
|----------|------|------|
| **COS Sync** | Centralized storage, easy updates, version control | Requires COS, adds startup time |
| **Baked-in** | Fast startup, no dependencies | Requires image rebuild for updates |
| **ConfigMap** | Simple, no external deps | 1MB size limit, not ideal for large plugins |
| **PVC** | No size limit, persistent | Requires manual file copying |

## Best Practices

1. **Version Control**: Keep plugin versions in COS with dated prefixes
2. **Testing**: Test plugins locally before uploading to COS
3. **Monitoring**: Monitor sync logs for failures
4. **Backup**: Enable COS versioning for plugin backup
5. **Documentation**: Document plugin changes in COS object metadata

## Advanced Usage

### Multiple Environments

Use different COS prefixes for different environments:

```bash
# Production
COS_PREFIX="plugins/prod/"

# Staging
COS_PREFIX="plugins/staging/"

# Development
COS_PREFIX="plugins/dev/"
```

### Plugin Versioning

Store versioned plugins in COS:

```
contextforge-plugins/
└── plugins/
    ├── current/              # Active plugins
    │   └── pii_filter_na/
    └── versions/             # Historical versions
        ├── v1.0.0/
        │   └── pii_filter_na/
        └── v1.1.0/
            └── pii_filter_na/
```

### Automated Deployment

Integrate with CI/CD:

```yaml
# .github/workflows/deploy-plugins.yml
name: Deploy Plugins to COS
on:
  push:
    paths:
      - 'plugins/**'
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Upload to COS
        run: |
          ibmcloud cos upload --bucket contextforge-plugins \
            --key plugins/ --file plugins/ --recursive
      - name: Restart Application
        run: |
          ibmcloud ce app update --name context-forge-0 --force
```

## Support

For issues or questions:
- Check application logs: `ibmcloud ce app logs --name context-forge-0`
- Review COS bucket contents: `ibmcloud cos list-objects --bucket contextforge-plugins`
- Verify credentials: `ibmcloud ce secret get --name cos-credentials`