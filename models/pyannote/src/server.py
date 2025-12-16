"""FastAPI server for pyannote speaker diarization with async processing."""

import asyncio
import os
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

import numpy as np
import soundfile as sf
import torch
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from pyannote.audio import Pipeline

app = FastAPI(
    title="Pyannote Speaker Diarization API",
    description="Speaker diarization and embeddings using pyannote-audio",
    version="2.0.0",
)

# Global pipeline instance
pipeline: Optional[Pipeline] = None

# Thread pool for CPU-bound diarization work
executor = ThreadPoolExecutor(max_workers=2)

# In-memory job storage (for single pod - use Redis for multi-pod)
jobs: dict = {}

# Job expiration time (clean up old jobs)
JOB_EXPIRATION_HOURS = 24


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DiarizationSegment(BaseModel):
    start: float
    end: float
    speaker: str


class DiarizationResponse(BaseModel):
    segments: list[DiarizationSegment]
    num_speakers: int


class SpeakerEmbedding(BaseModel):
    speaker: str
    embedding: list[float]


class EmbeddingsResponse(BaseModel):
    embeddings: list[SpeakerEmbedding]
    dimension: int


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: str
    message: Optional[str] = None


class JobResultResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[DiarizationResponse] = None
    embeddings: Optional[EmbeddingsResponse] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    device: str
    active_jobs: int


def load_audio(file_path: str) -> dict:
    """Load audio file and convert to pyannote format."""
    waveform, sample_rate = sf.read(file_path, dtype="float32")
    waveform = torch.from_numpy(waveform)
    if waveform.ndim == 1:
        waveform = waveform.unsqueeze(0)
    else:
        waveform = waveform.T
    return {"waveform": waveform, "sample_rate": sample_rate}


def run_diarization(
    audio: dict,
    num_speakers: Optional[int] = None,
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None,
    return_embeddings: bool = False,
) -> tuple:
    """Run diarization synchronously (called from thread pool)."""
    params = {}
    if num_speakers is not None:
        params["num_speakers"] = num_speakers
    if min_speakers is not None:
        params["min_speakers"] = min_speakers
    if max_speakers is not None:
        params["max_speakers"] = max_speakers

    result = pipeline(audio, **params)

    # Extract annotation
    diarization = getattr(result, "speaker_diarization", result)

    # Build segments
    segments = []
    speakers = set()
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        segments.append(
            DiarizationSegment(start=turn.start, end=turn.end, speaker=speaker)
        )
        speakers.add(speaker)

    diarization_result = DiarizationResponse(
        segments=segments, num_speakers=len(speakers)
    )

    # Extract embeddings if requested
    embeddings_result = None
    if return_embeddings:
        speaker_embeddings = getattr(result, "speaker_embeddings", None)
        if speaker_embeddings is not None:
            embeddings = []
            speaker_list = sorted(speakers)
            for i, speaker in enumerate(speaker_list):
                if i < len(speaker_embeddings):
                    emb = speaker_embeddings[i]
                    if isinstance(emb, np.ndarray):
                        emb = emb.tolist()
                    elif isinstance(emb, torch.Tensor):
                        emb = emb.cpu().numpy().tolist()
                    embeddings.append(SpeakerEmbedding(speaker=speaker, embedding=emb))
            if embeddings:
                embeddings_result = EmbeddingsResponse(
                    embeddings=embeddings, dimension=len(embeddings[0].embedding)
                )

    return diarization_result, embeddings_result


async def process_job(job_id: str, file_path: str, params: dict):
    """Process diarization job in background."""
    try:
        jobs[job_id]["status"] = JobStatus.PROCESSING

        # Load audio
        audio = load_audio(file_path)

        # Run diarization in thread pool to not block event loop
        loop = asyncio.get_event_loop()
        diarization_result, embeddings_result = await loop.run_in_executor(
            executor,
            run_diarization,
            audio,
            params.get("num_speakers"),
            params.get("min_speakers"),
            params.get("max_speakers"),
            params.get("return_embeddings", False),
        )

        jobs[job_id]["status"] = JobStatus.COMPLETED
        jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
        jobs[job_id]["result"] = diarization_result
        jobs[job_id]["embeddings"] = embeddings_result

    except Exception as e:
        jobs[job_id]["status"] = JobStatus.FAILED
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()

    finally:
        # Clean up temp file
        if os.path.exists(file_path):
            os.unlink(file_path)


def cleanup_old_jobs():
    """Remove jobs older than expiration time."""
    cutoff = datetime.utcnow() - timedelta(hours=JOB_EXPIRATION_HOURS)
    to_delete = []
    for job_id, job in jobs.items():
        created = datetime.fromisoformat(job["created_at"])
        if created < cutoff:
            to_delete.append(job_id)
    for job_id in to_delete:
        del jobs[job_id]


@app.on_event("startup")
async def load_model():
    """Load the pyannote pipeline on startup."""
    global pipeline

    model_path = os.getenv("MODEL_PATH", "/mnt/models")
    hf_token = os.getenv("HF_TOKEN")
    model_name = os.getenv("MODEL_NAME", "pyannote/speaker-diarization-3.1")

    device = "cuda" if torch.cuda.is_available() else "cpu"

    try:
        if os.path.exists(os.path.join(model_path, "config.yaml")):
            pipeline = Pipeline.from_pretrained(model_path)
        else:
            if not hf_token:
                raise ValueError(
                    "HF_TOKEN required to download model from HuggingFace. "
                    "Either provide HF_TOKEN or mount model at MODEL_PATH."
                )
            pipeline = Pipeline.from_pretrained(model_name, token=hf_token)

        pipeline = pipeline.to(torch.device(device))
        print(f"Model loaded successfully on {device}")
    except Exception as e:
        print(f"Failed to load model: {e}")
        raise


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    active = sum(1 for j in jobs.values() if j["status"] in [JobStatus.PENDING, JobStatus.PROCESSING])
    return HealthResponse(
        status="healthy" if pipeline is not None else "unhealthy",
        model_loaded=pipeline is not None,
        device=device,
        active_jobs=active,
    )


@app.get("/ready")
async def ready():
    """Readiness probe endpoint."""
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "ready"}


# =============================================================================
# SYNCHRONOUS ENDPOINTS (original behavior)
# =============================================================================


@app.post("/v1/diarize", response_model=DiarizationResponse)
async def diarize(
    file: UploadFile = File(...),
    num_speakers: Optional[int] = Form(None),
    min_speakers: Optional[int] = Form(None),
    max_speakers: Optional[int] = Form(None),
):
    """
    Perform speaker diarization on an audio file (synchronous).

    For long audio files, consider using /v1/diarize/async instead.
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        audio = load_audio(tmp_path)
        loop = asyncio.get_event_loop()
        result, _ = await loop.run_in_executor(
            executor, run_diarization, audio, num_speakers, min_speakers, max_speakers, False
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diarization failed: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/v1/vad")
async def voice_activity_detection(file: UploadFile = File(...)):
    """Perform voice activity detection on an audio file."""
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        audio = load_audio(tmp_path)
        loop = asyncio.get_event_loop()
        result, _ = await loop.run_in_executor(
            executor, run_diarization, audio, None, None, None, False
        )
        speech_segments = [{"start": s.start, "end": s.end} for s in result.segments]
        return {"speech_segments": speech_segments}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VAD failed: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# =============================================================================
# ASYNCHRONOUS JOB ENDPOINTS
# =============================================================================


@app.post("/v1/diarize/async", response_model=JobResponse)
async def diarize_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    num_speakers: Optional[int] = Form(None),
    min_speakers: Optional[int] = Form(None),
    max_speakers: Optional[int] = Form(None),
    return_embeddings: bool = Form(False),
):
    """
    Submit audio for asynchronous diarization.

    Returns a job_id immediately. Poll /v1/jobs/{job_id} for results.

    Args:
        file: Audio file (WAV format recommended)
        num_speakers: Exact number of speakers (optional)
        min_speakers: Minimum number of speakers (optional)
        max_speakers: Maximum number of speakers (optional)
        return_embeddings: Also extract speaker embeddings (for Milvus storage)
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    # Clean up old jobs periodically
    cleanup_old_jobs()

    # Save file to temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    # Create job
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": JobStatus.PENDING,
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "result": None,
        "embeddings": None,
        "error": None,
    }

    # Queue background processing
    params = {
        "num_speakers": num_speakers,
        "min_speakers": min_speakers,
        "max_speakers": max_speakers,
        "return_embeddings": return_embeddings,
    }
    background_tasks.add_task(process_job, job_id, tmp_path, params)

    return JobResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        created_at=jobs[job_id]["created_at"],
        message="Job submitted. Poll /v1/jobs/{job_id} for results.",
    )


@app.get("/v1/jobs/{job_id}", response_model=JobResultResponse)
async def get_job(job_id: str):
    """
    Get the status and results of a diarization job.

    Poll this endpoint until status is 'completed' or 'failed'.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    return JobResultResponse(
        job_id=job_id,
        status=job["status"],
        created_at=job["created_at"],
        completed_at=job["completed_at"],
        result=job["result"],
        embeddings=job["embeddings"],
        error=job["error"],
    )


@app.get("/v1/jobs")
async def list_jobs(status: Optional[JobStatus] = None, limit: int = 100):
    """List recent jobs, optionally filtered by status."""
    result = []
    for job_id, job in list(jobs.items())[-limit:]:
        if status is None or job["status"] == status:
            result.append(
                {
                    "job_id": job_id,
                    "status": job["status"],
                    "created_at": job["created_at"],
                    "completed_at": job["completed_at"],
                }
            )
    return {"jobs": result, "total": len(result)}


@app.delete("/v1/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a completed or failed job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    if job["status"] in [JobStatus.PENDING, JobStatus.PROCESSING]:
        raise HTTPException(status_code=400, detail="Cannot delete active job")

    del jobs[job_id]
    return {"message": "Job deleted"}


# =============================================================================
# EMBEDDINGS ENDPOINT
# =============================================================================


@app.post("/v1/embeddings", response_model=EmbeddingsResponse)
async def extract_embeddings(
    file: UploadFile = File(...),
    num_speakers: Optional[int] = Form(None),
    min_speakers: Optional[int] = Form(None),
    max_speakers: Optional[int] = Form(None),
):
    """
    Extract speaker embeddings from audio.

    Returns embeddings for each detected speaker. These embeddings can be
    stored in Milvus for cross-recording speaker identification.

    Embedding dimension: 512 (pyannote speaker embedding model)
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        audio = load_audio(tmp_path)
        loop = asyncio.get_event_loop()
        _, embeddings_result = await loop.run_in_executor(
            executor, run_diarization, audio, num_speakers, min_speakers, max_speakers, True
        )

        if embeddings_result is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to extract embeddings. Model may not support embedding extraction.",
            )

        return embeddings_result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding extraction failed: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/v1/diarize-with-embeddings")
async def diarize_with_embeddings(
    file: UploadFile = File(...),
    num_speakers: Optional[int] = Form(None),
    min_speakers: Optional[int] = Form(None),
    max_speakers: Optional[int] = Form(None),
):
    """
    Perform diarization and extract embeddings in one call.

    Returns both diarization segments and speaker embeddings.
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        audio = load_audio(tmp_path)
        loop = asyncio.get_event_loop()
        diarization_result, embeddings_result = await loop.run_in_executor(
            executor, run_diarization, audio, num_speakers, min_speakers, max_speakers, True
        )

        return {
            "diarization": diarization_result,
            "embeddings": embeddings_result,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# =============================================================================
# SPEAKER TRACKING ENDPOINTS (Milvus integration)
# =============================================================================

# Lazy import to avoid startup failure if Milvus is unavailable
_speaker_tracker = None


def get_speaker_tracker():
    """Get speaker tracker, initializing on first use."""
    global _speaker_tracker
    if _speaker_tracker is None:
        try:
            from speaker_tracker import SpeakerTracker
            _speaker_tracker = SpeakerTracker()
            if not _speaker_tracker.connect():
                _speaker_tracker = None
        except Exception as e:
            print(f"Speaker tracker unavailable: {e}")
            _speaker_tracker = None
    return _speaker_tracker


@app.get("/v1/speakers/status")
async def speaker_tracking_status():
    """Check if speaker tracking (Milvus) is available."""
    tracker = get_speaker_tracker()
    if tracker is None:
        return {
            "available": False,
            "message": "Milvus connection not available. Set MILVUS_HOST env var.",
        }
    return {
        "available": True,
        "stats": tracker.get_collection_stats(),
    }


@app.post("/v1/speakers/identify")
async def identify_speakers(
    file: UploadFile = File(...),
    recording_id: Optional[str] = Form(None),
    num_speakers: Optional[int] = Form(None),
    min_speakers: Optional[int] = Form(None),
    max_speakers: Optional[int] = Form(None),
    similarity_threshold: Optional[float] = Form(None),
):
    """
    Diarize audio and identify speakers against known speakers in Milvus.

    For each detected speaker:
    - If embedding matches a known speaker, returns the persistent speaker_id
    - If no match, creates a new speaker_id

    This enables tracking speakers across multiple recordings.
    """
    tracker = get_speaker_tracker()
    if tracker is None:
        raise HTTPException(
            status_code=503,
            detail="Speaker tracking unavailable. Milvus not connected.",
        )

    if pipeline is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        audio = load_audio(tmp_path)
        loop = asyncio.get_event_loop()
        diarization_result, embeddings_result = await loop.run_in_executor(
            executor, run_diarization, audio, num_speakers, min_speakers, max_speakers, True
        )

        if embeddings_result is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to extract embeddings for speaker identification.",
            )

        # Identify each speaker
        identified_speakers = []
        for emb in embeddings_result.embeddings:
            result = tracker.identify_or_create(
                embedding=emb.embedding,
                recording_id=recording_id,
                session_speaker=emb.speaker,
                threshold=similarity_threshold,
            )
            identified_speakers.append({
                "session_speaker": emb.speaker,
                "speaker_id": result["speaker_id"],
                "speaker_name": result["speaker_name"],
                "is_new": result["is_new"],
                "similarity": result["similarity"],
                "matched_recording": result["matched_recording"],
            })

        # Map session speakers to persistent IDs in segments
        speaker_map = {s["session_speaker"]: s["speaker_id"] for s in identified_speakers}
        segments_with_ids = []
        for seg in diarization_result.segments:
            segments_with_ids.append({
                "start": seg.start,
                "end": seg.end,
                "session_speaker": seg.speaker,
                "speaker_id": speaker_map.get(seg.speaker, seg.speaker),
            })

        return {
            "recording_id": recording_id,
            "num_speakers": diarization_result.num_speakers,
            "speakers": identified_speakers,
            "segments": segments_with_ids,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Speaker identification failed: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/v1/speakers/search")
async def search_speaker(
    file: UploadFile = File(...),
    limit: int = Form(5),
    threshold: Optional[float] = Form(None),
):
    """
    Search for matching speakers given an audio sample.

    Extracts embeddings from the audio and searches Milvus for similar speakers.
    Useful for finding if a speaker has appeared in previous recordings.
    """
    tracker = get_speaker_tracker()
    if tracker is None:
        raise HTTPException(
            status_code=503,
            detail="Speaker tracking unavailable. Milvus not connected.",
        )

    if pipeline is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        audio = load_audio(tmp_path)
        loop = asyncio.get_event_loop()
        _, embeddings_result = await loop.run_in_executor(
            executor, run_diarization, audio, None, None, None, True
        )

        if embeddings_result is None or not embeddings_result.embeddings:
            raise HTTPException(
                status_code=500,
                detail="No speakers detected in audio.",
            )

        # Search for each detected speaker
        results = []
        for emb in embeddings_result.embeddings:
            matches = tracker.find_speaker(
                embedding=emb.embedding,
                threshold=threshold,
                limit=limit,
            )
            results.append({
                "session_speaker": emb.speaker,
                "matches": matches,
            })

        return {"results": results}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Speaker search failed: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.get("/v1/speakers")
async def list_speakers(limit: int = 100):
    """List all known speakers in the database."""
    tracker = get_speaker_tracker()
    if tracker is None:
        raise HTTPException(
            status_code=503,
            detail="Speaker tracking unavailable. Milvus not connected.",
        )

    speakers = tracker.get_all_speakers(limit=limit)
    return {"speakers": speakers, "total": len(speakers)}


@app.delete("/v1/speakers/{speaker_id}")
async def delete_speaker(speaker_id: str):
    """Delete a speaker and all their embeddings."""
    tracker = get_speaker_tracker()
    if tracker is None:
        raise HTTPException(
            status_code=503,
            detail="Speaker tracking unavailable. Milvus not connected.",
        )

    count = tracker.delete_speaker(speaker_id)
    return {"message": f"Deleted {count} embeddings for speaker {speaker_id}"}


@app.post("/v1/speakers/add")
async def add_speaker_embedding(
    embedding: list[float],
    speaker_id: Optional[str] = None,
    speaker_name: Optional[str] = None,
    recording_id: Optional[str] = None,
    session_speaker: Optional[str] = None,
):
    """
    Manually add a speaker embedding to the database.

    Useful for importing known speakers or correcting identifications.
    """
    tracker = get_speaker_tracker()
    if tracker is None:
        raise HTTPException(
            status_code=503,
            detail="Speaker tracking unavailable. Milvus not connected.",
        )

    if len(embedding) != 256:
        raise HTTPException(
            status_code=400,
            detail=f"Embedding must be 256-dimensional, got {len(embedding)}",
        )

    new_speaker_id = tracker.add_speaker(
        embedding=embedding,
        speaker_id=speaker_id,
        speaker_name=speaker_name,
        recording_id=recording_id,
        session_speaker=session_speaker,
    )

    return {
        "speaker_id": new_speaker_id,
        "message": "Speaker embedding added successfully",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
