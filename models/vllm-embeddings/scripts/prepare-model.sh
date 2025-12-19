#!/bin/bash
# prepare-model.sh - Download HuggingFace models and upload to S3 for RHOAI deployment
#
# Usage:
#   ./prepare-model.sh <model-id> <s3-bucket> [s3-prefix]
#
# Examples:
#   ./prepare-model.sh sentence-transformers/all-MiniLM-L6-v2 my-models-bucket
#   ./prepare-model.sh ibm-granite/granite-embedding-278m-multilingual my-bucket models/embeddings
#   ./prepare-model.sh cross-encoder/ms-marco-MiniLM-L12-v2 my-bucket models/rerankers

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check arguments
if [ $# -lt 2 ]; then
    echo -e "${RED}Error: Missing required arguments${NC}"
    echo ""
    echo "Usage: $0 <model-id> <s3-bucket> [s3-prefix]"
    echo ""
    echo "Arguments:"
    echo "  model-id    HuggingFace model ID (e.g., sentence-transformers/all-MiniLM-L6-v2)"
    echo "  s3-bucket   S3 bucket name (without s3:// prefix)"
    echo "  s3-prefix   Optional path prefix in bucket (default: models)"
    echo ""
    echo "Examples:"
    echo "  $0 sentence-transformers/all-MiniLM-L6-v2 my-models-bucket"
    echo "  $0 ibm-granite/granite-embedding-278m-multilingual my-bucket embeddings"
    exit 1
fi

MODEL_ID="$1"
S3_BUCKET="$2"
S3_PREFIX="${3:-models}"

# Extract model name from ID (e.g., "all-MiniLM-L6-v2" from "sentence-transformers/all-MiniLM-L6-v2")
MODEL_NAME=$(basename "$MODEL_ID")
LOCAL_DIR="/tmp/hf-models/${MODEL_NAME}"
S3_PATH="s3://${S3_BUCKET}/${S3_PREFIX}/${MODEL_NAME}"

echo -e "${GREEN}=== vLLM Model Preparation for RHOAI ===${NC}"
echo ""
echo "Model ID:     $MODEL_ID"
echo "Local Dir:    $LOCAL_DIR"
echo "S3 Path:      $S3_PATH"
echo ""

# Check for required tools
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is required${NC}"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: aws CLI is required${NC}"
    echo "Install with: pip install awscli"
    exit 1
fi

# Check if huggingface_hub is installed
if ! python3 -c "import huggingface_hub" 2>/dev/null; then
    echo -e "${YELLOW}Installing huggingface_hub...${NC}"
    pip install -q huggingface_hub
fi

echo -e "${GREEN}Prerequisites OK${NC}"
echo ""

# Step 1: Download model from HuggingFace
echo -e "${YELLOW}Step 1: Downloading model from HuggingFace...${NC}"
echo "This may take a few minutes depending on model size."
echo ""

# Create local directory
mkdir -p "$LOCAL_DIR"

# Download using huggingface-cli
python3 << EOF
from huggingface_hub import snapshot_download
import os

model_id = "$MODEL_ID"
local_dir = "$LOCAL_DIR"

print(f"Downloading {model_id}...")
snapshot_download(
    repo_id=model_id,
    local_dir=local_dir,
    local_dir_use_symlinks=False,
    ignore_patterns=["*.git*", "*.md", "*.txt"]  # Skip non-essential files
)
print(f"Download complete: {local_dir}")
EOF

echo ""
echo -e "${GREEN}Download complete!${NC}"
echo ""

# Show downloaded files
echo "Downloaded files:"
ls -lh "$LOCAL_DIR"
echo ""

# Calculate total size
TOTAL_SIZE=$(du -sh "$LOCAL_DIR" | cut -f1)
echo "Total size: $TOTAL_SIZE"
echo ""

# Step 2: Upload to S3
echo -e "${YELLOW}Step 2: Uploading to S3...${NC}"
echo "Destination: $S3_PATH"
echo ""

aws s3 sync "$LOCAL_DIR" "$S3_PATH" --no-progress

echo ""
echo -e "${GREEN}Upload complete!${NC}"
echo ""

# Verify upload
echo -e "${YELLOW}Verifying S3 upload...${NC}"
aws s3 ls "$S3_PATH/" --human-readable --summarize

echo ""
echo -e "${GREEN}=== Model Ready for RHOAI Deployment ===${NC}"
echo ""
echo "Next steps in RHOAI:"
echo ""
echo "1. Create a Data Connection:"
echo "   - Go to: OpenShift AI → Data Science Projects → Your Project → Data Connections"
echo "   - Click 'Add data connection'"
echo "   - Name: ${MODEL_NAME}-connection"
echo "   - S3 Bucket: ${S3_BUCKET}"
echo "   - Path: ${S3_PREFIX}/${MODEL_NAME}"
echo "   - Configure AWS credentials"
echo ""
echo "2. Deploy the model:"
echo "   - Go to: Models → Deploy model"
echo "   - Model name: ${MODEL_NAME}"
echo "   - Serving runtime: vLLM Embedding Runtime (or vLLM Reranker Runtime)"
echo "   - Model location: Select your data connection"
echo "   - Path: ${MODEL_NAME} (or leave empty if path is in data connection)"
echo ""
echo "3. Configure resources:"
echo "   - GPU: 1 (NVIDIA)"
echo "   - Memory: 4-8 Gi (depending on model size)"
echo ""

# Cleanup prompt
echo -e "${YELLOW}Cleanup:${NC}"
echo "To remove local files: rm -rf $LOCAL_DIR"
echo ""
