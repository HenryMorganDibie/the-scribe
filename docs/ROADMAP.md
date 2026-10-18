# The Scribe — Roadmap: from Christian ghostwriter to book-finishing workspace

**Goal:** The Scribe is an AI workspace that helps you *finish* a book. Each book
keeps its own context — chapters, notes, research, characters/references,
style, drafts and progress — so the AI works from the whole book, not a prompt.

**Strategy:** generic core + **genre packs**. A pack defines onboarding
questions, book-bible entry types, prompt fragments, a reference verifier and
nav labels. Christian writing becomes the first pack (no regression for
existing users). Second pack: general non-fiction (talks/podcasts/posts → book,
reusing the sermon pipeline). Fiction third.

Mark items `[x]` as they land. Add the PR/commit next to finished items.

---

## Phase 0 — Reposition (a few days) — done, commit `3563625`

- [x] Rewrite the landing page around "finish your book" (`frontend/src/pages/Landing.tsx`)
- [x] Update `README.md` / `ARCHITECTURE.md` intro to the broader positioning
- [x] Add a `pack` / book-type field (start with `christian` and `general`), default existing users to `christian` (`voice_profiles.pack`, migration `0007`; new users default to `general`)
- [x] Make prompts genre-neutral; move Christian wording into the Christian pack
  - [x] `build_voice_brief`, chapter generation, voice preview, voice DNA extraction (`backend/app/services/ai/generation.py`)
  - [x] Companion chat, sermon book planner, DNA report, testimony mining, voice enrichment (`backend/app/services/ai/`)
- [x] Pack-driven nav labels (`frontend/src/components/layout/AppLayout.tsx`)
  - [x] Sermons → Sources
  - [x] Testimonies → Stories
  - [x] Ministry DNA → Voice DNA
- [x] Generic onboarding path: replace theological lens / translation / guardrails with genre, audience, style rules for non-Christian packs (`Onboarding.tsx`, `routes/onboarding.py`)
- [x] Keep DB table names (`sermons`, `testimonies`, `scriptures`) unchanged — rename only in UI/API copy
- [x] Pack switcher on the Voice Profile page; scripture tools hidden for non-Christian packs
- [x] Fix: onboarding steps after the first were never saved (JSONB in-place mutation)

## Phase 1 — The workspace — done, commit `bc981eb`

- [x] **Per-book style:** project-level style/voice that inherits from the user's default voice profile
- [x] **Book bible:** typed entries per project (character, place, term, source, note, research clip)
  - [x] Model + migration + CRUD routes
  - [x] Embed entries for retrieval (same pattern as `index_chapter`)
  - [x] Inject relevant entries into chapter generation and Companion Chat
  - [x] UI: book-bible panel in Manuscript Studio and the chapter editor sidebar
- [x] **Notes & research** attached to a book or chapter (can share the book-bible model)
- [x] **Chapter draft history:** versions on save and before every AI generation; view/restore
  - [x] Stop "Generate chapter" from clearing the editor with no way back
- [x] Per-book source library (sources linked to a project, not only the user)
- [x] Fix: leaving the editor silently dropped the last edits (unmount save still used the removed bearer token)

Later improvements noticed while building Phase 1:
- [ ] Show all *relevant* book-bible entries in the editor sidebar, not only the ones attached to the chapter
- [ ] Side-by-side diff between a version and the current draft
- [ ] Re-index existing linked sources' embeddings if the embedding model ever changes

## Phase 2 — Help with finishing — done, commit `860f0e8`

- [x] Goals: target word count, deadline, daily target per book (weekly target not built — see below)
- [x] Progress dashboard: outline → drafted → revised → done per chapter
- [x] "What's next" from Companion Chat (gaps in the outline, unfinished chapters)
- [x] Consistency checks: repeated content across chapters, contradicting book-bible facts
- [x] Writing streaks / session history
- [x] Chapter stages (Outline → Drafted → Revised → Done) settable from the studio and the editor — previously nothing in the UI could mark a chapter complete

Later improvements noticed while building Phase 2:
- [ ] Days follow UTC; use the writer's own timezone for "today" and streaks
- [ ] Optionally exclude AI-generated words from the daily goal (count only words the author typed)
- [ ] Cross-book writing stats and streak on the Dashboard
- [ ] Weekly word target (alongside the daily one)

## Phase 3 — Second pack, then fiction — done (except academic), pending commit

- [x] **General non-fiction pack**
  - [x] Source ingestion copy and prompts for talks, podcasts, lectures, blog posts, interviews
  - [x] Story/anecdote bank (from testimony mining)
  - [x] Citation/quote verification (generalise the scripture verifier)
- [x] **Fiction pack**
  - [x] Character / place / timeline entry types with continuity checks
  - [x] Scene-level structure inside chapters
  - [x] Fiction-specific style signals (POV, tense, dialogue ratio)
- [ ] (Later) Academic pack: citation manager, literature base, reference styles
- [x] Plan tab in the editor: edit a chapter's intent and key points (previously impossible after creation) plus its scene/section plan
- [x] Fix: voice check showed "NaN%" after running (response field name mismatch)

Later improvements noticed while building Phase 3:
- [ ] Verify quotes from published works outside the book's own sources (citation lookup)
- [ ] Detect dialogue in single quotes (British style) for the fiction signals
- [ ] Warn automatically when a chapter's POV/tense drifts from the book's POV rule

---

## Carry-over from the code review (do alongside)

- [x] Logged-out reload loop, email casing, companion-chat quota/history, export filename crash, silent SSE errors — commit `4d0ce59`
- [x] Chapter/project deletes (migration `0006`, integration test) — commit `ff299d5`
- [ ] Rate-limit the onboarding preview/complete, reprocess and DNA report endpoints; validate onboarding input sizes
- [ ] First-chunk timeout on LLM providers so failover actually happens
- [ ] Durable background jobs (job table + recovery on startup) — more important with more source uploads
- [ ] Redesign the voice match score (compare against the author's own samples + style features)
- [ ] Fresh DB session inside streaming endpoints
- [ ] Remove dead code / stale docs (commented-out onboarding, dramatiq/Railway references, unused deps)
