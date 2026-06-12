# The Scribe ✍️

> AI writing assistant purpose-built for Christian authors. Not generic — every generation is deeply personalized to the individual author's theological voice, signature phrases, anchor scriptures, personal stories, and writing style.

## What makes it different

Most AI writing tools do: *upload sample → generate text.*

The Scribe does:
1. **Voice Onboarding Interview** — structured theological voice capture
2. **Live Voice Preview** — AI voice emerges in real time as you answer questions
3. **Voice DNA** — extracted signature phrases, cadence score, scripture patterns, style tags
4. **Embedding-powered retrieval** — relevant sermons/testimonies retrieved per chapter (not brute-force injected)
5. **Testimony Vault** — personal stories woven into manuscript contextually
6. **Chapter Memory** — prior chapter summaries maintain doctrinal consistency
7. **Voice Drift Scoring** — real-time voice match % on every generated paragraph
8. **Scripture Index** — verified, themed, translation-aware (no hallucinated refs)
9. **Voice Evolution Timeline** — version-controlled voice profile, like git commits for your writing identity

## Stack

| Layer | Tech |
|-------|------|
| Frontend | React + Vite + Tailwind + TipTap |
| Backend | FastAPI (Python 3.12) |
| Database | PostgreSQL + pgvector |
| AI | Claude API (claude-sonnet-4) |
| Embeddings | sentence-transformers / OpenAI Ada |
| Background Jobs | Dramatiq + Redis |
| Auth | Supabase Auth |
| Storage | Supabase Storage |
| Deploy | Railway (backend) + Vercel (frontend) |

## Project Structure

```
the-scribe/
├── backend/
│   ├── app/
│   │   ├── api/routes/       # FastAPI route handlers
│   │   ├── core/             # Config, security, dependencies
│   │   ├── db/               # Database session, migrations
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/
│   │   │   ├── ai/           # Claude API, voice brief builder, generation
│   │   │   ├── voice/        # Embedding, drift scoring, DNA extraction
│   │   │   └── export/       # DOCX/PDF generation
│   │   └── workers/          # Dramatiq background tasks
│   └── alembic/              # DB migrations
└── frontend/
    └── src/
        ├── components/       # UI components by domain
        ├── pages/            # Route pages
        ├── hooks/            # Custom React hooks
        ├── stores/           # Zustand state
        ├── lib/              # API client, utilities
        └── types/            # TypeScript types
```

## Getting Started

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in your keys
alembic upgrade head
python scripts/seed_scriptures.py
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## Author

**Henry Dibie** — ML Systems Engineer & Data Scientist  
[LinkedIn](https://linkedin.com/in/kinghenrymorgan) · [GitHub](https://github.com/HenryMorganDibie)
