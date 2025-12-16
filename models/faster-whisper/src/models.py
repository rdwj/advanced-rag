"""Pydantic models for faster-whisper API responses.

These models follow the OpenAI verbose_json format for transcription output,
with words nested inside segments.
"""

from pydantic import BaseModel, Field


class Word(BaseModel):
    """A single transcribed word with timing information."""

    word: str = Field(..., description="The transcribed word")
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    probability: float = Field(..., description="Confidence probability (0-1)")


class Segment(BaseModel):
    """A transcription segment containing text and word-level details."""

    id: int = Field(..., description="Segment index")
    start: float = Field(..., description="Segment start time in seconds")
    end: float = Field(..., description="Segment end time in seconds")
    text: str = Field(..., description="Transcribed text for this segment")
    avg_logprob: float = Field(..., description="Average log probability")
    no_speech_prob: float = Field(..., description="Probability of no speech")
    words: list[Word] = Field(default_factory=list, description="Word-level timestamps")


class TranscriptionResponse(BaseModel):
    """Full transcription response in OpenAI verbose_json format."""

    task: str = Field(default="transcribe", description="Task type")
    language: str = Field(..., description="Detected or specified language code")
    duration: float = Field(..., description="Audio duration in seconds")
    text: str = Field(..., description="Full transcription text")
    segments: list[Segment] = Field(
        default_factory=list, description="Transcription segments with word timestamps"
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    model_loaded: bool = Field(..., description="Whether model is loaded")
    model_size: str = Field(..., description="Loaded model size")
    device: str = Field(..., description="Compute device (cuda/cpu)")
    compute_type: str = Field(..., description="Compute precision type")


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str = Field(..., description="Error message")
