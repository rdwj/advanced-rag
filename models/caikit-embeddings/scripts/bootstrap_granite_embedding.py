#!/usr/bin/env python3
"""
Bootstrap Granite Embedding Model for Caikit Serving

This script bootstraps the IBM Granite embedding model for deployment
on OpenShift AI using the Caikit Standalone serving runtime.

Usage (in OpenShift AI Workbench):
    python bootstrap_embedding_model.py

The script will:
1. Download the model from HuggingFace
2. Convert it to Caikit format
3. Save it to the specified output directory
"""

import os
import sys
from pathlib import Path

# Model configuration
MODEL_NAME = "ibm-granite/granite-embedding-278m-multilingual"
OUTPUT_DIR = "/opt/app-root/src/models/granite-embedding-278m"


def bootstrap_model():
    """Bootstrap the embedding model for Caikit serving."""
    print(f"Bootstrapping model: {MODEL_NAME}")
    print(f"Output directory: {OUTPUT_DIR}")

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    try:
        from caikit_nlp.modules.text_embedding import EmbeddingModule

        print("\nDownloading and converting model...")
        print("This may take several minutes depending on your connection speed.")

        # Bootstrap the model (downloads from HuggingFace and converts to Caikit format)
        model = EmbeddingModule.bootstrap(MODEL_NAME)

        print(f"\nSaving model to {OUTPUT_DIR}...")
        model.save(OUTPUT_DIR)

        print("\nModel bootstrapped successfully!")
        print(f"\nModel files saved to: {OUTPUT_DIR}")

        # List the saved files
        print("\nSaved files:")
        for root, dirs, files in os.walk(OUTPUT_DIR):
            level = root.replace(OUTPUT_DIR, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f'{indent}{os.path.basename(root)}/')
            subindent = ' ' * 2 * (level + 1)
            for file in files:
                filepath = os.path.join(root, file)
                size_mb = os.path.getsize(filepath) / (1024 * 1024)
                print(f'{subindent}{file} ({size_mb:.2f} MB)')

        return True

    except ImportError as e:
        print(f"\nError: caikit-nlp not installed. Run: pip install caikit-nlp")
        print(f"Details: {e}")
        return False
    except Exception as e:
        print(f"\nError bootstrapping model: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = bootstrap_model()
    sys.exit(0 if success else 1)
