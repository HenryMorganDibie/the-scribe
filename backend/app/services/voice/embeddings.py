"""
Embedding service using sentence-transformers (all-MiniLM-L6-v2).
Handles encoding writing samples and testimonies into pgvector-compatible vectors.
"""
import asyncio
from typing import List
from functools import lru_cache

from app.core.config import settings


class EmbeddingService:
    _model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
        return self._model

    async def embed(self, text: str) -> List[float]:
        """Embed a single text string."""
        loop = asyncio.get_event_loop()
        model = self._get_model()
        result = await loop.run_in_executor(
            None, lambda: model.encode(text, normalize_embeddings=True).tolist()
        )
        return result

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts in one pass."""
        loop = asyncio.get_event_loop()
        model = self._get_model()
        result = await loop.run_in_executor(
            None, lambda: model.encode(texts, normalize_embeddings=True).tolist()
        )
        return result

    def chunk_text(self, text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks for embedding."""
        words = text.split()
        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
            i += chunk_size - overlap
        return chunks


embedding_service = EmbeddingService()


async def index_writing_sample(user_id: str, text: str, db) -> int:
    """
    Chunk a writing sample and store embeddings in document_embeddings.
    Returns number of chunks stored.
    """
    from app.models import DocumentEmbedding

    service = EmbeddingService()
    chunks = service.chunk_text(text)
    embeddings = await service.embed_batch(chunks)

    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        doc = DocumentEmbedding(
            user_id=user_id,
            doc_type="writing_sample",
            chunk_index=i,
            content=chunk,
            embedding=emb,
        )
        db.add(doc)

    await db.commit()
    return len(chunks)


async def index_testimony(user_id: str, testimony_id: str, text: str, db) -> int:
    """Index a testimony for vector retrieval."""
    from app.models import DocumentEmbedding

    service = EmbeddingService()
    chunks = service.chunk_text(text, chunk_size=300)
    embeddings = await service.embed_batch(chunks)

    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        doc = DocumentEmbedding(
            user_id=user_id,
            doc_type="testimony",
            source_id=testimony_id,
            chunk_index=i,
            content=chunk,
            embedding=emb,
        )
        db.add(doc)

    await db.commit()
    return len(chunks)
