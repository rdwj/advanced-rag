"""FastAPI server for faster-whisper transcription service.

Provides REST API for audio transcription with word-level timestamps
in OpenAI verbose_json format.
"""

import asyncio
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from .models import ErrorResponse, HealthResponse, TranscriptionResponse
from .transcribe import get_model_config, load_model, transcribe

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Thread pool for CPU-bound transcription work
executor = ThreadPoolExecutor(max_workers=2)

# Model configuration from environment
MODEL_SIZE = os.environ.get("MODEL_SIZE", "medium")
DEVICE = os.environ.get("DEVICE", "cuda")
COMPUTE_TYPE = os.environ.get("COMPUTE_TYPE", "float16")
MODEL_PATH = os.environ.get("MODEL_PATH", "/mnt/models")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - load model on startup."""
    logger.info("Starting faster-whisper service...")
    logger.info(
        f"Configuration: model_size={MODEL_SIZE}, device={DEVICE}, "
        f"compute_type={COMPUTE_TYPE}, model_path={MODEL_PATH}"
    )

    # Load model on startup
    try:
        load_model(
            model_size=MODEL_SIZE,
            device=DEVICE,
            compute_type=COMPUTE_TYPE,
            model_path=MODEL_PATH,
        )
        logger.info("Model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise

    yield

    # Cleanup on shutdown
    logger.info("Shutting down faster-whisper service...")
    executor.shutdown(wait=True)


app = FastAPI(
    title="Faster-Whisper Transcription Service",
    description="Audio transcription API with word-level timestamps (verbose_json format)",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint with model status."""
    config = get_model_config()
    return HealthResponse(
        status="healthy" if config["model_loaded"] else "degraded",
        model_loaded=config["model_loaded"],
        model_size=config["model_size"],
        device=config["device"],
        compute_type=config["compute_type"],
    )


@app.get("/ready")
async def readiness_check():
    """Readiness probe - returns 200 if model is loaded."""
    config = get_model_config()
    if not config["model_loaded"]:
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "reason": "model not loaded"},
        )
    return {"status": "ready"}


@app.post(
    "/transcribe",
    response_model=TranscriptionResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Transcription failed"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
    },
)
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    language: str | None = Query(
        None,
        description="Language code (e.g., 'en', 'es'). Auto-detect if not specified.",
    ),
):
    """Transcribe audio file and return verbose_json format response.

    The response includes:
    - Full transcription text
    - Segments with timing information
    - Word-level timestamps within each segment

    Supported audio formats: wav, mp3, m4a, flac, ogg, webm
    """
    config = get_model_config()
    if not config["model_loaded"]:
        raise HTTPException(status_code=503, detail="Model not loaded")

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Check file extension
    valid_extensions = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm", ".mp4"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in valid_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {ext}. Supported: {', '.join(valid_extensions)}",
        )

    logger.info(f"Received transcription request: {file.filename}, language={language}")

    # Save uploaded file to temp location
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail="Failed to process uploaded file")

    # Run transcription in thread pool to avoid blocking
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            lambda: transcribe(tmp_path, language=language),
        )
        logger.info(f"Transcription complete: {len(result.segments)} segments")
        return result
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "faster-whisper",
        "version": "1.0.0",
        "endpoints": {
            "transcribe": "POST /transcribe",
            "health": "GET /health",
            "ready": "GET /ready",
        },
    }
