# Design Spec: Sermon Ingestion, Testimony Mining & Ministry DNA Report

**Date:** 2026-06-19
**Status:** Approved (pending implementation plan)
**Features:** #1 Sermon Upload & Automatic Knowledge Extraction, #2 Automatic Testimony Mining, #6 Ministry DNA Report (from `feat.docx`)

---

## 1. Goal & Scope

Let authors feed their existing sermons (documents and audio) into The Scribe so the system can:
1. Transcribe/extract the text and **enrich the author's Voice DNA** automatically (#1).
2. **Mine personal stories** from that text and suggest them for the Testimony Vault with one-click approval (#2).
3. Aggregate everything into a **Ministry DNA Report** of recurring themes, most-quoted scriptures, most-used phrases, dominant ministry focus, and voice change over time (#6).

The three features share one ingestion backbone: #2 and #6 consume the text that #1 ingests.

### Decisions locked during brainstorming
- **Input formats (v1):** Documents (PDF, DOCX, pasted text) + Audio (transcribed via Groq Whisper `whisper-large-v3`). **No YouTube** in v1.
- **Processing model:** In-process FastAPI `BackgroundTask`s + a status-polling endpoint. **No Redis required** (works in local dev today).
- **DNA Report:** Hybrid — exact metrics computed from the database + a short cached AI narrative.
- **Voice enrichment:** Each sermon **auto-merges** (additive, non-destructive) into the Voice DNA profile and writes a `VoiceVersion` snapshot.
- **Storage:** Persist **extracted transcript text only**, not the raw uploaded file/audio binary (no object storage needed).

### Out of scope (v1)
YouTube ingestion; persisting raw uploaded files; chunked transcription of audio above the Groq size limit; websockets/real-time push (we poll); multi-language transcription tuning; suggestion-based (approval-gated) voice updates.

---

## 2. Data Model

### New table: `sermons`
Represents an ingested source and its processing state.

| Column | Type | Notes |
|---|---|---|
| `id` | String PK (uuid) | |
| `user_id` | String FK → users.id (CASCADE) | |
| `title` | String | user-provided or derived from filename |
| `source_type` | String | `pdf` \| `docx` \| `text` \| `audio` |
| `original_filename` | String, nullable | for display only |
| `status` | String | `pending` \| `extracting` \| `analyzing` \| `complete` \| `failed` |
| `transcript` | Text, nullable | extracted/transcribed text |
| `word_count` | Integer, default 0 | |
| `phrases_added` | Integer, default 0 | result summary |
| `testimonies_suggested` | Integer, default 0 | result summary |
| `error_message` | Text, nullable | populated on `failed` |
| `created_at` | DateTime | |
| `processed_at` | DateTime, nullable | |

Index: `(user_id, status)`.

### Extend `testimonies` (additive, non-breaking)
| Column | Type | Default | Notes |
|---|---|---|---|
| `status` | String | `approved` | `suggested` \| `approved` |
| `source` | String | `manual` | `manual` \| `mined` |
| `source_sermon_id` | String FK → sermons.id, nullable | NULL | provenance for mined testimonies |

Existing rows default to `approved`/`manual`, so current behavior is unchanged.

### Extend `voice_profiles` (for the cached DNA narrative)
| Column | Type | Default | Notes |
|---|---|---|---|
| `dna_narrative` | Text, nullable | NULL | cached AI narrative for the DNA Report; set to NULL on each ingest to invalidate, regenerated lazily on next report request |

### Reused without schema change
- `document_embeddings` — gains a new `doc_type` value `'sermon'` (`source_id = sermon.id`).
- `voice_versions` — gains a new `trigger` value `'sermon_ingested'`.

### Migration
One Alembic revision: create `sermons`, add the three `testimonies` columns, add `voice_profiles.dna_narrative`. (Reuses the existing async migration setup.)

---

## 3. Ingestion Pipeline

### Entry point
`POST /api/sermons` accepts **either**:
- multipart file upload (`file` + optional `title`), or
- JSON `{ "title", "text" }` for pasted text.

Handler: validate → create `Sermon` row (`status=pending`) → register a FastAPI `BackgroundTask` → return `{ sermon_id, status }` (HTTP 202). The request returns immediately.

### Background task steps
Runs in-process with its own DB session (mirrors the pattern in `app/workers/tasks.py` but without Dramatiq):

1. **Extract text** → set `status=extracting`.
   - `pdf` → `pypdf` (new dependency).
   - `docx` → `python-docx` (already installed; used by export).
   - `text` → use as-is.
   - `audio` → Groq Whisper via the existing `groq` client (`client.audio.transcriptions.create(model="whisper-large-v3", file=...)`).
   - Save `transcript`, `word_count`.
2. **Embed for RAG** → chunk + embed transcript into `document_embeddings` (`doc_type='sermon'`) via the existing `EmbeddingService`.
3. **Enrich Voice DNA** → set `status=analyzing`. Run extraction on the transcript, then **additively merge** into `VoiceProfile`:
   - `signature_phrases`: union (dedup).
   - `anchor_scriptures`: merge by `ref` (keep existing, add new).
   - `style_tags`: union.
   - `cadence_score`: blended/updated.
   - `voice_summary`: regenerated to reflect the expanded corpus.
   Then write a `VoiceVersion` snapshot (`trigger='sermon_ingested'`, `change_summary` describing what the sermon added).
4. **Mine testimonies** → one LLM pass over the transcript returns candidate stories as JSON (`title`, `story`, `themes`). Insert each as a `Testimony` with `status='suggested'`, `source='mined'`, `source_sermon_id`. (Mined testimonies are NOT embedded until approved.)
5. Set `status=complete`, `processed_at=now`, populate `phrases_added` / `testimonies_suggested`.

### Status & errors
- `GET /api/sermons/{id}` returns the row (status + result summary) for UI polling.
- Any failure sets `status=failed` + `error_message` and stops the pipeline. Causes: unreadable/empty document, audio over the Groq size limit, transcription error, LLM/JSON parse failure (mining failure is non-fatal — log and continue to `complete`).

### Constraint
Groq Whisper caps audio file size (~25 MB). v1 rejects oversized audio at upload with a clear message; chunked transcription is a future enhancement.

---

## 4. Testimony Mining UX (#2)

- Mined testimonies are stored with `status='suggested'` and never auto-enter the vault.
- The **Testimonies page** shows a "Suggested from your sermons" section above the approved list.
- Each suggestion card supports:
  - **Approve** (one click) → `status='approved'`; then index it for retrieval exactly like a manual testimony (reuse `index_testimony` flow).
  - **Edit then approve** → adjust title/story/themes, then approve.
  - **Dismiss** → delete the row.
- Endpoints:
  - `GET /api/testimonies?status=suggested` (extend existing list route with an optional filter).
  - `POST /api/testimonies/{id}/approve`.
  - Dismiss reuses the existing `DELETE /api/testimonies/{id}`.
- The existing manual create/list/update/delete flow is unchanged (manual testimonies remain `status='approved'`).

---

## 5. Ministry DNA Report (#6) — Hybrid

`GET /api/voice/dna-report` returns metrics computed directly from the database (exact, no token cost) plus a short cached AI narrative.

### Metrics (DB-computed)
- **Most-quoted scriptures** — ranked from `anchor_scriptures` + scripture references detected across sermon transcripts.
- **Most-used phrases** — `signature_phrases` ranked by occurrence count across the corpus (transcripts + samples).
- **Recurring themes** — tallied from anchor-scripture themes + testimony themes.
- **Dominant ministry focus** — derived from `theological_lens` + top themes.
- **Voice change over time** — series from the `VoiceVersion` timeline (`cadence_score`, `phrase_count`, `scripture_count` per version).

### AI narrative
One short LLM-written summary ("Your ministry centers on…"). Cached in `voice_profiles.dna_narrative`; invalidated (set NULL) on each ingest and regenerated lazily the next time the report is requested, so opening the report is normally free.

### Frontend
New **Ministry DNA page** renders the metrics with `recharts` (already a dependency) + the narrative.

---

## 6. API Summary

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/sermons` | Upload a sermon (file or text); returns sermon_id (202) |
| GET | `/api/sermons` | List the user's sermons |
| GET | `/api/sermons/{id}` | Status + result summary (polled by UI) |
| DELETE | `/api/sermons/{id}` | Delete a sermon (and its embeddings) |
| GET | `/api/testimonies?status=suggested` | List mined suggestions |
| POST | `/api/testimonies/{id}/approve` | Approve a suggested testimony |
| GET | `/api/voice/dna-report` | Ministry DNA Report (metrics + narrative) |

All routes require auth (`get_current_user`) and are user-scoped.

---

## 7. Frontend Changes

- **New "Sermons" page** — upload (drag-drop file or paste text), list with live status badges (polling `GET /api/sermons/{id}`), per-sermon result summary (phrases added, testimonies suggested).
- **Testimonies page** — add the "Suggested" review section (approve / edit-approve / dismiss).
- **New "Ministry DNA" page** — charts + narrative.
- Navigation entries for the two new pages.
- `lib/api.ts` — add a multipart upload helper and the new endpoint calls; add a small polling helper for sermon status.

---

## 8. New Dependencies

- Backend: `pypdf` (PDF text extraction).
- Audio transcription: existing `groq` client (no new dep).
- DOCX: existing `python-docx`.
- Frontend: none (`recharts` already present).

---

## 9. Testing

### Unit
- Text extraction per format (sample PDF/DOCX/text fixtures); audio path mocked at the Groq client boundary.
- Additive voice-DNA merge — asserts no existing phrases/scriptures are lost and new ones are added.
- DNA-report metric computation — deterministic given seeded data.
- Testimony-mining JSON parsing with malformed-output fallback (mirrors existing `extract_voice_dna` parsing).

### Integration
- Upload-text → poll until `complete` → assert: embeddings created (`doc_type='sermon'`), one new `VoiceVersion`, suggested testimonies present, sermon result counts populated.
- Approve a suggested testimony → assert `status='approved'` and that it indexes.

---

## 10. Build Order (high level)

1. Migration + models (`Sermon`, `Testimony` extensions).
2. Text-extraction service (per-format) + Groq Whisper transcription.
3. Ingestion service + in-process background runner + sermon routes (upload/list/status/delete).
4. Voice-DNA merge logic + `VoiceVersion` snapshot on ingest.
5. Testimony mining + suggestion endpoints + approve flow.
6. Ministry DNA Report endpoint (metrics + cached narrative).
7. Frontend: Sermons page, Testimonies suggestions, Ministry DNA page, nav + api client.
8. Tests (unit + integration) throughout.
