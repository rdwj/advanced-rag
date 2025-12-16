"""Speaker tracking with Milvus vector database.

This module provides speaker identification across recordings by storing
and searching speaker embeddings in Milvus.
"""

import os
from datetime import datetime
from typing import Optional
from uuid import uuid4

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    MilvusClient,
    connections,
    utility,
)

# Configuration from environment
MILVUS_HOST = os.getenv("MILVUS_HOST", "milvus.milvus.svc.cluster.local")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
COLLECTION_NAME = os.getenv("MILVUS_COLLECTION", "speaker_embeddings")
EMBEDDING_DIM = 256  # pyannote speaker embedding dimension

# Similarity threshold for speaker matching (cosine similarity)
SIMILARITY_THRESHOLD = float(os.getenv("SPEAKER_SIMILARITY_THRESHOLD", "0.85"))


class SpeakerTracker:
    """Track speakers across recordings using Milvus vector search."""

    def __init__(self):
        self.client: Optional[MilvusClient] = None
        self.collection: Optional[Collection] = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to Milvus and ensure collection exists."""
        try:
            # Connect using MilvusClient for simpler API
            uri = f"http://{MILVUS_HOST}:{MILVUS_PORT}"
            self.client = MilvusClient(uri=uri)

            # Also create legacy connection for Collection operations
            connections.connect(
                alias="default",
                host=MILVUS_HOST,
                port=MILVUS_PORT,
            )

            # Ensure collection exists
            self._ensure_collection()
            self._connected = True
            return True

        except Exception as e:
            print(f"Failed to connect to Milvus: {e}")
            self._connected = False
            return False

    def _ensure_collection(self):
        """Create the speaker embeddings collection if it doesn't exist."""
        if utility.has_collection(COLLECTION_NAME):
            self.collection = Collection(COLLECTION_NAME)
            self.collection.load()
            return

        # Define schema
        fields = [
            FieldSchema(
                name="id",
                dtype=DataType.VARCHAR,
                is_primary=True,
                max_length=64,
            ),
            FieldSchema(
                name="speaker_id",
                dtype=DataType.VARCHAR,
                max_length=128,
                description="Persistent speaker identifier",
            ),
            FieldSchema(
                name="speaker_name",
                dtype=DataType.VARCHAR,
                max_length=256,
                description="Human-readable speaker name",
            ),
            FieldSchema(
                name="recording_id",
                dtype=DataType.VARCHAR,
                max_length=256,
                description="Source recording identifier",
            ),
            FieldSchema(
                name="session_speaker",
                dtype=DataType.VARCHAR,
                max_length=64,
                description="Original session speaker label (SPEAKER_00, etc.)",
            ),
            FieldSchema(
                name="embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=EMBEDDING_DIM,
            ),
            FieldSchema(
                name="created_at",
                dtype=DataType.VARCHAR,
                max_length=32,
            ),
            FieldSchema(
                name="metadata",
                dtype=DataType.VARCHAR,
                max_length=2048,
                description="JSON metadata",
            ),
        ]

        schema = CollectionSchema(
            fields=fields,
            description="Speaker embeddings for cross-recording identification",
        )

        self.collection = Collection(
            name=COLLECTION_NAME,
            schema=schema,
        )

        # Create index for vector search
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        }
        self.collection.create_index(
            field_name="embedding",
            index_params=index_params,
        )

        # Load collection for searching
        self.collection.load()
        print(f"Created collection: {COLLECTION_NAME}")

    def find_speaker(
        self,
        embedding: list[float],
        threshold: Optional[float] = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        Search for matching speakers by embedding similarity.

        Args:
            embedding: 256-dim speaker embedding vector
            threshold: Minimum similarity score (default: SIMILARITY_THRESHOLD)
            limit: Maximum number of results

        Returns:
            List of matching speakers with similarity scores
        """
        if not self._connected:
            raise RuntimeError("Not connected to Milvus")

        if threshold is None:
            threshold = SIMILARITY_THRESHOLD

        results = self.client.search(
            collection_name=COLLECTION_NAME,
            data=[embedding],
            limit=limit,
            output_fields=["speaker_id", "speaker_name", "recording_id", "session_speaker", "created_at"],
        )

        matches = []
        for hits in results:
            for hit in hits:
                # Cosine similarity: higher is better, range [0, 1] after normalization
                similarity = 1 - hit["distance"]  # Convert distance to similarity
                if similarity >= threshold:
                    matches.append({
                        "id": hit["id"],
                        "speaker_id": hit["entity"].get("speaker_id"),
                        "speaker_name": hit["entity"].get("speaker_name"),
                        "recording_id": hit["entity"].get("recording_id"),
                        "session_speaker": hit["entity"].get("session_speaker"),
                        "similarity": similarity,
                        "created_at": hit["entity"].get("created_at"),
                    })

        return matches

    def add_speaker(
        self,
        embedding: list[float],
        speaker_id: Optional[str] = None,
        speaker_name: Optional[str] = None,
        recording_id: Optional[str] = None,
        session_speaker: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Add a speaker embedding to the database.

        Args:
            embedding: 256-dim speaker embedding vector
            speaker_id: Persistent speaker ID (generated if not provided)
            speaker_name: Human-readable name (optional)
            recording_id: Source recording identifier
            session_speaker: Original label (SPEAKER_00, etc.)
            metadata: Additional JSON metadata

        Returns:
            The speaker_id (generated or provided)
        """
        if not self._connected:
            raise RuntimeError("Not connected to Milvus")

        import json

        record_id = str(uuid4())
        speaker_id = speaker_id or f"spk_{uuid4().hex[:12]}"

        data = {
            "id": record_id,
            "speaker_id": speaker_id,
            "speaker_name": speaker_name or "",
            "recording_id": recording_id or "",
            "session_speaker": session_speaker or "",
            "embedding": embedding,
            "created_at": datetime.utcnow().isoformat(),
            "metadata": json.dumps(metadata or {}),
        }

        self.client.insert(
            collection_name=COLLECTION_NAME,
            data=[data],
        )

        return speaker_id

    def identify_or_create(
        self,
        embedding: list[float],
        recording_id: Optional[str] = None,
        session_speaker: Optional[str] = None,
        threshold: Optional[float] = None,
    ) -> dict:
        """
        Identify an existing speaker or create a new one.

        This is the main method for speaker tracking workflow:
        1. Search for matching speakers
        2. If match found, return existing speaker_id
        3. If no match, create new speaker and return new speaker_id

        Args:
            embedding: 256-dim speaker embedding vector
            recording_id: Source recording identifier
            session_speaker: Original label (SPEAKER_00, etc.)
            threshold: Minimum similarity for match

        Returns:
            Dict with speaker_id, is_new, and match details
        """
        # Search for existing speaker
        matches = self.find_speaker(embedding, threshold=threshold, limit=1)

        if matches:
            # Found existing speaker
            best_match = matches[0]
            return {
                "speaker_id": best_match["speaker_id"],
                "speaker_name": best_match["speaker_name"],
                "is_new": False,
                "similarity": best_match["similarity"],
                "matched_recording": best_match["recording_id"],
            }
        else:
            # Create new speaker
            speaker_id = self.add_speaker(
                embedding=embedding,
                recording_id=recording_id,
                session_speaker=session_speaker,
            )
            return {
                "speaker_id": speaker_id,
                "speaker_name": None,
                "is_new": True,
                "similarity": None,
                "matched_recording": None,
            }

    def update_speaker_name(self, speaker_id: str, name: str) -> bool:
        """Update the name for a speaker."""
        if not self._connected:
            raise RuntimeError("Not connected to Milvus")

        # Milvus doesn't support direct updates, so we need to:
        # 1. Query all records for this speaker_id
        # 2. Delete them
        # 3. Re-insert with updated name
        # For simplicity, we'll just add a note that this requires app-level handling
        # In practice, speaker names should be stored in a separate metadata store

        # For now, return False to indicate not implemented
        # TODO: Implement with external metadata store or Milvus upsert when available
        return False

    def get_all_speakers(self, limit: int = 1000) -> list[dict]:
        """Get all unique speakers."""
        if not self._connected:
            raise RuntimeError("Not connected to Milvus")

        results = self.client.query(
            collection_name=COLLECTION_NAME,
            filter="",
            output_fields=["speaker_id", "speaker_name", "recording_id", "created_at"],
            limit=limit,
        )

        # Deduplicate by speaker_id
        speakers = {}
        for r in results:
            sid = r["speaker_id"]
            if sid not in speakers:
                speakers[sid] = {
                    "speaker_id": sid,
                    "speaker_name": r.get("speaker_name"),
                    "recordings": [],
                    "first_seen": r.get("created_at"),
                }
            if r.get("recording_id"):
                speakers[sid]["recordings"].append(r["recording_id"])

        return list(speakers.values())

    def delete_speaker(self, speaker_id: str) -> int:
        """Delete all embeddings for a speaker."""
        if not self._connected:
            raise RuntimeError("Not connected to Milvus")

        result = self.client.delete(
            collection_name=COLLECTION_NAME,
            filter=f'speaker_id == "{speaker_id}"',
        )
        return result.get("delete_count", 0)

    def get_collection_stats(self) -> dict:
        """Get collection statistics."""
        if not self._connected:
            return {"connected": False}

        stats = self.collection.num_entities
        return {
            "connected": True,
            "collection": COLLECTION_NAME,
            "total_embeddings": stats,
            "embedding_dim": EMBEDDING_DIM,
            "similarity_threshold": SIMILARITY_THRESHOLD,
        }

    def close(self):
        """Close Milvus connection."""
        if self._connected:
            connections.disconnect("default")
            self._connected = False


# Global tracker instance
_tracker: Optional[SpeakerTracker] = None


def get_tracker() -> SpeakerTracker:
    """Get or create the global speaker tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = SpeakerTracker()
        _tracker.connect()
    return _tracker
