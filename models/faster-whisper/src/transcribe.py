"""Faster-whisper transcription wrapper.

Provides model loading and transcription with verbose_json output format.
"""

import logging
import os
from pathlib import Path
from typing import BinaryIO

import numpy as np
from faster_whisper import WhisperModel

from .models import Segment, TranscriptionResponse, Word

logger = logging.getLogger(__name__)

# Global model instance
_model: WhisperModel | None = None
_model_size: str = ""
_device: str = ""
_compute_type: str = ""


def get_model_config() -> dict:
    """Get current model configuration."""
    return {
        "model_size": _model_size,
        "device": _device,
        "compute_type": _compute_type,
        "model_loaded": _model is not None,
    }


def _check_cuda_available() -> bool:
    """Check if CUDA is actually available and functional.

    This performs a lightweight check before attempting to load models,
    catching cuDNN library issues that would crash the process.

    Returns:
        True if CUDA is available and functional, False otherwise
    """
    try:
        import torch

        if not torch.cuda.is_available():
            logger.info("CUDA not available (torch.cuda.is_available() = False)")
            return False

        # Try to actually use CUDA - this catches cuDNN issues
        logger.info("Testing CUDA availability...")
        device = torch.device("cuda")
        # Allocate a small tensor on GPU
        x = torch.zeros(1, device=device)
        # Run a simple operation to verify CUDA works
        y = x + 1
        del x, y
        torch.cuda.empty_cache()

        logger.info(f"CUDA is available: {torch.cuda.get_device_name(0)}")
        return True

    except Exception as e:
        logger.warning(f"CUDA check failed: {e}")
        return False


def _validate_model(model: WhisperModel, device: str) -> bool:
    """Validate model works by running a tiny test transcription.

    This catches issues like missing cuDNN libraries that only manifest
    during actual inference, not during model loading.

    Args:
        model: Loaded WhisperModel instance
        device: Device the model is loaded on

    Returns:
        True if validation passed, False otherwise
    """
    try:
        # Generate 1 second of silence as test audio
        test_audio = np.zeros(16000, dtype=np.float32)

        # Run a minimal transcription to verify CUDA/cuDNN works
        logger.info(f"Validating model on {device}...")
        segments, _ = model.transcribe(
            test_audio,
            language="en",
            word_timestamps=False,
            vad_filter=False,
        )
        # Consume the generator to actually run inference
        list(segments)
        logger.info(f"Model validation passed on {device}")
        return True
    except Exception as e:
        logger.warning(f"Model validation failed on {device}: {e}")
        return False


def load_model(
    model_size: str = "medium",
    device: str = "cuda",
    compute_type: str = "float16",
    model_path: str | None = None,
) -> WhisperModel:
    """Load the faster-whisper model with automatic CPU fallback.

    Args:
        model_size: Whisper model size (tiny, base, small, medium, large-v3)
        device: Compute device (cuda, cpu)
        compute_type: Precision type (float16, int8, float32)
        model_path: Optional path to cache/load model from

    Returns:
        Loaded WhisperModel instance

    Note:
        If CUDA is not available or validation fails, automatically falls back to CPU.
        This handles cases where CUDA loads but cuDNN ops fail during inference.
    """
    global _model, _model_size, _device, _compute_type

    if _model is not None:
        logger.info("Model already loaded, returning existing instance")
        return _model

    # Determine download directory
    download_root = model_path or os.environ.get("MODEL_PATH", "/mnt/models")
    Path(download_root).mkdir(parents=True, exist_ok=True)

    logger.info(
        f"Loading faster-whisper model: size={model_size}, device={device}, "
        f"compute_type={compute_type}, download_root={download_root}"
    )

    # Check CUDA availability BEFORE attempting to load on GPU
    # This catches cuDNN issues that would crash the process
    use_cuda = device == "cuda" and _check_cuda_available()

    if device == "cuda" and not use_cuda:
        logger.warning("CUDA requested but not available/functional, falling back to CPU")
        device = "cpu"
        compute_type = "float32"

    # Try loading on determined device
    try:
        model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            download_root=download_root,
        )
        logger.info(f"Model loaded on {device}")

        # Validate the model actually works
        if _validate_model(model, device):
            _model = model
            _model_size = model_size
            _device = device
            _compute_type = compute_type
            return _model
        else:
            logger.warning(f"Model validation failed on {device}, will try fallback")
            del model  # Free memory before fallback

    except Exception as e:
        logger.warning(f"Failed to load model on {device}: {e}")

    # CPU fallback if CUDA failed or validation failed
    if device == "cuda":
        logger.info("Attempting CPU fallback...")
        try:
            model = WhisperModel(
                model_size,
                device="cpu",
                compute_type="float32",  # CPU works best with float32
                download_root=download_root,
            )

            if _validate_model(model, "cpu"):
                _model = model
                _model_size = model_size
                _device = "cpu"
                _compute_type = "float32"
                logger.info("Model loaded and validated on CPU (fallback)")
                return _model
            else:
                raise RuntimeError("CPU fallback validation also failed")

        except Exception as e:
            logger.error(f"CPU fallback failed: {e}")
            raise RuntimeError(f"Could not load model on any device: {e}")

    raise RuntimeError(f"Failed to load model on {device}")


def transcribe(
    audio: str | BinaryIO,
    language: str | None = None,
) -> TranscriptionResponse:
    """Transcribe audio and return verbose_json format response.

    Args:
        audio: Path to audio file or file-like object
        language: Optional language code (auto-detect if not specified)

    Returns:
        TranscriptionResponse with segments containing word timestamps
    """
    if _model is None:
        raise RuntimeError("Model not loaded. Call load_model() first.")

    logger.info(f"Starting transcription, language={language or 'auto'}")

    # Run transcription with word timestamps enabled
    segments_generator, info = _model.transcribe(
        audio,
        language=language,
        word_timestamps=True,
        vad_filter=True,
    )

    # Convert generator to list and build response
    segments_list = []
    full_text_parts = []

    for idx, segment in enumerate(segments_generator):
        # Extract words with timestamps
        words = []
        if segment.words:
            for word_info in segment.words:
                words.append(
                    Word(
                        word=word_info.word,
                        start=round(word_info.start, 3),
                        end=round(word_info.end, 3),
                        probability=round(word_info.probability, 4),
                    )
                )

        segments_list.append(
            Segment(
                id=idx,
                start=round(segment.start, 3),
                end=round(segment.end, 3),
                text=segment.text.strip(),
                avg_logprob=round(segment.avg_logprob, 4),
                no_speech_prob=round(segment.no_speech_prob, 4),
                words=words,
            )
        )
        full_text_parts.append(segment.text.strip())

    full_text = " ".join(full_text_parts)
    duration = info.duration if info.duration else 0.0

    logger.info(
        f"Transcription complete: {len(segments_list)} segments, "
        f"duration={duration:.2f}s, language={info.language}"
    )

    return TranscriptionResponse(
        task="transcribe",
        language=info.language,
        duration=round(duration, 3),
        text=full_text,
        segments=segments_list,
    )
