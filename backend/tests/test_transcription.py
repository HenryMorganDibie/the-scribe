import pytest
from app.services.ingestion.transcription import transcribe_audio, MAX_AUDIO_BYTES


async def test_transcribe_rejects_oversized_audio():
    too_big = b"x" * (MAX_AUDIO_BYTES + 1)
    with pytest.raises(ValueError):
        await transcribe_audio(too_big, "huge.mp3")
