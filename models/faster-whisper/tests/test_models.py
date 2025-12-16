"""Tests for Pydantic response models."""

import json

import pytest

from src.models import (
    ErrorResponse,
    HealthResponse,
    Segment,
    TranscriptionResponse,
    Word,
)


class TestWord:
    """Tests for Word model."""

    def test_word_creation(self):
        word = Word(word="hello", start=0.0, end=0.5, probability=0.95)
        assert word.word == "hello"
        assert word.start == 0.0
        assert word.end == 0.5
        assert word.probability == 0.95

    def test_word_serialization(self):
        word = Word(word="world", start=0.5, end=1.0, probability=0.98)
        data = word.model_dump()
        assert data == {
            "word": "world",
            "start": 0.5,
            "end": 1.0,
            "probability": 0.98,
        }


class TestSegment:
    """Tests for Segment model."""

    def test_segment_with_words(self):
        words = [
            Word(word="hello", start=0.0, end=0.4, probability=0.95),
            Word(word="world", start=0.5, end=0.9, probability=0.98),
        ]
        segment = Segment(
            id=0,
            start=0.0,
            end=1.0,
            text="hello world",
            avg_logprob=-0.25,
            no_speech_prob=0.01,
            words=words,
        )
        assert segment.id == 0
        assert len(segment.words) == 2
        assert segment.words[0].word == "hello"

    def test_segment_empty_words(self):
        segment = Segment(
            id=0,
            start=0.0,
            end=1.0,
            text="test",
            avg_logprob=-0.2,
            no_speech_prob=0.05,
        )
        assert segment.words == []


class TestTranscriptionResponse:
    """Tests for TranscriptionResponse model."""

    def test_full_response(self):
        words = [
            Word(word="Hello", start=0.0, end=0.4, probability=0.95),
            Word(word="world", start=0.5, end=0.9, probability=0.98),
        ]
        segment = Segment(
            id=0,
            start=0.0,
            end=1.0,
            text="Hello world",
            avg_logprob=-0.25,
            no_speech_prob=0.01,
            words=words,
        )
        response = TranscriptionResponse(
            language="en",
            duration=1.0,
            text="Hello world",
            segments=[segment],
        )

        assert response.task == "transcribe"
        assert response.language == "en"
        assert response.duration == 1.0
        assert len(response.segments) == 1
        assert len(response.segments[0].words) == 2

    def test_response_json_serialization(self):
        """Test that response serializes to expected JSON structure."""
        words = [Word(word="test", start=0.0, end=0.5, probability=0.9)]
        segment = Segment(
            id=0,
            start=0.0,
            end=0.5,
            text="test",
            avg_logprob=-0.3,
            no_speech_prob=0.02,
            words=words,
        )
        response = TranscriptionResponse(
            language="en",
            duration=0.5,
            text="test",
            segments=[segment],
        )

        json_str = response.model_dump_json()
        data = json.loads(json_str)

        # Verify structure matches OpenAI verbose_json format
        assert "task" in data
        assert "language" in data
        assert "duration" in data
        assert "text" in data
        assert "segments" in data
        assert "words" in data["segments"][0]


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_healthy_response(self):
        response = HealthResponse(
            status="healthy",
            model_loaded=True,
            model_size="medium",
            device="cuda",
            compute_type="float16",
        )
        assert response.status == "healthy"
        assert response.model_loaded is True

    def test_degraded_response(self):
        response = HealthResponse(
            status="degraded",
            model_loaded=False,
            model_size="",
            device="",
            compute_type="",
        )
        assert response.status == "degraded"
        assert response.model_loaded is False


class TestErrorResponse:
    """Tests for ErrorResponse model."""

    def test_error_response(self):
        error = ErrorResponse(detail="Something went wrong")
        assert error.detail == "Something went wrong"
