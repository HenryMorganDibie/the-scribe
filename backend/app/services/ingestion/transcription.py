"""Transcribe sermon audio to text using Groq's Whisper endpoint."""
from app.core.config import settings

# Groq Whisper free tier caps upload size around 25 MB.
MAX_AUDIO_BYTES = 25 * 1024 * 1024


async def transcribe_audio(file_bytes: bytes, filename: str) -> str:
    """Return the transcript text for an audio file. Raises ValueError if too large."""
    if len(file_bytes) > MAX_AUDIO_BYTES:
        raise ValueError(
            f"Audio file is too large ({len(file_bytes) // (1024 * 1024)} MB). "
            f"Limit is {MAX_AUDIO_BYTES // (1024 * 1024)} MB."
        )

    from groq import AsyncGroq
    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    result = await client.audio.transcriptions.create(
        file=(filename, file_bytes),
        model="whisper-large-v3",
    )
    return (result.text or "").strip()
