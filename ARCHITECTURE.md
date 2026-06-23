# The Scribe — Architecture

A full-stack AI writing assistant for Christian authors. Built around a
Voice DNA model: the system learns the author's voice from everything they
have already preached or written before it generates a single word.

---

## System Overview

```
Browser / Mobile
React 18 + Vite + TypeScript + Tailwind CSS
Deployed on Vercel (auto-deploy from main)
         |
         | HTTPS + SSE (Server-Sent Events)
         |
FastAPI Backend
Python 3.12 · Uvicorn · SQLAlchemy 2.0 (async) · Alembic
Deployed on Render (Docker, auto-deploy from main)
         |                          |
Supabase (Postgres + pgvector)    External AI APIs
11 tables, Alembic migrations     - Anthropic Claude (generation, voice DNA)
Session pooler (port 5432)        - Groq Whisper (sermon transcription)
```

---

## Frontend

| Layer | Choice | Reason |
|---|---|---|
| Framework | React 18 + Vite | Fast HMR, ESM-native, TypeScript first-class |
| Styling | Tailwind CSS | Design-token-based; warm paper palette in `tailwind.config.js` |
| Rich text | TipTap (ProseMirror) | Inline formatting, no Quill DOM overhead |
| HTTP + SSE | Axios + custom `streamSSE()` | Upload progress natively; SSE without a library |
| State | Zustand (`useAuthStore`) | Auth token in localStorage, no boilerplate |
| Charts | Recharts | Composable, works well with Tailwind tokens |
| Drag-and-drop | `@dnd-kit` | Accessible, works on touch/mobile |
| Deployment | Vercel | Edge CDN, zero config for Vite |

### Design System

Three-tier palette — tokens in `tailwind.config.js`, component classes in `src/styles/globals.css`:
- `paper-*` — warm off-white for reading/writing surfaces
- `study-*` — deep charcoal for navigation chrome
- `seal-*` — copper-red accent, used sparingly (interactive elements, scripture highlighting)

Fonts: Source Serif 4 (display), Source Sans 3 (UI), Lora (manuscript editor).

---

## Backend

| Layer | Choice | Reason |
|---|---|---|
| Framework | FastAPI | Native async/await, SSE via StreamingResponse, auto OpenAPI |
| ORM | SQLAlchemy 2.0 async (asyncpg) | Typed models, async sessions, pgvector compatible |
| Migrations | Alembic | `alembic upgrade head` runs on every deploy |
| Auth | JWT (python-jose) + bcrypt | Stateless, no session store |
| Embeddings | fastembed (ONNX) | Local inference, no GPU, ~90MB model |
| Background | FastAPI BackgroundTasks | In-process, no broker/worker |
| LLM abstraction | `app/services/ai/llm_client.py` | `LLM_PROVIDER=anthropic` or `groq`, zero code changes to switch |

### Key Services

```
app/services/
├── ai/
│   ├── llm_client.py         # Provider abstraction (Anthropic / Groq)
│   ├── generation.py         # Voice brief, chapter generation, voice DNA,
│   │                         #   analyze_voice_drift() multi-dimensional scoring
│   └── companion_chat.py     # Whole-manuscript RAG chat
├── voice/
│   ├── embeddings.py         # index_writing_sample, index_testimony, index_chapter
│   └── timeline.py           # Voice version snapshots
├── ingestion/
│   ├── pipeline.py           # process_sermon() - PDF/DOCX/audio pipeline
│   └── transcription.py      # Groq Whisper, 25MB cap, 5-min timeout
└── export/
    └── docx_export.py        # python-docx export
```

### Background Task Flow

```
POST /api/onboarding/complete
  -> extract_voice_dna_task(user_id)
  -> index_writing_samples_task(user_id)

POST /api/testimonies
  -> index_testimony_task(user_id, testimony_id, story)

PUT /api/projects/:id/chapters/:id  (on content save)
  -> generate_chapter_summary_task(chapter_id)
  -> index_chapter_task(chapter_id)

POST /api/sermons
  -> process_sermon(sermon_id)  # transcription + voice enrichment + testimony mining
```

---

## Database Schema (11 tables)

```
users
  voice_profiles (1:1) -> voice_versions (1:many)
  projects (1:many)    -> chapters (1:many)
                          companion_chat_messages (1:many per project)
  testimonies (1:many)
  sermons (1:many)
  document_embeddings (1:many)  # pgvector, doc_type: writing_sample/testimony/chapter/sermon
  generation_logs (1:many)      # every AI call: tokens, cost, voice_match_score
  scriptures (shared, 15 seeded)
```

`document_embeddings.embedding` = `vector(384)` (all-MiniLM-L6-v2 via fastembed).
Similarity search uses pgvector `<=>` cosine distance, per-user scoped.

---

## AI Features

### Voice Brief (assembled per generation request)
1. `voice_summary` from voice DNA extraction
2. Signature phrases + anchor scriptures
3. Preferred Bible translation + cadence/style tags
4. RAG retrieval: relevant writing samples + testimonies (pgvector top-k)
5. Prior chapter summaries (chapter memory)
6. Chapter intent, key points, anchor scriptures

### Voice DNA Extraction
Claude extracts from writing samples: `signature_phrases`, `anchor_scriptures`,
`cadence_score` (0.0 punchy to 1.0 flowing), `style_tags`, `voice_summary`.

### Voice Drift Analytics
`analyze_voice_drift()` scores four dimensions:
- **Overall** — cosine similarity vs voice summary embedding
- **Cadence delta** — content rhythm vs profile baseline (signed)
- **Phrase usage rate** — fraction of signature phrases found in text
- **Scripture usage** — anchor scripture citations found

Every `/generate/voice-check` logs a `GenerationLog` row for the timeline chart.

### Manuscript Companion Chat
Per-query flow:
1. Embed the question (fastembed)
2. Retrieve top-6 semantically similar chapter chunks (`project_id` scoped)
3. Add structural manifest (every chapter: title, status, key points, scriptures)
4. Stream grounded answer; return `cited_chapter_ids` as clickable chips

### Sermon Ingestion Pipeline
1. Accept PDF / DOCX / audio (mp3, m4a, wav — not video)
2. Extract text (pypdf / python-docx) or transcribe (Groq Whisper, 5-min timeout)
3. Extract voice patterns + anchor scriptures (Claude)
4. Mine personal testimonies (Claude) → suggest to Testimony Vault

---

## Deployment

| Service | Platform | Config |
|---|---|---|
| Backend API | Render Web Service | `backend/Dockerfile`, root dir `backend` |
| Frontend | Vercel | `frontend/vercel.json`, root dir `frontend` |
| Database | Supabase | Session pooler, `postgresql+asyncpg://...` |

**Start command (Render)**:
```
alembic upgrade head && python scripts/seed_scriptures.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

**Required env vars (backend)**:
```
DATABASE_URL         Supabase Session pooler connection string
ANTHROPIC_API_KEY    When LLM_PROVIDER=anthropic
GROQ_API_KEY         Sermon audio transcription
SECRET_KEY           JWT signing key
ENVIRONMENT          Set to "production" on Render
CORS_ORIGINS         JSON array of allowed frontend origins
```

---

## Key Design Decisions

**No Redis / no separate worker.** BackgroundTasks run in-process after each HTTP response. One service, no operational overhead. Each task is already an `async def` function — migrating to Celery/Dramatiq is a call-site change only if scale requires it.

**SSE over WebSockets.** Unidirectional is sufficient for streaming generation. Works over HTTP/2, no special infrastructure, auto-reconnects. The `streamSSE()` helper in `lib/api.ts` handles text deltas (`onChunk`) and metadata payloads (`onEvent`) without a library.

**fastembed over sentence-transformers.** ONNX runtime is ~10x smaller than PyTorch, faster cold starts, identical embeddings. 384-dim vectors; exact cosine search (no IVFFlat index) is fast enough at per-user query scale.

**Provider-agnostic LLM client.** Single `llm_client.py` interface wraps both Anthropic and Groq. `LLM_PROVIDER` env var switches at runtime — free/fast Groq for dev, Claude for production voice consistency.
