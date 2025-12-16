"""Faster-whisper transcription wrapper.

Provides model loading and transcription with verbose_json output format.
"""

import logging
import os
from pathlib import Path
from typing import BinaryIO

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


def load_model(
    model_size: str = "medium",
    device: str = "cuda",
    compute_type: str = "float16",
    model_path: str | None = None,
) -> WhisperModel:
    """Load the faster-whisper model.

    Args:
        model_size: Whisper model size (tiny, base, small, medium, large-v3)
        device: Compute device (cuda, cpu)
        compute_type: Precision type (float16, int8, float32)
        model_path: Optional path to cache/load model from

    Returns:
        Loaded WhisperModel instance
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

    try:
        _model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            download_root=download_root,
        )
        _model_size = model_size
        _device = device
        _compute_type = compute_type
        logger.info(f"Model loaded successfully on {device}")
        return _model
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        # Try CPU fallback if CUDA fails
        if device == "cuda":
            logger.info("Attempting CPU fallback...")
            _model = WhisperModel(
                model_size,
                device="cpu",
                compute_type="float32",
                download_root=download_root,
            )
            _model_size = model_size
            _device = "cpu"
            _compute_type = "float32"
            logger.info("Model loaded on CPU (fallback)")
            return _model
        raise


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
