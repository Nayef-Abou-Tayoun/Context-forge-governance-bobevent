#!/usr/bin/env python3
"""
IBM Cloud Object Storage Plugin Sync Script (Python)
Uses boto3 with IBM Cloud COS credentials
Downloads plugins to /tmp which is writable in Code Engine
"""

import os
import sys
import json
from pathlib import Path
import boto3
from botocore.client import Config

def main():
    print("=== IBM Cloud Object Storage Plugin Sync (Python) ===")
    print("Starting plugin sync from COS bucket...")
    
    # Required environment variables
    cos_api_key = os.environ.get('COS_API_KEY')
    cos_instance_id = os.environ.get('COS_INSTANCE_ID')
    cos_bucket = os.environ.get('COS_BUCKET')
    cos_endpoint = os.environ.get('COS_ENDPOINT')
    
    if not all([cos_api_key, cos_instance_id, cos_bucket, cos_endpoint]):
        print("ERROR: Missing required environment variables")
        print("Required: COS_API_KEY, COS_INSTANCE_ID, COS_BUCKET, COS_ENDPOINT")
        sys.exit(1)
    
    # Optional variables
    plugin_dir = os.environ.get('PLUGIN_DIR', '/tmp/plugins')
    cos_prefix = os.environ.get('COS_PREFIX', 'plugins/')
    
    print(f"Configuration:")
    print(f"  COS Endpoint: {cos_endpoint}")
    print(f"  COS Bucket: {cos_bucket}")
    print(f"  COS Prefix: {cos_prefix}")
    print(f"  Plugin Directory: {plugin_dir}")
    
    # Create boto3 client for IBM Cloud COS
    print("Connecting to IBM Cloud COS...")
    cos_client = boto3.client(
        's3',
        aws_access_key_id=cos_api_key,
        aws_secret_access_key=cos_instance_id,
        endpoint_url=f'https://{cos_endpoint}',
        config=Config(signature_version='s3v4')
    )
    
    # Test connection
    try:
        cos_client.list_objects_v2(Bucket=cos_bucket, Prefix=cos_prefix, MaxKeys=1)
        print("✓ COS connection successful")
    except Exception as e:
        print(f"ERROR: Failed to connect to COS: {e}")
        sys.exit(1)
    
    # Create plugin directory
    Path(plugin_dir).mkdir(parents=True, exist_ok=True)
    print(f"✓ Created plugin directory: {plugin_dir}")
    
    # List and download plugins
    print("Listing plugins in COS...")
    try:
        paginator = cos_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=cos_bucket, Prefix=cos_prefix)
        
        file_count = 0
        for page in pages:
            if 'Contents' not in page:
                continue
                
            for obj in page['Contents']:
                key = obj['Key']
                
                # Skip directory markers
                if key.endswith('/'):
                    continue
                
                # Remove prefix to get relative path
                relative_path = key[len(cos_prefix):]
                if not relative_path:
                    continue
                
                local_path = Path(plugin_dir) / relative_path
                
                # Create directory if needed
                local_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Download file
                print(f"  Downloading: {key} -> {local_path}")
                cos_client.download_file(cos_bucket, key, str(local_path))
                file_count += 1
        
        print(f"✓ Downloaded {file_count} file(s) from COS")
        
    except Exception as e:
        print(f"ERROR: Failed to sync plugins: {e}")
        sys.exit(1)
    
    # Count synced plugins
    plugin_dirs = [d for d in Path(plugin_dir).iterdir() if d.is_dir()]
    plugin_count = len(plugin_dirs)
    print(f"✓ Synced {plugin_count} plugin(s) from COS")
    
    # List synced plugins
    if plugin_count > 0:
        print("Synced plugins:")
        for plugin_path in plugin_dirs:
            print(f"  - {plugin_path.name}")
    
    # Verify plugin structure
    print("Verifying plugin structure...")
    for plugin_path in plugin_dirs:
        plugin_name = plugin_path.name
        
        if not (plugin_path / 'plugin.py').exists():
            print(f"WARNING: Plugin {plugin_name} missing plugin.py")
        
        if not (plugin_path / 'plugin-manifest.yaml').exists():
            print(f"WARNING: Plugin {plugin_name} missing plugin-manifest.yaml")
    
    print("=== Plugin sync completed successfully ===")
    print(f"Plugins are available at: {plugin_dir}")

if __name__ == '__main__':
    main()

# Made with Bob