"""
Embedding service using fastembed (ONNX) with all-MiniLM-L6-v2 (384-dim).
Handles encoding writing samples and testimonies into pgvector-compatible vectors.

fastembed runs the same model as sentence-transformers but via ONNX Runtime
instead of PyTorch, keeping memory and image size small enough for constrained
hosts (e.g. a 512 MB instance). Output vectors are L2-normalized — matching the
previous `normalize_embeddings=True` behavior and the same 384 dimensions — so
existing stored vectors and the pgvector schema are unchanged.
"""
import asyncio
from typing import List

from app.core.config import settings


# Process-wide singleton — the model is loaded once and shared by every
# EmbeddingService instance (the app constructs several), so we never hold more
# than one copy of the model in memory.
_model = None


def _load_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        name = settings.EMBEDDING_MODEL
        if "/" not in name:
            # fastembed expects the fully-qualified Hugging Face id
            name = f"sentence-transformers/{name}"
        _model = TextEmbedding(model_name=name)
    return _model


def _embed_texts(texts: List[str]) -> List[List[float]]:
    """Synchronous fastembed call (run in a thread executor). Returns L2-normalized vectors."""
    import numpy as np

    model = _load_model()
    vectors = []
    for vec in model.embed(list(texts)):
        arr = np.asarray(vec, dtype=float)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        vectors.append(arr.tolist())
    return vectors


class EmbeddingService:
    """Encodes text into pgvector-compatible 384-dim vectors via fastembed (ONNX)."""

    def _get_model(self):
        return _load_model()

    async def embed(self, text: str) -> List[float]:
        """Embed a single text string."""
        result = await self.embed_batch([text])
        return result[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts in one pass, off the event loop."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _embed_texts, texts)

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


async def index_chapter(user_id: str, project_id: str, chapter_id: str, html_content: str, db) -> int:
    """
    Chunk and embed a chapter's content for Manuscript Companion Chat retrieval.

    Re-indexes from scratch on every call (delete existing chunks for this
    chapter, then insert fresh ones) since chapter content changes on every
    save -- unlike writing samples/testimonies, which are written once.
    """
    from sqlalchemy import delete
    from app.models import DocumentEmbedding
    from app.services.export.docx_export import html_to_plain

    plain_text = html_to_plain(html_content or "").strip()

    await db.execute(
        delete(DocumentEmbedding).where(
            DocumentEmbedding.doc_type == "chapter",
            DocumentEmbedding.source_id == chapter_id,
        )
    )

    if not plain_text:
        await db.commit()
        return 0

    service = EmbeddingService()
    chunks = service.chunk_text(plain_text, chunk_size=350, overlap=40)
    embeddings = await service.embed_batch(chunks)

    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        doc = DocumentEmbedding(
            user_id=user_id,
            doc_type="chapter",
            source_id=chapter_id,
            project_id=project_id,
            chunk_index=i,
            content=chunk,
            embedding=emb,
        )
        db.add(doc)

    await db.commit()
    return len(chunks)
