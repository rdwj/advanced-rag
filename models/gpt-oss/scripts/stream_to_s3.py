#!/usr/bin/env python3
"""
Stream GPT-OSS-20b from HuggingFace directly to S3.
This avoids needing local disk space for the full model.
Run this script in the caikit-embeddings workbench.
"""

import os
import subprocess
import sys

# Install required packages if not present
def install_packages():
    packages = ['huggingface_hub', 'boto3']
    for pkg in packages:
        try:
            __import__(pkg.replace('-', '_'))
        except ImportError:
            print(f"Installing {pkg}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg, '-q'])

install_packages()

from huggingface_hub import hf_hub_download, list_repo_files
import boto3
from pathlib import Path
import tempfile
import urllib3

urllib3.disable_warnings()

# Configuration
MODEL_ID = "RedHatAI/gpt-oss-20b"
S3_PREFIX = "gpt-oss-models/gpt-oss-20b"
TIKTOKEN_URL = "https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken"

# S3 Configuration - Set these environment variables before running:
#   S3_ENDPOINT - S3/Noobaa endpoint URL
#   AWS_ACCESS_KEY_ID - S3 access key
#   AWS_SECRET_ACCESS_KEY - S3 secret key
#   S3_BUCKET - Target bucket name
S3_ENDPOINT = os.environ.get("S3_ENDPOINT")
S3_BUCKET = os.environ.get("S3_BUCKET")
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")

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

def get_s3_client():
    """Create S3 client."""
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        verify=False
    )

def file_exists_in_s3(s3, key):
    """Check if file already exists in S3."""
    try:
        s3.head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except:
        return False

def upload_tiktoken(s3):
    """Download and upload tiktoken vocab file."""
    s3_key = f"{S3_PREFIX}/o200k_base.tiktoken"

    if file_exists_in_s3(s3, s3_key):
        print(f"  [skip] o200k_base.tiktoken (already exists)")
        return

    print(f"Downloading tiktoken file...")
    import urllib.request
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        urllib.request.urlretrieve(TIKTOKEN_URL, tmp.name)
        print(f"  Uploading o200k_base.tiktoken to S3...")
        s3.upload_file(tmp.name, S3_BUCKET, s3_key)
        os.unlink(tmp.name)
    print(f"  [done] o200k_base.tiktoken")

def stream_model_to_s3():
    """Stream model files one at a time from HuggingFace to S3."""
    s3 = get_s3_client()

    # First, upload tiktoken
    upload_tiktoken(s3)

    # List all files in the repo
    print(f"\nListing files in {MODEL_ID}...")
    files = list_repo_files(MODEL_ID)
    total_files = len(files)
    print(f"Found {total_files} files to transfer")

    # Transfer config for large files
    from boto3.s3.transfer import TransferConfig
    config = TransferConfig(
        multipart_threshold=100 * 1024 * 1024,
        multipart_chunksize=100 * 1024 * 1024,
        max_concurrency=4
    )

    transferred = 0
    skipped = 0

    for i, filename in enumerate(files):
        s3_key = f"{S3_PREFIX}/{filename}"

        # Check if already uploaded
        if file_exists_in_s3(s3, s3_key):
            print(f"  [{i+1}/{total_files}] [skip] {filename} (already exists)")
            skipped += 1
            continue

        print(f"  [{i+1}/{total_files}] Downloading {filename}...")

        # Download single file to temp location
        try:
            local_path = hf_hub_download(
                repo_id=MODEL_ID,
                filename=filename,
                local_dir="/tmp/hf_download",
                local_dir_use_symlinks=False
            )

            file_size = os.path.getsize(local_path)
            size_mb = file_size / (1024 * 1024)
            print(f"           Uploading {filename} ({size_mb:.1f} MB) to S3...")

            # Upload to S3
            if file_size > 100 * 1024 * 1024:
                s3.upload_file(local_path, S3_BUCKET, s3_key, Config=config)
            else:
                s3.upload_file(local_path, S3_BUCKET, s3_key)

            # Delete local file immediately to save space
            os.unlink(local_path)

            transferred += 1
            print(f"           [done] {filename}")

        except Exception as e:
            print(f"           [ERROR] {filename}: {e}")

    # Cleanup temp directory
    import shutil
    shutil.rmtree("/tmp/hf_download", ignore_errors=True)

    print(f"\n{'='*60}")
    print(f"Transfer complete!")
    print(f"  Transferred: {transferred} files")
    print(f"  Skipped:     {skipped} files (already existed)")
    print(f"  Total:       {total_files} files")
    print(f"\nModel available at: s3://{S3_BUCKET}/{S3_PREFIX}/")
    print(f"{'='*60}")

def main():
    print("=" * 60)
    print("GPT-OSS-20b Stream to S3")
    print("=" * 60)
    print(f"Model: {MODEL_ID}")
    print(f"Target: s3://{S3_BUCKET}/{S3_PREFIX}/")
    print("=" * 60)
    print()

    stream_model_to_s3()

    print("\nDone! Update your InferenceService to use:")
    print(f"  storage.path: {S3_PREFIX}")

if __name__ == "__main__":
    main()
