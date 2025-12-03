#!/usr/bin/env python3
"""
Bootstrap cross-encoder reranker model for Caikit serving on OpenShift AI.

Run this script in the OpenShift AI workbench to bootstrap the model,
then upload to S3 for serving via InferenceService.

Usage:
    python bootstrap_reranker_model.py
"""

import os

# Don't create the output directory - caikit.save() needs it to not exist
MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L12-v2"
OUTPUT_DIR = "/opt/app-root/src/models/ms-marco-reranker"

# Ensure parent directory exists
os.makedirs(os.path.dirname(OUTPUT_DIR), exist_ok=True)

print(f"Bootstrapping {MODEL_NAME}...")
print("This may take a few minutes to download the model...")

from caikit_nlp.modules.text_embedding import CrossEncoderModule

model = CrossEncoderModule.bootstrap(MODEL_NAME)
model.save(OUTPUT_DIR)

print(f"Model saved to {OUTPUT_DIR}")
print("\nNext steps:")
print("1. Upload the model to S3 with the correct nested structure")
print("2. Deploy InferenceService pointing to the model")
print("3. Test the /api/v1/task/rerank endpoint")
