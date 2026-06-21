"""Transcribe sermon audio to text using Groq's Whisper endpoint."""
import asyncio
from app.core.config import settings

# Groq Whisper free tier caps upload size around 25 MB.
MAX_AUDIO_BYTES = 25 * 1024 * 1024

# Without a timeout, a stalled network call to Groq leaves the sermon stuck
# in "extracting" forever with no way for the user to know -- which is
# indistinguishable from the upload itself hanging. 5 minutes is generous
# for a 25MB audio file but guarantees the background task eventually fails
# loudly (caught by process_sermon's except block, which marks the sermon
# "failed" with an error_message) instead of hanging silently.
TRANSCRIPTION_TIMEOUT_SECONDS = 300


async def transcribe_audio(file_bytes: bytes, filename: str) -> str:
    """Return the transcript text for an audio file. Raises ValueError if too large or too slow."""
    if len(file_bytes) > MAX_AUDIO_BYTES:
        raise ValueError(
            f"Audio file is too large ({len(file_bytes) // (1024 * 1024)} MB). "
            f"Limit is {MAX_AUDIO_BYTES // (1024 * 1024)} MB."
        )

    from groq import AsyncGroq
    client = AsyncGroq(api_key=settings.GROQ_API_KEY)

    try:
        result = await asyncio.wait_for(
            client.audio.transcriptions.create(
                file=(filename, file_bytes),
                model="whisper-large-v3",
            ),
            timeout=TRANSCRIPTION_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise ValueError(
            f"Transcription took longer than {TRANSCRIPTION_TIMEOUT_SECONDS // 60} minutes and was "
            "cancelled. Try a shorter audio clip, or try again -- this is usually a transient "
            "issue with the transcription service."
        )

    return (result.text or "").strip()
