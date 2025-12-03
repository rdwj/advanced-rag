#!/usr/bin/env python3
"""
Upload bootstrapped MiniLM embedding model to S3 with correct nested structure.

Run this script in the OpenShift AI workbench after running bootstrap_minilm_embedding.py.

IMPORTANT: Caikit requires models to be nested one level deep:
  - CORRECT: s3://bucket/minilm-models/all-minilm-l6-v2/config.yml
  - WRONG:   s3://bucket/all-minilm-l6-v2/config.yml

The InferenceService 'storage.path' should point to the parent folder ('minilm-models'),
and Caikit will discover the model in the subfolder.
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
MODEL_PATH = "/opt/app-root/src/models/all-minilm-l6-v2"

# IMPORTANT: Use "parent-folder/model-name" structure so Caikit discovers the model
# The InferenceService storage.path should be "minilm-models" (the parent folder)
S3_PREFIX = "minilm-models/all-minilm-l6-v2"

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    verify=False
)


def upload_model():
    """Upload model with correct nested structure."""
    print(f"Uploading model from {MODEL_PATH} to s3://{BUCKET}/{S3_PREFIX}/")
    print(f"\nThis creates the correct nested structure for Caikit:")
    print(f"  s3://{BUCKET}/minilm-models/")
    print(f"    └── all-minilm-l6-v2/")
    print(f"        └── config.yml (and other model files)")
    print()

    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model path does not exist: {MODEL_PATH}")
        print("Run bootstrap_minilm_embedding.py first to download the model.")
        return False

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
    return True


def verify_structure():
    """Verify the model structure is correct."""
    print("\nVerifying model structure...")

    # Check config.yml exists at correct nested path
    config_key = f"{S3_PREFIX}/config.yml"
    try:
        s3.head_object(Bucket=BUCKET, Key=config_key)
        print(f"✓ config.yml found at {config_key}")
    except Exception as e:
        print(f"✗ config.yml not found at {config_key}")
        print(f"  Error: {e}")
        return False

    # List contents to show structure
    print(f"\nModel files in s3://{BUCKET}/{S3_PREFIX}/:")
    response = s3.list_objects_v2(Bucket=BUCKET, Prefix=S3_PREFIX)
    if 'Contents' in response:
        for obj in response['Contents'][:20]:  # Show first 20 files
            key = obj['Key'].replace(S3_PREFIX + "/", "  ")
            size_mb = obj['Size'] / (1024 * 1024)
            print(f"  {key} ({size_mb:.2f} MB)")
        if len(response['Contents']) > 20:
            print(f"  ... and {len(response['Contents']) - 20} more files")

    print("\n" + "="*60)
    print("NEXT STEPS:")
    print("="*60)
    print("""
1. Deploy the InferenceService:
   make deploy-minilm

   Or manually:
   oc apply -f manifests/minilm-embedding/inference-service.yaml -n caikit-embeddings

2. Test the endpoint:
   curl -X POST $ENDPOINT/api/v1/task/embedding \\
     -H 'Content-Type: application/json' \\
     -d '{"model_id": "all-minilm-l6-v2", "inputs": "Hello world"}'
""")
    return True


if __name__ == "__main__":
    if upload_model():
        verify_structure()
