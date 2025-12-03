#!/usr/bin/env python3
"""
Download GPT-OSS-20b from HuggingFace and upload to S3.
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

from huggingface_hub import snapshot_download
import boto3
from pathlib import Path

# Configuration
MODEL_ID = "RedHatAI/gpt-oss-20b"
LOCAL_DIR = "/opt/app-root/src/models/gpt-oss-20b"
S3_PREFIX = "gpt-oss-models/gpt-oss-20b"  # Nested one level for vLLM discovery
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

def download_model():
    """Download model from HuggingFace."""
    print(f"Downloading {MODEL_ID} to {LOCAL_DIR}...")
    snapshot_download(
        repo_id=MODEL_ID,
        local_dir=LOCAL_DIR,
        local_dir_use_symlinks=False,
        resume_download=True
    )
    print("Model download complete!")

def download_tiktoken():
    """Download tiktoken vocab file."""
    tiktoken_path = Path(LOCAL_DIR) / "o200k_base.tiktoken"
    if not tiktoken_path.exists():
        print(f"Downloading tiktoken file...")
        import urllib.request
        urllib.request.urlretrieve(TIKTOKEN_URL, tiktoken_path)
        print(f"Tiktoken saved to {tiktoken_path}")
    else:
        print(f"Tiktoken already exists at {tiktoken_path}")

def upload_to_s3():
    """Upload model files to S3."""
    import urllib3
    urllib3.disable_warnings()

    s3 = boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        verify=False
    )

    local_path = Path(LOCAL_DIR)
    total_files = sum(1 for _ in local_path.rglob('*') if _.is_file())
    uploaded = 0

    print(f"Uploading {total_files} files to s3://{S3_BUCKET}/{S3_PREFIX}/...")

    for file_path in local_path.rglob('*'):
        if file_path.is_file():
            relative_path = file_path.relative_to(local_path)
            s3_key = f"{S3_PREFIX}/{relative_path}"

            # Check if file already exists
            try:
                s3.head_object(Bucket=S3_BUCKET, Key=s3_key)
                print(f"  [skip] {relative_path} (already exists)")
                uploaded += 1
                continue
            except:
                pass

            file_size = file_path.stat().st_size
            size_mb = file_size / (1024 * 1024)
            print(f"  [{uploaded+1}/{total_files}] Uploading {relative_path} ({size_mb:.1f} MB)...")

            # Use multipart upload for large files
            if file_size > 100 * 1024 * 1024:  # > 100MB
                from boto3.s3.transfer import TransferConfig
                config = TransferConfig(
                    multipart_threshold=100 * 1024 * 1024,
                    multipart_chunksize=100 * 1024 * 1024,
                    max_concurrency=4
                )
                s3.upload_file(str(file_path), S3_BUCKET, s3_key, Config=config)
            else:
                s3.upload_file(str(file_path), S3_BUCKET, s3_key)

            uploaded += 1

    print(f"\nUpload complete! {uploaded} files uploaded to s3://{S3_BUCKET}/{S3_PREFIX}/")

def main():
    print("=" * 60)
    print("GPT-OSS-20b Download and Upload Script")
    print("=" * 60)

    # Step 1: Download model
    download_model()

    # Step 2: Download tiktoken
    download_tiktoken()

    # Step 3: Upload to S3
    upload_to_s3()

    print("\n" + "=" * 60)
    print("Done! Update your InferenceService to use:")
    print(f"  storage.path: {S3_PREFIX}")
    print("=" * 60)

if __name__ == "__main__":
    main()
