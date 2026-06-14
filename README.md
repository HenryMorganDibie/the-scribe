# The Scribe

An AI writing assistant for Christian authors — apostolic, prophetic, and Spirit-filled
voices in particular. The Scribe does not write generic devotional copy. It interviews
an author about their theological lens, recurring phrases, anchor scriptures, cadence,
and personal testimonies, builds a versioned "voice profile" from that interview, and
then ghostwrites manuscript chapters in that voice — retrieving the author's own
material via embeddings rather than stuffing everything into one prompt.

---

## Table of contents

- [What's actually in here](#whats-actually-in-here)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [LLM provider: Anthropic vs Groq](#llm-provider-anthropic-vs-groq)
- [Setup](#setup)
  - [1. Database (Postgres + pgvector)](#1-database-postgres--pgvector)
  - [2. Backend](#2-backend)
  - [3. Frontend](#3-frontend)
- [Running it](#running-it)
- [Using the app — a walkthrough](#using-the-app--a-walkthrough)
- [Testing](#testing)
  - [1. One-command end-to-end smoke test](#1-one-command-end-to-end-smoke-test-recommended)
  - [2. Manual curl walkthrough](#2-manual-curl-walkthrough)
  - [3. UI walkthrough (for the recorded demo)](#3-ui-walkthrough-for-the-recorded-demo)
  - [4. Backend unit tests](#4-backend-unit-tests)
- [Project structure](#project-structure)
- [Design system](#design-system)
- [Known limitations / what's stubbed](#known-limitations--whats-stubbed)
- [Deployment notes](#deployment-notes)

---

## What's actually in here

| Feature | Where it lives |
|---|---|
| Voice Onboarding Interview (9 steps) | `frontend/src/pages/Onboarding.tsx`, `backend/app/api/routes/onboarding.py` |
| Live Voice Preview during onboarding (SSE) | `POST /api/onboarding/preview`, `generate_voice_preview_stream` in `app/services/ai/generation.py` |
| Voice DNA extraction (background job) | `backend/app/workers/tasks.py` → `extract_voice_dna_task` |
| pgvector embeddings + RAG retrieval | `backend/app/services/voice/embeddings.py`, `retrieve_relevant_context` in `generation.py` |
| Voice Brief builder (the "ghost brief") | `build_voice_brief` in `app/services/ai/generation.py` |
| LLM provider abstraction (Anthropic / Groq) | `backend/app/services/ai/llm_client.py` |
| Chapter memory (prior-chapter summaries) | `get_chapter_memory` in `generation.py`, `generate_chapter_summary_task` |
| Voice drift / match scoring | `score_voice_match`, `POST /api/generate/voice-check` |
| Scripture index (seeded, themed) | `backend/scripts/seed_scriptures.py`, `Scripture` model |
| Voice Evolution Timeline | `backend/app/services/voice/timeline.py`, `frontend/src/pages/VoiceProfile.tsx` |
| Manuscript Studio (drag-to-reorder chapters) | `frontend/src/pages/ManuscriptStudio.tsx` |
| Chapter Editor (TipTap) + Scribe AI sidebar | `frontend/src/pages/ChapterEditor.tsx` |
| DOCX export | `backend/app/services/export/docx_export.py` |

---

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌────────────────────┐
│   React UI   │◄────►│   FastAPI    │◄────►│  PostgreSQL +       │
│  (Vite, TS)  │ SSE  │   backend    │      │  pgvector           │
└─────────────┘      └──────┬───────┘      └────────────────────┘
                             │
                  ┌──────────┼──────────┐
                  ▼                     ▼
          ┌───────────────┐   ┌──────────────────┐
          │  Anthropic API │   │  Dramatiq + Redis │
          │ (Claude Sonnet)│   │  (background jobs)│
          └───────────────┘   └──────────────────┘
```

Every AI generation request (chapter draft, "continue writing", weave-story, chat)
goes through `build_voice_brief()`, which compiles:

- the author's theological lens, tone preferences, cadence description
- their signature phrases and anchor scriptures
- a 300-word "voice summary" generated once from their writing samples
- the most relevant chunks of their writing samples and testimonies, retrieved via
  pgvector cosine similarity against the current chapter's topic
- summaries of prior chapters in the same manuscript (chapter memory)

This brief is prepended to every prompt sent to Claude, so generation is grounded in
the author's actual material rather than a generic prompt template.

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** and npm
- **PostgreSQL 15+ with the `pgvector` extension** (or use the provided `docker-compose.yml`)
- **Redis** (for background jobs — optional in dev, the app degrades gracefully without it)
- An LLM provider key — **either**:
  - an **Anthropic API key** (`ANTHROPIC_API_KEY`) — this is the production target
    and what the final demo/submission should run on, **or**
  - a **Groq API key** (`GROQ_API_KEY`, free at [console.groq.com](https://console.groq.com)) —
    useful for development iteration without spending Anthropic credits

---

## LLM provider: Anthropic vs Groq

The Scribe talks to its LLM through one abstraction
(`backend/app/services/ai/llm_client.py`), so the provider is a one-line config
change — nothing else in the codebase changes.

| | Anthropic (`claude-sonnet-4`) | Groq (`llama-3.3-70b-versatile`) |
|---|---|---|
| Cost | Paid (~$3/$15 per M tokens in/out) | Free tier |
| Speed | Fast | Very fast |
| Output quality for this use case | Best — strongest at sustained voice-matching and theological nuance over long generations | Good — solid for iterating on prompts, UI, and the demo flow; voice-matching is noticeably less precise on long chapters |
| Recommended for | Final demo recording, submission, anything you'll show reviewers | Local development, rapid prompt iteration, rehearsing the demo flow for free |

Set the provider in `backend/.env`:

```env
LLM_PROVIDER=anthropic   # or "groq"

ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-20250514

GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile
```

Restart the backend after changing `LLM_PROVIDER` — no code changes needed.
Every `generation_logs` row records which provider produced it, so you can
compare quality side-by-side if you generate the same chapter under both.

**Recommendation for this project**: develop and rehearse on Groq (free, fast
iteration), then switch to `LLM_PROVIDER=anthropic` for the final demo recording
and for whatever output you submit. The quality difference is real, especially
on full chapter generations — Claude holds the voice brief and chapter memory
more consistently over 1,500+ words.

---

## Setup

### 1. Database (Postgres + pgvector)

Easiest path — use the provided Docker Compose file, which runs Postgres with
pgvector pre-installed and Redis:

```bash
docker compose up -d
```

This starts:
- Postgres on `localhost:5432` (user `scribe`, password `scribe`, db `thescribe`)
- Redis on `localhost:6379`

If you'd rather use Supabase or a managed Postgres, just make sure the `vector`
extension is enabled (`CREATE EXTENSION IF NOT EXISTS vector;`) — the first
migration does this automatically if your Postgres user has the privilege.

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
```

Edit `.env`:

```env
DATABASE_URL=postgresql+asyncpg://scribe:scribe@localhost:5432/thescribe
SYNC_DATABASE_URL=postgresql://scribe:scribe@localhost:5432/thescribe

# Pick one provider — see "LLM provider" section above
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...your-key...
# ANTHROPIC_API_KEY=sk-ant-...your-key...

SECRET_KEY=generate-a-random-string-here
REDIS_URL=redis://localhost:6379/0
CORS_ORIGINS=["http://localhost:5173"]
```

Run migrations and seed the scripture index:

```bash
alembic upgrade head
python scripts/seed_scriptures.py
```

You should see `Seeded 15 scriptures.`

Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/api/docs` — you should see the full FastAPI/Swagger
docs for every route described in the table above.

**(Optional) Start the background worker** — needed for Voice DNA extraction and
chapter summaries to run automatically. In a second terminal:

```bash
cd backend
source venv/bin/activate
dramatiq app.workers.tasks
```

Without this running, onboarding still completes and the app remains usable —
the voice profile just won't get its AI-extracted signature phrases / cadence
score / voice summary until you run the worker (or restart it later; the job
is queued in Redis and will be picked up whenever a worker is running).

### 3. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
```

`.env.local` should point at your backend:

```env
VITE_API_URL=http://localhost:8000/api
```

Start the dev server:

```bash
npm run dev
```

Visit `http://localhost:5173`.

---

## Running it

With Postgres/Redis (via `docker compose up -d`), the backend (`uvicorn`), the
worker (`dramatiq`), and the frontend (`npm run dev`) all running, you have the
full stack live at `http://localhost:5173`.

---

## Using the app — a walkthrough

This is the actual user flow, useful both for manual testing and for recording
a demo.

1. **Sign up** at `/signup` with a name, email, and password.
2. You're redirected to **`/onboarding`** — a 9-step voice interview:
   - Ministry background (free text)
   - Theological lens (Apostolic / Prophetic / Spirit-filled / Pentecostal / Word of Faith)
   - Target audience (free text)
   - Tone preferences (multi-select, order matters)
   - Preferred Bible translation
   - Signature phrases (one per line — things you say often)
   - Anchor scriptures (one reference per line, e.g. `Isaiah 61:1-3`)
   - Writing samples (paste a sermon, devotional, or social post — the more the better)
   - A personal testimony (goes straight into the Testimony Vault)

   After steps marked with a preview trigger (theological lens, tone, signature
   phrases, anchor scriptures, writing samples), the **right-hand panel streams a
   live AI-generated paragraph** showing what your voice sounds like so far. This
   updates as you provide more information — it's the most visually interesting
   part of the app to demo.

3. On completing step 9, onboarding finalizes and two background jobs fire:
   - `extract_voice_dna_task` — analyzes your writing samples and populates
     `signature_phrases`, `cadence_score`, `style_tags`, `voice_summary`, and
     additional `anchor_scriptures` on your voice profile. Also creates **Voice
     Version 1** in your evolution timeline.
   - `index_writing_samples_task` — chunks and embeds your writing samples into
     `document_embeddings` for later retrieval.

   If the Dramatiq worker isn't running, these jobs sit queued in Redis until a
   worker starts. The dashboard will show "still being processed" until then.

4. **`/dashboard`** — your "Desk". Shows your Voice DNA summary (once processed)
   and your manuscripts.

5. **`/voice-profile`** — full Voice DNA: theological lens, cadence score (with a
   visual bar), signature phrases, anchor scriptures with themes, style tags, and
   the **Voice Evolution Timeline** — a version history of your profile. Each
   manual edit or accepted chapter edit creates a new version with a diff
   (phrases added/removed, cadence shift direction).

6. **`/testimonies`** — add personal stories with themes. Each one is chunked and
   embedded immediately for retrieval.

7. **`/projects`** — create a manuscript: title, genre (teaching / devotional /
   prophetic / memoir), target chapter count, and a theme description.

8. **Manuscript Studio** (`/projects/:id`) — add chapters with a title and an
   "intent" (what the chapter should accomplish). Chapters can be **drag-reordered**
   — this calls `PUT /api/projects/:id/chapters/reorder`.

9. **Chapter Editor** (`/projects/:id/chapters/:chapterId`) — the main event:
   - If the chapter is empty, a **"Generate Chapter Draft in My Voice"** button
     streams a full ~1,500–2,500 word draft, built from: the voice brief, RAG-retrieved
     writing samples and testimonies relevant to this chapter's intent, and summaries
     of all prior chapters.
   - The right sidebar ("The Scribe") has two tabs:
     - **Quick Actions**: *Continue Writing* (streams a continuation from the
       cursor), *Check My Voice* (scores the current text against your voice
       profile and gives specific feedback), *Weave In My Story* (pick a
       testimony, streams it integrated into the text), *Suggest Scripture
       Anchor* (returns 3 verified scriptures with one-click insert).
     - **Chat**: freeform conversation with "The Scribe" — it has your full voice
       brief as system context.
   - Content autosaves 2 seconds after you stop typing. **Export** downloads the
     chapter (or full manuscript, from Manuscript Studio) as a `.docx`.

---

## Testing

There are three layers here: a one-command end-to-end smoke test (the fastest way
to prove everything works), manual curl calls for poking at individual endpoints,
and a small pytest scaffold for the core logic. For a reviewer demo, the smoke
test plus a short walkthrough in the UI is the strongest combination — it proves
the backend works independent of the UI, then shows the UI is just a thin layer
on top of a real system.

### 1. One-command end-to-end smoke test (recommended)

`backend/scripts/smoke_test.py` runs the entire user journey against your running
backend — signup, onboarding, live voice preview, voice DNA check, create
manuscript, create chapter, **generate a full chapter in the author's voice
(streamed)**, voice match scoring, and DOCX export. It prints readable,
narratable output at each step.

```bash
# Terminal 1
cd backend && source venv/bin/activate
uvicorn app.main:app --reload

# Terminal 2 (optional but recommended — enables Voice DNA extraction)
cd backend && source venv/bin/activate
dramatiq app.workers.tasks

# Terminal 3
cd backend && source venv/bin/activate
python scripts/smoke_test.py
```

Expected output (abridged):

```
============================================================
  1/8  Signing up demo author
  demo-1718...@thescribe.test
============================================================
✓ Account created. Token acquired.

============================================================
  2/8  Completing voice onboarding interview
============================================================
✓ Onboarding complete. Voice DNA is being processed...

============================================================
  3/8  Streaming live voice preview
============================================================
✓ Preview generated:

  "Let that sink in — before the foundations of the earth were laid..."

============================================================
  4/8  Checking voice profile (background DNA extraction)
============================================================
✓ Voice DNA extracted:
  Cadence score: 0.35
  Signature phrases: ['This is your set time', 'Let that sink in', ...]

...

============================================================
  7/8  Generating chapter draft in author's voice (this is the main feature)
============================================================
There is a season every called person walks through...
[full ~1,800 word chapter streams to the terminal in real time]

✓ Generated 1,847 words in 14.2s

============================================================
  8/8  Running voice match check + exporting manuscript
============================================================
✓ Voice match: 87% (Strong)
  Feedback: This passage is strongly in your voice.
✓ Manuscript exported to /tmp/the-scribe-demo-export.docx (38214 bytes)

============================================================
  DONE — full journey completed successfully
============================================================
```

This is a good script to run live on screen while narrating — it's the fastest
way to prove the system works end-to-end, including the parts (background voice
DNA extraction, embeddings, chapter memory) that aren't visually obvious in the UI.

Run it once with `LLM_PROVIDER=groq` while developing (free), then once with
`LLM_PROVIDER=anthropic` before recording your final demo to confirm output
quality on the production provider.

### 2. Manual curl walkthrough

If you want to inspect individual responses (e.g. to check the exact shape of
the voice brief, or debug a specific endpoint), the Swagger UI at
`http://localhost:8000/api/docs` lets you authenticate once and try every route
interactively. Or via `curl`:

```bash
# 1. Sign up
curl -s -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123","full_name":"Test Author"}' \
  | tee /tmp/signup.json

TOKEN=$(python3 -c "import json;print(json.load(open('/tmp/signup.json'))['access_token'])")

# 2. Check auth works
curl -s http://localhost:8000/api/auth/me -H "Authorization: Bearer $TOKEN"

# 3. Complete onboarding (minimal data)
curl -s -X POST http://localhost:8000/api/onboarding/complete \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "data": {
      "ministry_background": "I pastor a small church focused on prophetic discipleship.",
      "theological_lens": "Prophetic",
      "target_audience": "Believers who feel called but uncertain of their purpose.",
      "tone_preferences": ["Teaching", "Exhortation"],
      "preferred_translation": "NKJV",
      "signature_phrases": ["This is your set time", "Let that sink in"],
      "anchor_scriptures": ["Isaiah 61:1-3", "Jeremiah 29:11"],
      "writing_samples": ["Paste a few paragraphs of real sermon/devotional text here for best results."]
    }
  }'

# 4. Stream a live voice preview (SSE — chunks print as they arrive)
curl -N -s -X POST http://localhost:8000/api/onboarding/preview \
  -H "Authorization: Bearer $TOKEN"

# 5. Create a project
PROJECT=$(curl -s -X POST http://localhost:8000/api/projects \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"Called","genre":"teaching","theme":"Finding purpose in the wilderness season","target_chapters":5}')
PROJECT_ID=$(python3 -c "import json,sys;print(json.loads('$PROJECT')['id'])")

# 6. Add a chapter
CHAPTER=$(curl -s -X POST http://localhost:8000/api/projects/$PROJECT_ID/chapters \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"The Wilderness Season","chapter_number":1,"intent":"Help the reader see their current hardship as preparation, not punishment.","key_points":["God uses wilderness seasons to prepare leaders","Isolation is not abandonment"],"anchor_scriptures":["Isaiah 61:1-3"],"testimony_ids":[]}')
CHAPTER_ID=$(python3 -c "import json,sys;print(json.loads('$CHAPTER')['id'])")

# 7. Generate the chapter (SSE stream — this is the main feature)
curl -N -s -X POST http://localhost:8000/api/generate/chapter \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"chapter_id\":\"$CHAPTER_ID\"}"
```

You should see a stream of `data: {"text": "..."}` chunks followed by `data: [DONE]`.

**If Voice DNA hasn't finished processing yet** (no Dramatiq worker running), the
voice brief falls back to raw onboarding answers — generation still works, just
without the extracted signature phrases / cadence score / voice summary layered in.

### 3. UI walkthrough (for the recorded demo)

Once the smoke test confirms the backend works, the recorded demo should walk
through the same journey in the UI, in this order — it maps directly onto the
"What it does" list on the landing page and tells a complete story:

1. **Landing page** — orient the reviewer: who this is for, what makes it different.
2. **Sign up → Onboarding** — go through 2–3 steps quickly, then pause on a step
   with a `previewTrigger` (e.g. signature phrases or writing samples) and let
   the **Live Voice Preview** stream on screen. This is the single most
   memorable moment in the demo — narrate what's happening ("it's drafting in
   real time, based only on what I've told it so far").
3. **Dashboard** — show the Voice DNA summary populating (if the worker has run).
4. **Voice Profile page** — show the full Voice DNA breakdown and the **Voice
   Evolution Timeline** — explain that this versions like commit history.
5. **Testimony Vault** — add or show a testimony.
6. **Manuscript Studio** — create a chapter, show drag-to-reorder.
7. **Chapter Editor** — the centerpiece:
   - Click **Generate Chapter Draft in My Voice** and let it stream.
   - Use **Check My Voice** to show the match score and feedback.
   - Use **Weave In My Story** to show testimony retrieval in action.
   - Use **Suggest Scripture Anchor** to show the scripture index.
   - Briefly show the **Chat** tab.
8. **Export** — download the `.docx` and show the formatted result.

Keep narration focused on *why* each piece exists (the voice brief, RAG
retrieval, chapter memory) rather than just *what* it does — that's what
separates this from "I called an LLM API in a loop."

### 4. Backend unit tests

A `pytest` scaffold covers the two pieces of core logic that don't require a
live LLM call: the voice brief builder and DOCX export.

```bash
cd backend
source venv/bin/activate
pip install pytest pytest-asyncio   # if not already installed
pytest -v
```

Expand this suite as time allows — `retrieve_relevant_context` (with a seeded
test database) and the `/api/generate/*` routes with a mocked LLM client are the
next highest-value additions.

---

## Project structure

```
the-scribe/
├── docker-compose.yml          # Postgres+pgvector, Redis
├── backend/
│   ├── app/
│   │   ├── api/routes/          # auth, onboarding, projects, voice, generate, export
│   │   ├── core/                 # config, JWT/security
│   │   ├── db/                   # async session, Base
│   │   ├── models/                # SQLAlchemy models (users, voice_profiles,
│   │   │                          #   voice_versions, document_embeddings,
│   │   │                          #   testimonies, scriptures, projects,
│   │   │                          #   chapters, generation_logs)
│   │   ├── services/
│   │   │   ├── ai/generation.py   # voice brief builder, chapter generation,
│   │   │   │                      #   voice preview, voice DNA extraction,
│   │   │   │                      #   voice match scoring
│   │   │   ├── voice/embeddings.py # pgvector embedding + chunking
│   │   │   ├── voice/timeline.py   # voice version snapshots + diffs
│   │   │   └── export/docx_export.py
│   │   └── workers/tasks.py       # Dramatiq background jobs
│   ├── alembic/                   # migrations (0001_initial_schema creates
│   │                               #   everything incl. pgvector index)
│   └── scripts/seed_scriptures.py
└── frontend/
    └── src/
        ├── pages/                  # Landing, Login, Signup, Onboarding,
        │                           #   Dashboard, VoiceProfile, Testimonies,
        │                           #   Projects, ManuscriptStudio, ChapterEditor
        ├── components/layout/AppLayout.tsx
        ├── components/ui/QuillLogo.tsx
        ├── stores/authStore.ts     # Zustand auth state
        ├── lib/api.ts               # axios client + SSE stream helper
        └── styles/globals.css       # design tokens / component classes
```

---

## Design system

The visual language is a study desk, not a SaaS dashboard: warm paper tones
(`paper-*`) for reading and writing surfaces, a deep warm charcoal (`study-*`)
for chrome/navigation, and a single oxidized copper-red accent (`seal-*`) used
sparingly — like sealing wax on a letter. Typefaces: **Source Serif 4** for
display headings, **Source Sans 3** for UI text, and **Lora** for the manuscript
editor and reading surfaces. All tokens are defined in
`frontend/tailwind.config.js` and the component classes (`.card`, `.btn-primary`,
`.btn-secondary`, `.scripture-block`, `.manuscript-canvas`, `.status-tag`, `.folio`)
in `frontend/src/styles/globals.css`.

---

## Known limitations / what's stubbed

- **Auth** is a simple email/password + JWT implementation (no email verification,
  password reset, or OAuth). Fine for a demo; would need hardening for production.
- **Scripture index** is seeded with 15 well-known apostolic/prophetic verses
  (`backend/scripts/seed_scriptures.py`). The scripture-suggest endpoint currently
  asks Claude to return verses directly rather than querying this table — wiring
  the suggestion endpoint to query `scriptures` first (and fall back to Claude only
  for thematic matching) is a natural next step.
- **Embeddings** use `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim) running
  locally on CPU — fine for demo-scale data, but the first embedding call after a
  cold start will download the model (~90MB).
- **LLM provider**: the app runs on Anthropic (Claude Sonnet 4) or Groq
  (Llama 3.3 70B), switchable via `LLM_PROVIDER` in `.env` — see
  [LLM provider](#llm-provider-anthropic-vs-groq) above. Groq's free tier doesn't
  return token usage on streamed responses, so cost/latency figures for Groq
  generations in `generation_logs` are estimates (word-count based), not exact.
- **DOCX export** produces a clean, publisher-style manuscript but doesn't yet
  handle embedded images or a generated table of contents.
- **No PDF export** yet — only `.docx`.
- Background jobs degrade gracefully if Redis/Dramatiq aren't running (onboarding
  still completes), but Voice DNA won't populate until a worker processes the queue.

---

## Deployment notes

- **Backend**: any container host that can run `uvicorn` + a Postgres connection
  works (Railway, Render, Fly.io). Run `alembic upgrade head` and
  `python scripts/seed_scriptures.py` as part of your deploy step.
- **Worker**: deploy `dramatiq app.workers.tasks` as a separate process/service
  pointed at the same Redis and database.
- **Frontend**: static build via `npm run build` → `dist/` — deploy to Vercel,
  Netlify, or any static host. Set `VITE_API_URL` to your deployed backend's
  `/api` path.
- **Database**: any Postgres 15+ with the `vector` extension available (Supabase
  has this built in — enable it in the Database → Extensions panel before running
  migrations).

---

## Author

**Henry Dibie** — ML Systems Engineer & Data Scientist
[LinkedIn](https://linkedin.com/in/kinghenrymorgan) · [GitHub](https://github.com/HenryMorganDibie)
