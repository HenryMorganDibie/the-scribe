"""In-process sermon ingestion pipeline (runs as a FastAPI BackgroundTask, no Redis)."""
from datetime import datetime
import structlog
from sqlalchemy import select, update

from app.db.session import AsyncSessionLocal
from app.models import Sermon, VoiceProfile, Testimony, DocumentEmbedding
from app.services.ingestion.text_extraction import extract_text
from app.services.ingestion.transcription import transcribe_audio
from app.services.voice.embeddings import EmbeddingService
from app.services.ai.voice_enrichment import extract_dna_from_text, merge_voice_dna
from app.services.ai.testimony_mining import mine_testimonies
from app.services.voice.timeline import snapshot_voice

logger = structlog.get_logger()
_embedding_service = EmbeddingService()


async def process_sermon(sermon_id: str, source_type: str, file_bytes: bytes | None = None,
                         text_value: str | None = None, filename: str | None = None) -> None:
    """Full ingestion: extract -> embed -> enrich voice -> mine testimonies."""
    async with AsyncSessionLocal() as db:
        sermon = (await db.execute(select(Sermon).where(Sermon.id == sermon_id))).scalar_one_or_none()
        if not sermon:
            return
        try:
            # 1. Extract / transcribe text
            sermon.status = "extracting"
            await db.commit()
            if source_type == "audio":
                transcript = await transcribe_audio(file_bytes or b"", filename or "audio.mp3")
            else:
                transcript = extract_text(source_type, file_bytes=file_bytes, text_value=text_value)
            if not transcript or not transcript.strip():
                raise ValueError("No readable text could be extracted or transcribed from this sermon.")
            sermon.transcript = transcript
            sermon.word_count = len(transcript.split())
            sermon.status = "analyzing"
            await db.commit()

            # 2. Embed transcript chunks for RAG (doc_type='sermon')
            chunks = _embedding_service.chunk_text(transcript)
            embeddings = await _embedding_service.embed_batch(chunks)
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                db.add(DocumentEmbedding(
                    user_id=sermon.user_id, doc_type="sermon", source_id=sermon.id,
                    chunk_index=i, content=chunk, embedding=emb,
                ))
            await db.commit()

            # 3. Enrich Voice DNA + snapshot a version
            profile = (await db.execute(
                select(VoiceProfile).where(VoiceProfile.user_id == sermon.user_id)
            )).scalar_one_or_none()
            if profile:
                dna = await extract_dna_from_text(transcript)
                merged = merge_voice_dna(profile, dna)
                sermon.phrases_added = merged["phrases_added"]
                profile.dna_narrative = None  # invalidate cached report narrative
                await db.commit()
                await snapshot_voice(
                    profile=profile, trigger="sermon_ingested", db=db,
                    change_summary=f"Ingested sermon '{sermon.title}': +{merged['phrases_added']} phrases, +{merged['scriptures_added']} scriptures.",
                )

            # 4. Mine testimonies -> suggested
            stories = await mine_testimonies(transcript)
            for s in stories:
                db.add(Testimony(
                    user_id=sermon.user_id, title=s["title"], story=s["story"], themes=s["themes"],
                    status="suggested", source="mined", source_sermon_id=sermon.id,
                ))
            sermon.testimonies_suggested = len(stories)

            sermon.status = "complete"
            sermon.processed_at = datetime.utcnow()
            await db.commit()
        except Exception as e:
            logger.error("sermon_ingestion_failed", sermon_id=sermon_id, error=str(e))
            try:
                await db.rollback()
            except Exception:
                pass
            async with AsyncSessionLocal() as db2:
                await db2.execute(
                    update(Sermon)
                    .where(Sermon.id == sermon_id)
                    .values(status="failed", error_message=str(e)[:2000])
                )
                await db2.commit()
