#!/usr/bin/env python3
"""
Upload bootstrapped reranker model to S3 with correct nested structure.

Run this script in the OpenShift AI workbench after bootstrapping.
"""

import boto3
import os
import sys
import urllib3

# Disable SSL warnings for self-signed certs
urllib3.disable_warnings()

# S3 Configuration - Set these environment variables before running:
#   S3_ENDPOINT - S3/Noobaa endpoint URL
#   AWS_ACCESS_KEY_ID - S3 access key
#   AWS_SECRET_ACCESS_KEY - S3 secret key
#   S3_BUCKET - Target bucket name
S3_ENDPOINT = os.environ.get("S3_ENDPOINT")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
BUCKET = os.environ.get("S3_BUCKET")

# Validate required environment variables
_required_vars = ["S3_ENDPOINT", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "S3_BUCKET"]
_missing = [v for v in _required_vars if not os.environ.get(v)]
if _missing:
    print(f"ERROR: Missing required environment variables: {', '.join(_missing)}")
    print("\nSet these variables before running:")
    print("  export S3_ENDPOINT='https://s3-openshift-storage.apps.your-cluster.com'")
    print("  export AWS_ACCESS_KEY_ID='your-access-key'")
    print("  export AWS_SECRET_ACCESS_KEY='your-secret-key'")
    print("  export S3_BUCKET='your-bucket-name'")
    sys.exit(1)

# Model paths
MODEL_PATH = "/opt/app-root/src/models/ms-marco-reranker"
# IMPORTANT: Use "models/<model-name>" structure so Caikit discovers the model
S3_PREFIX = "models/ms-marco-reranker"

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    verify=False
)

print(f"Uploading model from {MODEL_PATH} to s3://{BUCKET}/{S3_PREFIX}/")

file_count = 0
for root, dirs, files in os.walk(MODEL_PATH):
    for filename in files:
        local_path = os.path.join(root, filename)
        relative_path = os.path.relpath(local_path, MODEL_PATH)
        s3_key = f"{S3_PREFIX}/{relative_path}"
        print(f"Uploading: {s3_key}")
        s3.upload_file(local_path, BUCKET, s3_key)
        file_count += 1

print(f"\nSuccessfully uploaded {file_count} files")
print(f"Model available at: s3://{BUCKET}/{S3_PREFIX}/")
print("\nVerifying config.yml exists...")

try:
    s3.head_object(Bucket=BUCKET, Key=f"{S3_PREFIX}/config.yml")
    print("✓ config.yml found - model structure is correct")
except Exception as e:
    print(f"✗ config.yml not found - check model structure: {e}")
