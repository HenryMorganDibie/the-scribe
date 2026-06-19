# Sermon Ingestion, Testimony Mining & Ministry DNA Report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let authors upload sermons (documents + audio), automatically enrich their Voice DNA, mine personal stories into suggested testimonies, and view a Ministry DNA Report.

**Architecture:** A single in-process ingestion pipeline (FastAPI `BackgroundTask`, no Redis) extracts text from a sermon, embeds it for RAG, additively merges new voice signals into the `VoiceProfile` (with a `VoiceVersion` snapshot), and mines suggested testimonies. The Ministry DNA Report computes exact metrics from the DB plus one cached AI narrative. New React pages drive upload, suggestion review, and the report.

**Tech Stack:** FastAPI, async SQLAlchemy 2.0 + asyncpg (Supabase/Postgres + pgvector), Alembic, Groq (LLM + Whisper transcription), sentence-transformers embeddings, React 18 + Vite + TypeScript, recharts.

**Spec:** `docs/superpowers/specs/2026-06-19-sermon-ingestion-testimony-dna-design.md`

## Global Constraints

- Python **3.12**; backend lives in `backend/`, run via its venv (`backend/venv/Scripts/python.exe`). App module is `app.main:app`.
- In this environment the backend runs on **port 8001**, frontend on **5174** (other ports are taken by unrelated projects). Database is the Supabase **session pooler** URL already in `backend/.env`.
- Models live in a single file `app/models/__init__.py`; String UUID primary keys via `gen_uuid` (column default applied at flush — never read `.id` before `await db.flush()`).
- API routers are included with prefix `/api` in `app/main.py`. Every endpoint is auth-guarded with `get_current_user` and user-scoped (`WHERE user_id == current_user.id`).
- LLM access: `from app.services.ai.llm_client import get_llm_client`; `await get_llm_client().complete(messages=[{"role":"user","content":...}], max_tokens=N)` returns `LLMResult(text, usage)`. Groq is the active provider locally.
- Embeddings: `from app.services.voice.embeddings import EmbeddingService` (384-dim vectors).
- Tests: pytest with `asyncio_mode = auto` (async tests need no decorator). Existing tests are **pure unit tests with no DB**. Follow that: TDD the pure functions; verify DB/route/pipeline work with the runnable smoke checks given in the relevant tasks. Run tests from `backend/` with the venv python.
- Frontend uses the `@/` import alias, the shared `api` axios instance (`@/lib/api`), `react-hot-toast`, `lucide-react`, `recharts`, and existing tailwind classes: `card`, `btn-primary`, `input-field`, `font-display`, `text-display-md`, `text-seal`, `text-study-300/400`, `bg-paper`.
- Work happens on branch `feat/sermon-ingestion-testimony-dna`. Commit after every task.

## File Structure

**Backend — create:**
- `backend/alembic/versions/0002_sermon_ingestion.py` — migration
- `backend/app/services/ingestion/__init__.py` — package marker
- `backend/app/services/ingestion/text_extraction.py` — PDF/DOCX/text → text
- `backend/app/services/ingestion/transcription.py` — audio → text (Groq Whisper)
- `backend/app/services/ingestion/pipeline.py` — `process_sermon` orchestrator
- `backend/app/services/ai/voice_enrichment.py` — extract DNA from text + additive merge
- `backend/app/services/ai/testimony_mining.py` — mine stories from text
- `backend/app/services/ai/dna_report.py` — DNA metrics + narrative
- `backend/app/api/routes/sermons.py` — sermon endpoints
- tests: `backend/tests/test_text_extraction.py`, `test_transcription.py`, `test_voice_enrichment.py`, `test_testimony_mining.py`, `test_dna_report.py`

**Backend — modify:**
- `backend/app/models/__init__.py` — add `Sermon`; extend `Testimony`; add `VoiceProfile.dna_narrative`
- `backend/app/main.py` — include `sermons` router
- `backend/app/api/routes/voice.py` — testimony status filter, approve endpoint, dna-report endpoint
- `backend/requirements.txt` — add `pypdf`

**Frontend — create:**
- `frontend/src/pages/Sermons.tsx`
- `frontend/src/pages/MinistryDNA.tsx`

**Frontend — modify:**
- `frontend/src/pages/Testimonies.tsx` — suggestions section
- `frontend/src/App.tsx` — two routes
- `frontend/src/components/layout/AppLayout.tsx` — two nav items

---

## Task 1: Database schema — `Sermon` model, `Testimony` + `VoiceProfile` columns, migration

**Files:**
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0002_sermon_ingestion.py`

**Interfaces:**
- Produces: `Sermon` model (`__tablename__="sermons"`) with fields `id, user_id, title, source_type, original_filename, status, transcript, word_count, phrases_added, testimonies_suggested, error_message, created_at, processed_at`; `Testimony.status`, `Testimony.source`, `Testimony.source_sermon_id`; `VoiceProfile.dna_narrative`.

- [ ] **Step 1: Add the `Sermon` model** to `backend/app/models/__init__.py` (append after the `GenerationLog` class):

```python
# ─────────────────────────────────────────────
# SERMONS (ingested sources)
# ─────────────────────────────────────────────
class Sermon(Base):
    __tablename__ = "sermons"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))

    title: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String)  # pdf|docx|text|audio
    original_filename: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|extracting|analyzing|complete|failed

    transcript: Mapped[Optional[str]] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    phrases_added: Mapped[int] = mapped_column(Integer, default=0)
    testimonies_suggested: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    __table_args__ = (
        Index("ix_sermons_user_status", "user_id", "status"),
    )
```

- [ ] **Step 2: Extend `Testimony`** — in `backend/app/models/__init__.py`, inside the `Testimony` class, add these three columns after the existing `used_in_chapters` line:

```python
    status: Mapped[str] = mapped_column(String, default="approved")  # suggested|approved
    source: Mapped[str] = mapped_column(String, default="manual")    # manual|mined
    source_sermon_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("sermons.id", ondelete="SET NULL"), nullable=True)
```

- [ ] **Step 3: Add `dna_narrative` to `VoiceProfile`** — in the `VoiceProfile` class, add after `voice_summary`:

```python
    dna_narrative: Mapped[Optional[str]] = mapped_column(Text)  # cached Ministry DNA Report narrative
```

- [ ] **Step 4: Create the migration** `backend/alembic/versions/0002_sermon_ingestion.py`:

```python
"""sermon ingestion, testimony mining, dna report

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sermons",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("source_type", sa.String()),
        sa.Column("original_filename", sa.String()),
        sa.Column("status", sa.String(), server_default="pending"),
        sa.Column("transcript", sa.Text()),
        sa.Column("word_count", sa.Integer(), server_default="0"),
        sa.Column("phrases_added", sa.Integer(), server_default="0"),
        sa.Column("testimonies_suggested", sa.Integer(), server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime()),
    )
    op.create_index("ix_sermons_user_status", "sermons", ["user_id", "status"])

    op.add_column("testimonies", sa.Column("status", sa.String(), server_default="approved"))
    op.add_column("testimonies", sa.Column("source", sa.String(), server_default="manual"))
    op.add_column("testimonies", sa.Column("source_sermon_id", sa.String(), sa.ForeignKey("sermons.id", ondelete="SET NULL"), nullable=True))

    op.add_column("voice_profiles", sa.Column("dna_narrative", sa.Text()))


def downgrade() -> None:
    op.drop_column("voice_profiles", "dna_narrative")
    op.drop_column("testimonies", "source_sermon_id")
    op.drop_column("testimonies", "source")
    op.drop_column("testimonies", "status")
    op.drop_index("ix_sermons_user_status", table_name="sermons")
    op.drop_table("sermons")
```

- [ ] **Step 5: Apply the migration**

Run (from `backend/`):
```
.\venv\Scripts\alembic.exe upgrade head
```
Expected: log line `Running upgrade 0001 -> 0002, sermon ingestion, testimony mining, dna report` and no error.

- [ ] **Step 6: Verify models import and the table is registered**

Run (from `backend/`):
```
.\venv\Scripts\python.exe -c "from app.models import Sermon, Testimony, VoiceProfile; print(Sermon.__tablename__, hasattr(Testimony, 'status'), hasattr(VoiceProfile, 'dna_narrative'))"
```
Expected: `sermons True True`

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/__init__.py backend/alembic/versions/0002_sermon_ingestion.py
git commit -m "feat: add Sermon model, testimony mining + dna columns, migration 0002"
```

---

## Task 2: Text extraction service (PDF / DOCX / text)

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/services/ingestion/__init__.py` (empty)
- Create: `backend/app/services/ingestion/text_extraction.py`
- Test: `backend/tests/test_text_extraction.py`

**Interfaces:**
- Produces: `extract_text(source_type: str, *, file_bytes: bytes | None = None, text_value: str | None = None) -> str`. Raises `ValueError` for empty/unreadable input.

- [ ] **Step 1: Add `pypdf` to `backend/requirements.txt`** (append a line after `python-docx==1.1.2`):

```
pypdf==4.3.1
```

Then install it (from `backend/`):
```
.\venv\Scripts\python.exe -m pip install pypdf==4.3.1
```
Expected: `Successfully installed pypdf-4.3.1`

- [ ] **Step 2: Create the empty package marker** `backend/app/services/ingestion/__init__.py` (empty file).

- [ ] **Step 3: Write failing tests** `backend/tests/test_text_extraction.py`:

```python
import io
from docx import Document
from app.services.ingestion.text_extraction import extract_text


def test_extract_text_passthrough_strips():
    assert extract_text("text", text_value="  Hello world  ") == "Hello world"


def test_extract_text_empty_raises():
    import pytest
    with pytest.raises(ValueError):
        extract_text("text", text_value="   ")


def test_extract_docx():
    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph("First line of the sermon.")
    doc.add_paragraph("Second line about grace.")
    doc.save(buf)
    out = extract_text("docx", file_bytes=buf.getvalue())
    assert "First line of the sermon." in out
    assert "grace" in out
```

- [ ] **Step 4: Run tests to verify they fail**

Run (from `backend/`):
```
.\venv\Scripts\python.exe -m pytest tests/test_text_extraction.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.ingestion.text_extraction'`

- [ ] **Step 5: Implement** `backend/app/services/ingestion/text_extraction.py`:

```python
"""Extract plain text from an uploaded sermon source (PDF, DOCX, or pasted text)."""
import io


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()


def _extract_docx(data: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs).strip()


def extract_text(source_type: str, *, file_bytes: bytes | None = None, text_value: str | None = None) -> str:
    """
    Return plain text for the given source type.
    - source_type 'text' uses text_value; 'pdf'/'docx' use file_bytes.
    Raises ValueError if the result is empty/unreadable.
    """
    if source_type == "text":
        result = (text_value or "").strip()
    elif source_type == "pdf":
        result = _extract_pdf(file_bytes or b"")
    elif source_type == "docx":
        result = _extract_docx(file_bytes or b"")
    else:
        raise ValueError(f"Unsupported source_type for text extraction: {source_type!r}")

    if not result:
        raise ValueError("No readable text could be extracted from the source.")
    return result
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_text_extraction.py -v`
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt backend/app/services/ingestion/__init__.py backend/app/services/ingestion/text_extraction.py backend/tests/test_text_extraction.py
git commit -m "feat: text extraction service for pdf/docx/text sermons"
```

---

## Task 3: Audio transcription (Groq Whisper)

**Files:**
- Create: `backend/app/services/ingestion/transcription.py`
- Test: `backend/tests/test_transcription.py`

**Interfaces:**
- Produces: `MAX_AUDIO_BYTES` (int) and `async def transcribe_audio(file_bytes: bytes, filename: str) -> str`. Raises `ValueError` when `len(file_bytes) > MAX_AUDIO_BYTES`.

- [ ] **Step 1: Write the failing test** `backend/tests/test_transcription.py`:

```python
import pytest
from app.services.ingestion.transcription import transcribe_audio, MAX_AUDIO_BYTES


async def test_transcribe_rejects_oversized_audio():
    too_big = b"x" * (MAX_AUDIO_BYTES + 1)
    with pytest.raises(ValueError):
        await transcribe_audio(too_big, "huge.mp3")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_transcription.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.ingestion.transcription'`

- [ ] **Step 3: Implement** `backend/app/services/ingestion/transcription.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_transcription.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ingestion/transcription.py backend/tests/test_transcription.py
git commit -m "feat: groq whisper audio transcription with size guard"
```

---

## Task 4: Voice DNA — extract from text + additive merge

**Files:**
- Create: `backend/app/services/ai/voice_enrichment.py`
- Test: `backend/tests/test_voice_enrichment.py`

**Interfaces:**
- Produces:
  - `_parse_dna_json(raw: str) -> dict` (pure; returns `{}` on failure)
  - `async def extract_dna_from_text(text: str) -> dict` (keys: `signature_phrases`, `cadence_score`, `style_tags`, `voice_summary`, `anchor_scriptures`)
  - `def merge_voice_dna(profile, new_dna: dict) -> dict` (mutates profile additively; returns `{"phrases_added": int, "scriptures_added": int}`)

- [ ] **Step 1: Write failing tests** `backend/tests/test_voice_enrichment.py`:

```python
from app.models import VoiceProfile
from app.services.ai.voice_enrichment import _parse_dna_json, merge_voice_dna


def test_parse_dna_json_strips_fences():
    raw = '```json\n{"signature_phrases": ["set time"], "cadence_score": 0.4}\n```'
    out = _parse_dna_json(raw)
    assert out["signature_phrases"] == ["set time"]
    assert out["cadence_score"] == 0.4


def test_parse_dna_json_bad_returns_empty():
    assert _parse_dna_json("not json at all") == {}


def test_merge_voice_dna_is_additive():
    profile = VoiceProfile(
        user_id="u1",
        signature_phrases=["this is your set time"],
        anchor_scriptures=[{"ref": "Isaiah 61:1", "themes": ["calling"]}],
        style_tags=["direct_address"],
        cadence_score=0.4,
        voice_summary="Old summary.",
    )
    new_dna = {
        "signature_phrases": ["this is your set time", "let that sink in"],
        "anchor_scriptures": [{"ref": "Isaiah 61:1"}, {"ref": "Joel 2:28", "themes": ["prophecy"]}],
        "style_tags": ["rhetorical_questions"],
        "cadence_score": 0.6,
        "voice_summary": "New summary.",
    }
    result = merge_voice_dna(profile, new_dna)

    assert profile.signature_phrases == ["this is your set time", "let that sink in"]
    refs = {s["ref"] for s in profile.anchor_scriptures}
    assert refs == {"Isaiah 61:1", "Joel 2:28"}
    assert set(profile.style_tags) == {"direct_address", "rhetorical_questions"}
    assert profile.cadence_score == 0.5  # average of 0.4 and 0.6
    assert profile.voice_summary == "New summary."
    assert result == {"phrases_added": 1, "scriptures_added": 1}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_voice_enrichment.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.ai.voice_enrichment'`

- [ ] **Step 3: Implement** `backend/app/services/ai/voice_enrichment.py`:

```python
"""Extract voice DNA from arbitrary text and additively merge it into a VoiceProfile."""
import json
from app.services.ai.llm_client import get_llm_client


def _parse_dna_json(raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    try:
        out = json.loads(text)
        return out if isinstance(out, dict) else {}
    except Exception:
        return {}


async def extract_dna_from_text(text: str) -> dict:
    """Run the voice-DNA extraction prompt over a transcript and return structured DNA."""
    prompt = f"""Analyze this writing/sermon transcript from a Christian author and extract their voice DNA.

TRANSCRIPT:
{text[:4000]}

Return a JSON object with exactly these keys:
{{
  "signature_phrases": ["8-12 distinctive recurring phrases or sentence openers"],
  "cadence_score": 0.0,
  "style_tags": ["6-8 style characteristics e.g. rhetorical_questions, direct_address, repetition_for_emphasis"],
  "voice_summary": "300-word description a ghostwriter could use as a compass",
  "anchor_scriptures": [{{"ref": "Isaiah 61:1", "themes": ["calling"]}}]
}}

Return ONLY valid JSON. No markdown, no explanation."""
    result = await get_llm_client().complete(messages=[{"role": "user", "content": prompt}], max_tokens=2000)
    return _parse_dna_json(result.text)


def merge_voice_dna(profile, new_dna: dict) -> dict:
    """
    Additively merge new DNA into the profile (never removes existing signals).
    Mutates `profile` in place. Returns counts of newly added phrases/scriptures.
    """
    # Phrases — union, preserve existing order
    existing_phrases = list(profile.signature_phrases or [])
    added_phrases = [p for p in (new_dna.get("signature_phrases") or []) if p not in existing_phrases]
    profile.signature_phrases = existing_phrases + added_phrases

    # Anchor scriptures — merge by ref
    existing_scriptures = list(profile.anchor_scriptures or [])
    existing_refs = {s["ref"] for s in existing_scriptures if isinstance(s, dict) and "ref" in s}
    added_scriptures = [
        s for s in (new_dna.get("anchor_scriptures") or [])
        if isinstance(s, dict) and s.get("ref") and s["ref"] not in existing_refs
    ]
    profile.anchor_scriptures = existing_scriptures + added_scriptures

    # Style tags — union
    existing_tags = list(profile.style_tags or [])
    profile.style_tags = existing_tags + [t for t in (new_dna.get("style_tags") or []) if t not in existing_tags]

    # Cadence — average with new if present
    new_cadence = new_dna.get("cadence_score")
    if isinstance(new_cadence, (int, float)):
        profile.cadence_score = round(((profile.cadence_score or new_cadence) + new_cadence) / 2, 3)

    # Voice summary — replace with the freshly generated one if present
    if new_dna.get("voice_summary"):
        profile.voice_summary = new_dna["voice_summary"]

    return {"phrases_added": len(added_phrases), "scriptures_added": len(added_scriptures)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_voice_enrichment.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/voice_enrichment.py backend/tests/test_voice_enrichment.py
git commit -m "feat: extract voice DNA from text + additive profile merge"
```

---

## Task 5: Testimony mining

**Files:**
- Create: `backend/app/services/ai/testimony_mining.py`
- Test: `backend/tests/test_testimony_mining.py`

**Interfaces:**
- Produces:
  - `_parse_testimonies(raw: str) -> list[dict]` (pure; returns `[]` on failure; each dict has `title`, `story`, `themes`)
  - `async def mine_testimonies(transcript: str) -> list[dict]`

- [ ] **Step 1: Write failing tests** `backend/tests/test_testimony_mining.py`:

```python
from app.services.ai.testimony_mining import _parse_testimonies


def test_parse_testimonies_valid_array():
    raw = '[{"title": "Healed at the altar", "story": "One night...", "themes": ["healing"]}]'
    out = _parse_testimonies(raw)
    assert len(out) == 1
    assert out[0]["title"] == "Healed at the altar"
    assert out[0]["themes"] == ["healing"]


def test_parse_testimonies_strips_fences():
    raw = '```json\n[{"title": "T", "story": "S", "themes": []}]\n```'
    assert _parse_testimonies(raw)[0]["title"] == "T"


def test_parse_testimonies_bad_returns_empty():
    assert _parse_testimonies("nonsense") == []


def test_parse_testimonies_drops_incomplete_entries():
    raw = '[{"title": "ok", "story": "s", "themes": []}, {"title": "no story"}]'
    out = _parse_testimonies(raw)
    assert len(out) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_testimony_mining.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.ai.testimony_mining'`

- [ ] **Step 3: Implement** `backend/app/services/ai/testimony_mining.py`:

```python
"""Mine personal stories / testimonies from a sermon transcript."""
import json
from app.services.ai.llm_client import get_llm_client


def _parse_testimonies(raw: str) -> list[dict]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    try:
        data = json.loads(text)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    cleaned = []
    for item in data:
        if isinstance(item, dict) and item.get("title") and item.get("story"):
            cleaned.append({
                "title": str(item["title"]),
                "story": str(item["story"]),
                "themes": item.get("themes") if isinstance(item.get("themes"), list) else [],
            })
    return cleaned


async def mine_testimonies(transcript: str) -> list[dict]:
    """Extract candidate personal stories from a transcript. Returns [] on failure."""
    prompt = f"""Read this sermon transcript and identify personal stories the author tells —
healing testimonies, ministry experiences, leadership lessons, prophetic encounters, or personal struggles.

TRANSCRIPT:
{transcript[:5000]}

Return a JSON array (max 5). Each item:
{{"title": "short title", "story": "the story retold in 2-4 sentences", "themes": ["theme1", "theme2"]}}

Only include genuine personal/ministry stories, not general teaching. If none, return [].
Return ONLY valid JSON. No markdown, no explanation."""
    result = await get_llm_client().complete(messages=[{"role": "user", "content": prompt}], max_tokens=1200)
    return _parse_testimonies(result.text)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_testimony_mining.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/testimony_mining.py backend/tests/test_testimony_mining.py
git commit -m "feat: testimony mining from sermon transcripts"
```

---

## Task 6: Ministry DNA Report — metrics + narrative

**Files:**
- Create: `backend/app/services/ai/dna_report.py`
- Test: `backend/tests/test_dna_report.py`

**Interfaces:**
- Produces:
  - `def compute_dna_metrics(profile, sermons: list, versions: list) -> dict` (pure). Returns keys: `top_scriptures` (list of `{"ref","count"}`), `top_phrases` (list of `{"phrase","count"}`), `top_themes` (list of `{"theme","count"}`), `ministry_focus` (str), `timeline` (list of `{"version","cadence_score","phrase_count","scripture_count"}`).
  - `async def generate_dna_narrative(metrics: dict) -> str`

- [ ] **Step 1: Write failing tests** `backend/tests/test_dna_report.py`:

```python
from types import SimpleNamespace
from app.models import VoiceProfile
from app.services.ai.dna_report import compute_dna_metrics


def _sermon(transcript):
    return SimpleNamespace(transcript=transcript)


def test_compute_dna_metrics_basic():
    profile = VoiceProfile(
        user_id="u1",
        theological_lens="Prophetic",
        signature_phrases=["set time", "let that sink in"],
        anchor_scriptures=[
            {"ref": "Isaiah 61:1", "themes": ["calling", "healing"]},
            {"ref": "Joel 2:28", "themes": ["prophecy", "calling"]},
        ],
    )
    sermons = [
        _sermon("This is your set time. Isaiah 61:1 says... set time again."),
        _sermon("Joel 2:28 and Isaiah 61:1. Let that sink in."),
    ]
    versions = [
        SimpleNamespace(version_number=1, cadence_score=0.4, phrase_count=2, scripture_count=1),
        SimpleNamespace(version_number=2, cadence_score=0.5, phrase_count=4, scripture_count=2),
    ]
    m = compute_dna_metrics(profile, sermons, versions)

    # "calling" appears in both scriptures -> top theme
    assert m["top_themes"][0]["theme"] == "calling"
    assert m["top_themes"][0]["count"] == 2
    # "set time" appears 2x across transcripts, more than "let that sink in" (1x)
    assert m["top_phrases"][0]["phrase"] == "set time"
    assert m["top_phrases"][0]["count"] == 2
    # Isaiah 61:1 referenced twice
    refs = {s["ref"]: s["count"] for s in m["top_scriptures"]}
    assert refs["Isaiah 61:1"] == 2
    assert "Prophetic" in m["ministry_focus"]
    assert m["timeline"][0]["version"] == 1 and m["timeline"][-1]["version"] == 2


def test_compute_dna_metrics_empty_profile():
    profile = VoiceProfile(user_id="u1")
    m = compute_dna_metrics(profile, [], [])
    assert m["top_scriptures"] == []
    assert m["top_phrases"] == []
    assert m["top_themes"] == []
    assert m["timeline"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_dna_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.ai.dna_report'`

- [ ] **Step 3: Implement** `backend/app/services/ai/dna_report.py`:

```python
"""Ministry DNA Report: exact metrics from the DB + a short cached AI narrative."""
from collections import Counter
from app.services.ai.llm_client import get_llm_client


def compute_dna_metrics(profile, sermons: list, versions: list) -> dict:
    """Compute deterministic metrics from the profile, sermons, and voice versions."""
    corpus = "\n".join((s.transcript or "") for s in sermons).lower()

    anchors = profile.anchor_scriptures or []
    phrases = profile.signature_phrases or []

    # Most-quoted scriptures: base 1 + mentions of the ref string across the corpus
    scripture_counts = []
    for s in anchors:
        if isinstance(s, dict) and s.get("ref"):
            ref = s["ref"]
            count = 1 + corpus.count(ref.lower())
            scripture_counts.append({"ref": ref, "count": count})
    scripture_counts.sort(key=lambda x: x["count"], reverse=True)

    # Most-used phrases: occurrences across the corpus
    phrase_counts = [
        {"phrase": p, "count": corpus.count(p.lower())}
        for p in phrases
    ]
    phrase_counts = [pc for pc in phrase_counts if pc["count"] > 0]
    phrase_counts.sort(key=lambda x: x["count"], reverse=True)

    # Recurring themes: tally across anchor scripture themes
    theme_counter = Counter()
    for s in anchors:
        if isinstance(s, dict):
            for t in (s.get("themes") or []):
                theme_counter[t] += 1
    top_themes = [{"theme": t, "count": c} for t, c in theme_counter.most_common()]

    # Dominant ministry focus
    lens = profile.theological_lens or "Spirit-filled"
    focus = lens
    if top_themes:
        focus = f"{lens} ministry centered on {top_themes[0]['theme']}"

    # Voice change over time
    timeline = [
        {
            "version": v.version_number,
            "cadence_score": v.cadence_score,
            "phrase_count": v.phrase_count,
            "scripture_count": v.scripture_count,
        }
        for v in sorted(versions, key=lambda x: x.version_number)
    ]

    return {
        "top_scriptures": scripture_counts[:10],
        "top_phrases": phrase_counts[:10],
        "top_themes": top_themes[:10],
        "ministry_focus": focus,
        "timeline": timeline,
    }


async def generate_dna_narrative(metrics: dict) -> str:
    """Write a short narrative summary of the computed metrics."""
    prompt = f"""Write a warm, 120-150 word narrative summarizing this Christian author's ministry DNA.
Use these computed facts; do not invent numbers.

Dominant focus: {metrics.get('ministry_focus')}
Top themes: {', '.join(t['theme'] for t in metrics.get('top_themes', [])[:5]) or 'none yet'}
Most-quoted scriptures: {', '.join(s['ref'] for s in metrics.get('top_scriptures', [])[:5]) or 'none yet'}
Signature phrases: {', '.join(p['phrase'] for p in metrics.get('top_phrases', [])[:5]) or 'none yet'}

Address the author as "you". No preamble — just the paragraph."""
    result = await get_llm_client().complete(messages=[{"role": "user", "content": prompt}], max_tokens=300)
    return result.text.strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\venv\Scripts\python.exe -m pytest tests/test_dna_report.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/dna_report.py backend/tests/test_dna_report.py
git commit -m "feat: ministry DNA report metrics + narrative"
```

---

## Task 7: Ingestion pipeline + sermon routes

**Files:**
- Create: `backend/app/services/ingestion/pipeline.py`
- Create: `backend/app/api/routes/sermons.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `extract_text`, `transcribe_audio`, `EmbeddingService`, `extract_dna_from_text`, `merge_voice_dna`, `snapshot_voice`, `mine_testimonies`.
- Produces: `async def process_sermon(sermon_id, source_type, file_bytes=None, text_value=None, filename=None)`; routes `POST /api/sermons`, `GET /api/sermons`, `GET /api/sermons/{id}`, `DELETE /api/sermons/{id}`.

- [ ] **Step 1: Implement the pipeline** `backend/app/services/ingestion/pipeline.py`:

```python
"""In-process sermon ingestion pipeline (runs as a FastAPI BackgroundTask, no Redis)."""
from datetime import datetime
import structlog
from sqlalchemy import select

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
            await db.rollback()
            sermon.status = "failed"
            sermon.error_message = str(e)
            await db.commit()
```

- [ ] **Step 2: Implement the routes** `backend/app/api/routes/sermons.py`:

```python
"""Sermon upload & ingestion routes. Upload accepts a file OR pasted text (multipart)."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.db.session import get_db
from app.models import User, Sermon, DocumentEmbedding
from app.core.security import get_current_user
from app.services.ingestion.pipeline import process_sermon

router = APIRouter(prefix="/sermons", tags=["sermons"])

_EXT_TO_TYPE = {"pdf": "pdf", "docx": "docx"}


def _serialize(s: Sermon) -> dict:
    return {
        "id": s.id, "title": s.title, "source_type": s.source_type, "status": s.status,
        "word_count": s.word_count, "phrases_added": s.phrases_added,
        "testimonies_suggested": s.testimonies_suggested, "error_message": s.error_message,
        "created_at": s.created_at, "processed_at": s.processed_at,
    }


@router.post("", status_code=202)
async def upload_sermon(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not text and not file:
        raise HTTPException(status_code=400, detail="Provide either pasted text or a file.")

    file_bytes = None
    filename = None
    if file:
        filename = file.filename or ""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in _EXT_TO_TYPE:
            source_type = _EXT_TO_TYPE[ext]
        elif ext in ("mp3", "m4a", "wav", "mpga", "mp4", "webm"):
            source_type = "audio"
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: .{ext}")
        file_bytes = await file.read()
    else:
        source_type = "text"

    sermon = Sermon(
        user_id=current_user.id, title=title, source_type=source_type,
        original_filename=filename, status="pending",
    )
    db.add(sermon)
    await db.commit()
    await db.refresh(sermon)

    background_tasks.add_task(
        process_sermon, sermon.id, source_type,
        file_bytes=file_bytes, text_value=text, filename=filename,
    )
    return {"id": sermon.id, "status": sermon.status}


@router.get("")
async def list_sermons(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Sermon).where(Sermon.user_id == current_user.id).order_by(Sermon.created_at.desc())
    )
    return [_serialize(s) for s in result.scalars().all()]


@router.get("/{sermon_id}")
async def get_sermon(sermon_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Sermon).where(Sermon.id == sermon_id, Sermon.user_id == current_user.id)
    )
    sermon = result.scalar_one_or_none()
    if not sermon:
        raise HTTPException(status_code=404, detail="Sermon not found")
    return _serialize(sermon)


@router.delete("/{sermon_id}", status_code=204)
async def delete_sermon(sermon_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Sermon).where(Sermon.id == sermon_id, Sermon.user_id == current_user.id)
    )
    sermon = result.scalar_one_or_none()
    if not sermon:
        raise HTTPException(status_code=404, detail="Sermon not found")
    # Remove this sermon's embeddings too
    await db.execute(
        DocumentEmbedding.__table__.delete().where(
            (DocumentEmbedding.doc_type == "sermon") & (DocumentEmbedding.source_id == sermon_id)
        )
    )
    await db.delete(sermon)
    await db.commit()
```

- [ ] **Step 3: Register the router** in `backend/app/main.py`. Change the routes import line:

```python
from app.api.routes import auth, onboarding, projects, voice, generate, export, sermons
```

and add, after `app.include_router(export.router, prefix="/api")`:

```python
app.include_router(sermons.router, prefix="/api")
```

- [ ] **Step 4: Verify the app imports**

Run (from `backend/`):
```
.\venv\Scripts\python.exe -c "import app.main; print('ok')"
```
Expected: `ok`

- [ ] **Step 5: Smoke-test the pipeline end-to-end** (requires the backend running on 8001). Start the server in one terminal:
```
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```
Then in PowerShell run this script (signs up a fresh user, uploads a text sermon, polls to completion):
```powershell
$email = "sermontest+$((Get-Random)).user@example.com"
$body = @{ email=$email; password="Test1234!"; full_name="Sermon Tester" } | ConvertTo-Json
$signup = Invoke-RestMethod "http://127.0.0.1:8001/api/auth/signup" -Method Post -Body $body -ContentType "application/json"
$h = @{ Authorization = "Bearer $($signup.access_token)" }
# complete onboarding minimally so a voice profile exists
$null = Invoke-RestMethod "http://127.0.0.1:8001/api/onboarding/complete" -Method Post -Headers $h -ContentType "application/json" -Body (@{ data=@{ theological_lens="Prophetic"; writing_samples=@("I preach about set time and calling.") } } | ConvertTo-Json -Depth 5)
$form = @{ title="Test Sermon"; text="This is your set time. One night at the altar, God healed my mother. Isaiah 61:1 declares freedom. Let that sink in." }
$up = Invoke-RestMethod "http://127.0.0.1:8001/api/sermons" -Method Post -Headers $h -Form $form
for ($i=0; $i -lt 30; $i++) {
  $s = Invoke-RestMethod "http://127.0.0.1:8001/api/sermons/$($up.id)" -Headers $h
  if ($s.status -in @("complete","failed")) { break }
  Start-Sleep -Seconds 2
}
Write-Output "status=$($s.status) phrases_added=$($s.phrases_added) testimonies_suggested=$($s.testimonies_suggested) error=$($s.error_message)"
$sug = Invoke-RestMethod "http://127.0.0.1:8001/api/testimonies?status=suggested" -Headers $h
Write-Output "suggested testimonies: $($sug.Count)"
```
Expected: `status=complete` with `phrases_added` ≥ 0 and a transcript processed. (Note: the `?status=suggested` filter line will only succeed after Task 8; until then it may 200 with all testimonies — that's fine for this task's check.)

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ingestion/pipeline.py backend/app/api/routes/sermons.py backend/app/main.py
git commit -m "feat: in-process sermon ingestion pipeline + sermon routes"
```

---

## Task 8: Testimony suggestions filter, approve endpoint, DNA report route

**Files:**
- Modify: `backend/app/api/routes/voice.py`

**Interfaces:**
- Consumes: `compute_dna_metrics`, `generate_dna_narrative`, `get_timeline`, `index_testimony_task`.
- Produces: `GET /api/testimonies?status=...`, `POST /api/testimonies/{id}/approve`, `GET /api/voice/dna-report`.

- [ ] **Step 1: Add a `status` filter to `list_testimonies`** in `backend/app/api/routes/voice.py`. Replace the existing `list_testimonies` function with:

```python
@router.get("/testimonies")
async def list_testimonies(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Testimony).where(Testimony.user_id == current_user.id)
    if status:
        query = query.where(Testimony.status == status)
    query = query.order_by(Testimony.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()
```

- [ ] **Step 2: Add the approve endpoint** in `backend/app/api/routes/voice.py`, after `update_testimony`:

```python
@router.post("/testimonies/{testimony_id}/approve")
async def approve_testimony(testimony_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Testimony).where(Testimony.id == testimony_id, Testimony.user_id == current_user.id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Testimony not found")
    t.status = "approved"
    await db.commit()
    # Index for retrieval now that it's part of the vault
    from app.workers.tasks import index_testimony_task
    fire_background_job(index_testimony_task, current_user.id, t.id, t.story, job_name="index_testimony")
    return {"approved": True, "id": t.id}
```

- [ ] **Step 3: Add the DNA report endpoint** in `backend/app/api/routes/voice.py`, in the "Voice Profile" section (after `update_voice_profile`):

```python
@router.get("/voice/dna-report")
async def dna_report(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models import Sermon
    from app.services.ai.dna_report import compute_dna_metrics, generate_dna_narrative

    profile = (await db.execute(select(VoiceProfile).where(VoiceProfile.user_id == current_user.id))).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Voice profile not found")

    sermons = (await db.execute(
        select(Sermon).where(Sermon.user_id == current_user.id, Sermon.status == "complete")
    )).scalars().all()
    versions = await get_timeline(current_user.id, db)

    metrics = compute_dna_metrics(profile, sermons, versions)

    if not profile.dna_narrative:
        narrative = await generate_dna_narrative(metrics)
        profile.dna_narrative = narrative
        await db.commit()
    else:
        narrative = profile.dna_narrative

    return {"metrics": metrics, "narrative": narrative, "sermon_count": len(sermons)}
```

- [ ] **Step 4: Verify the app imports**

Run (from `backend/`): `.\venv\Scripts\python.exe -c "import app.main; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Smoke-test** (backend running on 8001). Reusing a token from a user who has ingested a sermon (see Task 7 script), run:
```powershell
$report = Invoke-RestMethod "http://127.0.0.1:8001/api/voice/dna-report" -Headers $h
Write-Output "focus: $($report.metrics.ministry_focus)"
Write-Output "narrative chars: $($report.narrative.Length)"
# approve the first suggested testimony
$sug = Invoke-RestMethod "http://127.0.0.1:8001/api/testimonies?status=suggested" -Headers $h
if ($sug.Count -gt 0) {
  $ok = Invoke-RestMethod "http://127.0.0.1:8001/api/testimonies/$($sug[0].id)/approve" -Method Post -Headers $h
  Write-Output "approved: $($ok.approved)"
}
```
Expected: a `ministry_focus` string, a non-empty narrative, and `approved: True` if suggestions exist.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/voice.py
git commit -m "feat: testimony suggestions filter, approve endpoint, dna-report route"
```

---

## Task 9: Frontend — Sermons page (upload + status polling)

**Files:**
- Create: `frontend/src/pages/Sermons.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/layout/AppLayout.tsx`

**Interfaces:**
- Consumes: backend `POST /api/sermons` (multipart), `GET /api/sermons`, `GET /api/sermons/{id}`.

- [ ] **Step 1: Create** `frontend/src/pages/Sermons.tsx`:

```tsx
import { useEffect, useRef, useState } from 'react'
import { Upload, FileText, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '@/lib/api'

interface Sermon {
  id: string
  title: string
  source_type: string
  status: string
  phrases_added: number
  testimonies_suggested: number
  error_message?: string | null
}

const ACTIVE = ['pending', 'extracting', 'analyzing']

export default function Sermons() {
  const [sermons, setSermons] = useState<Sermon[]>([])
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = () => api.get('/sermons').then((r) => setSermons(r.data))

  useEffect(() => { load() }, [])

  // Poll while any sermon is still processing
  useEffect(() => {
    if (!sermons.some((s) => ACTIVE.includes(s.status))) return
    const t = setInterval(load, 2500)
    return () => clearInterval(t)
  }, [sermons])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const file = fileRef.current?.files?.[0]
    if (!title.trim()) return toast.error('Give the sermon a title')
    if (!file && !text.trim()) return toast.error('Upload a file or paste text')
    setSubmitting(true)
    try {
      const form = new FormData()
      form.append('title', title)
      if (file) form.append('file', file)
      else form.append('text', text)
      await api.post('/sermons', form)
      toast.success('Sermon uploaded — processing in the background')
      setTitle(''); setText('')
      if (fileRef.current) fileRef.current.value = ''
      load()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Upload failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <Upload size={24} className="text-seal" />
        <h1 className="font-display text-display-md font-semibold">Sermons</h1>
      </div>
      <p className="text-study-300 mb-6">
        Upload sermons (PDF, DOCX, audio) or paste a transcript. The Scribe transcribes, learns your voice,
        and mines personal stories into suggested testimonies.
      </p>

      <form onSubmit={submit} className="card p-6 mb-8 space-y-4">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="input-field w-full"
          placeholder="Sermon title"
        />
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="input-field w-full h-32 resize-none"
          placeholder="Paste a transcript here, or choose a file below..."
        />
        <input ref={fileRef} type="file" accept=".pdf,.docx,.mp3,.m4a,.wav,.webm,.mp4" className="block text-sm text-study-400" />
        <button type="submit" disabled={submitting} className="btn-primary flex items-center gap-2">
          {submitting ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
          Upload sermon
        </button>
      </form>

      <div className="space-y-3">
        {sermons.map((s) => (
          <div key={s.id} className="card p-5 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <FileText size={18} className="text-study-300" />
              <div>
                <h3 className="font-display font-semibold">{s.title}</h3>
                <p className="text-xs text-study-300 uppercase">{s.source_type}</p>
              </div>
            </div>
            <div className="text-right text-sm">
              {ACTIVE.includes(s.status) ? (
                <span className="flex items-center gap-1.5 text-study-300">
                  <Loader2 size={14} className="animate-spin" /> {s.status}…
                </span>
              ) : s.status === 'failed' ? (
                <span className="text-red-400" title={s.error_message || ''}>Failed</span>
              ) : (
                <span className="text-green-600">
                  +{s.phrases_added} phrases · {s.testimonies_suggested} stories
                </span>
              )}
            </div>
          </div>
        ))}
        {sermons.length === 0 && <p className="text-study-300 text-center py-12">No sermons yet.</p>}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add the route** in `frontend/src/App.tsx`. Add the import near the other page imports:

```tsx
import Sermons from '@/pages/Sermons'
```

and add this route inside the `AppLayout` nested routes block (after the `/testimonies` route):

```tsx
          <Route path="/sermons" element={<Sermons />} />
```

- [ ] **Step 3: Add the nav item** in `frontend/src/components/layout/AppLayout.tsx`. Add to the `navItems` array (after the Testimonies entry):

```tsx
  { to: '/sermons', label: 'Sermons' },
```

- [ ] **Step 4: Type-check the frontend**

Run (from `frontend/`):
```
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Sermons.tsx frontend/src/App.tsx frontend/src/components/layout/AppLayout.tsx
git commit -m "feat: sermons upload page with status polling + nav/route"
```

---

## Task 10: Frontend — Testimony suggestions review section

**Files:**
- Modify: `frontend/src/pages/Testimonies.tsx`

**Interfaces:**
- Consumes: `GET /api/testimonies?status=suggested`, `POST /api/testimonies/{id}/approve`, `DELETE /api/testimonies/{id}`.

- [ ] **Step 1: Load suggestions and add approve/dismiss handlers.** In `frontend/src/pages/Testimonies.tsx`, extend the `Testimony` interface with `status` and add suggestions state + handlers. Replace the `load` function and add the new pieces:

```tsx
  const [suggestions, setSuggestions] = useState<Testimony[]>([])

  const load = () => {
    api.get('/testimonies', { params: { status: 'approved' } }).then((r) => setTestimonies(r.data)).finally(() => setLoading(false))
    api.get('/testimonies', { params: { status: 'suggested' } }).then((r) => setSuggestions(r.data))
  }

  const approveSuggestion = async (id: string) => {
    try {
      await api.post(`/testimonies/${id}/approve`)
      toast.success('Added to your vault')
      load()
    } catch {
      toast.error('Failed to approve')
    }
  }

  const dismissSuggestion = async (id: string) => {
    try {
      await api.delete(`/testimonies/${id}`)
      setSuggestions((prev) => prev.filter((t) => t.id !== id))
    } catch {
      toast.error('Failed to dismiss')
    }
  }
```

(Also add `status: string` to the `Testimony` interface.)

- [ ] **Step 2: Render the suggestions section.** In the same file, add this block just above the existing list rendering (right after the closing `)}` of the `showForm` form, before the `{loading ? ...}` block):

```tsx
      {suggestions.length > 0 && (
        <div className="mb-8">
          <h2 className="font-display text-lg font-semibold mb-3">Suggested from your sermons</h2>
          <div className="space-y-3">
            {suggestions.map((t) => (
              <div key={t.id} className="card p-5 border-l-4 border-seal">
                <h3 className="font-display font-semibold mb-1">{t.title}</h3>
                <p className="text-study-400 text-sm leading-relaxed line-clamp-3 mb-3">{t.story}</p>
                <div className="flex gap-2">
                  <button onClick={() => approveSuggestion(t.id)} className="btn-primary text-sm px-3 py-1.5">Approve</button>
                  <button onClick={() => dismissSuggestion(t.id)} className="text-sm px-3 py-1.5 text-study-400 hover:text-red-400">Dismiss</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
```

- [ ] **Step 2b: Import `useState` is already present**; no new imports needed (uses existing `api`, `toast`).

- [ ] **Step 3: Type-check the frontend**

Run (from `frontend/`): `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Testimonies.tsx
git commit -m "feat: suggested-testimony review section (approve/dismiss)"
```

---

## Task 11: Frontend — Ministry DNA page

**Files:**
- Create: `frontend/src/pages/MinistryDNA.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/layout/AppLayout.tsx`

**Interfaces:**
- Consumes: `GET /api/voice/dna-report` → `{ metrics: { top_scriptures, top_phrases, top_themes, ministry_focus, timeline }, narrative, sermon_count }`.

- [ ] **Step 1: Create** `frontend/src/pages/MinistryDNA.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { Fingerprint } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { api } from '@/lib/api'

interface DnaReport {
  metrics: {
    top_scriptures: { ref: string; count: number }[]
    top_phrases: { phrase: string; count: number }[]
    top_themes: { theme: string; count: number }[]
    ministry_focus: string
    timeline: { version: number; cadence_score: number | null; phrase_count: number | null; scripture_count: number | null }[]
  }
  narrative: string
  sermon_count: number
}

function RankedList({ title, items }: { title: string; items: { label: string; count: number }[] }) {
  return (
    <div className="card p-5">
      <h3 className="font-display font-semibold mb-3">{title}</h3>
      {items.length === 0 ? (
        <p className="text-study-300 text-sm">Nothing yet.</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((it) => (
            <li key={it.label} className="flex justify-between text-sm">
              <span className="text-study-400">{it.label}</span>
              <span className="text-seal font-medium">{it.count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function MinistryDNA() {
  const [report, setReport] = useState<DnaReport | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/voice/dna-report').then((r) => setReport(r.data)).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-study-300">Loading…</div>
  if (!report) return <div className="p-8 text-study-300">No report available yet.</div>

  const { metrics, narrative, sermon_count } = report

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Fingerprint size={24} className="text-seal" />
        <h1 className="font-display text-display-md font-semibold">Ministry DNA</h1>
      </div>

      <div className="card p-6 mb-6">
        <p className="text-sm text-study-300 mb-1">Based on {sermon_count} ingested sermon(s)</p>
        <p className="font-display text-lg mb-3">{metrics.ministry_focus}</p>
        <p className="text-study-400 leading-relaxed">{narrative}</p>
      </div>

      <div className="grid md:grid-cols-3 gap-4 mb-6">
        <RankedList title="Most-quoted scriptures" items={metrics.top_scriptures.map((s) => ({ label: s.ref, count: s.count }))} />
        <RankedList title="Most-used phrases" items={metrics.top_phrases.map((p) => ({ label: p.phrase, count: p.count }))} />
        <RankedList title="Recurring themes" items={metrics.top_themes.map((t) => ({ label: t.theme, count: t.count }))} />
      </div>

      {metrics.timeline.length > 1 && (
        <div className="card p-5">
          <h3 className="font-display font-semibold mb-3">Voice over time</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={metrics.timeline}>
              <XAxis dataKey="version" stroke="#8a8175" fontSize={12} />
              <YAxis stroke="#8a8175" fontSize={12} />
              <Tooltip />
              <Line type="monotone" dataKey="phrase_count" stroke="#9a3412" strokeWidth={2} dot />
              <Line type="monotone" dataKey="scripture_count" stroke="#1E1E1E" strokeWidth={2} dot />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Add the route** in `frontend/src/App.tsx`. Add the import:

```tsx
import MinistryDNA from '@/pages/MinistryDNA'
```

and the route inside the `AppLayout` nested block (after `/sermons`):

```tsx
          <Route path="/ministry-dna" element={<MinistryDNA />} />
```

- [ ] **Step 3: Add the nav item** in `frontend/src/components/layout/AppLayout.tsx` (after the Sermons entry):

```tsx
  { to: '/ministry-dna', label: 'Ministry DNA' },
```

- [ ] **Step 4: Type-check the frontend**

Run (from `frontend/`): `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Full manual verification** (both servers running: backend 8001, frontend 5174). In the browser at `http://localhost:5174`: sign up → finish onboarding → go to **Sermons**, paste a transcript with a personal story, upload → watch status reach "complete" → go to **Testimonies**, approve a suggestion → go to **Ministry DNA**, confirm metrics + narrative render.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/MinistryDNA.tsx frontend/src/App.tsx frontend/src/components/layout/AppLayout.tsx
git commit -m "feat: ministry DNA report page with metrics + narrative + timeline"
```

---

## Final verification

- [ ] Run the full backend unit suite (from `backend/`): `.\venv\Scripts\python.exe -m pytest -v` — all green.
- [ ] `npx tsc --noEmit` in `frontend/` — clean.
- [ ] Manual end-to-end (Task 11 Step 5) passes.

## Spec coverage check

- Feature #1 (sermon upload + Voice DNA enrichment): Tasks 1–4, 7 (documents+audio, in-process processing, additive merge + version snapshot). ✓
- Feature #2 (testimony mining + one-click approval): Tasks 5, 7, 8, 10. ✓
- Feature #6 (Ministry DNA Report, hybrid): Tasks 6, 8, 11. ✓
- Out-of-scope items (YouTube, raw-file storage, >25MB audio, websockets) intentionally excluded. ✓
