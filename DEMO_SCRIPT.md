# The Scribe — Demo Video Storyboard

Target length: 12–14 minutes (limit: 15). Goal: prove this is a real,
production-architected system — not a prompt wrapper — while hitting every
bonus-point criterion (aesthetics, creative AI integration, thought process,
design system).

Record with `LLM_PROVIDER=anthropic` for this session — Claude's voice
consistency over long generations is the difference that will show.

---

## 0:00–0:45 — Cold open: the problem statement

**Screen**: Landing page (`/`).

**Say**:
> "Most AI writing tools work the same way: paste a sample, generate text. The
> problem is that a generic AI cannot write someone's testimony, cannot cite the
> scriptures they actually return to, and cannot sound like the person standing
> behind their pulpit. The Scribe is built around a different idea — it learns an
> author's voice first, as a structured, versioned profile, and only then writes
> in it. Let me show you how that works end to end."

Scroll the landing page slowly — let the "What it does" list (the six numbered
capabilities) be visible for a few seconds. This previews the whole demo and
shows you planned the architecture before the UI.

---

## 0:45–1:00 — Architecture in 15 seconds

**Screen**: Cut to the architecture diagram from the README (have it open in a
markdown preview or as a slide).

**Say**:
> "Quickly — the stack. React frontend, FastAPI backend, Postgres with pgvector
> for retrieval, Claude for generation, and a background worker for the heavier
> AI processing. The piece that matters most is this 'voice brief' — every single
> generation request gets built from the author's profile, their retrieved
> writing samples, their testimonies, and a memory of prior chapters. I'll show
> you each of those pieces as they get used."

Keep this tight — one breath, then move on.

---

## 1:00–4:30 — Sign up + Voice Onboarding + Live Voice Preview (the wow moment)

**Screen**: `/signup` → `/onboarding`

**Say** (while filling the first couple of steps quickly):
> "I'll sign up as a fictional author — a pastor with a prophetic, exhortative
> voice. The interview captures theological lens, target audience, tone,
> preferred translation..."

Move through steps 1–4 at a brisk, slightly sped-up pace (you can speed this
section up in editing — say so on screen: "speeding through the first few
steps").

**Slow down at "Signature Phrases" (step 6)**. Type in 2–3 real phrases, like:
- "This is your set time"
- "Let that sink in"
- "Can I be honest with you?"

**Say**:
> "Now watch the right panel."

Click Next — **let the Live Voice Preview stream fully on screen, in real time,
without cutting**. This is the single most important 20 seconds of the video.

> "That paragraph was generated using nothing but the phrases I just typed and
> the theological lens I picked two steps ago. As I add more — anchor scriptures,
> writing samples — this preview gets sharper. The author is watching their own
> voice come into focus before they've even finished the interview."

Continue to **Anchor Scriptures** (step 7) — type 2–3 real references (Isaiah
61:1-3, Jeremiah 29:11). Let the preview refresh again — this time narrate over
it rather than waiting in silence:

> "Notice it's already starting to lean on Isaiah 61 — that's the anchor
> scripture system feeding directly into generation, not just sitting in a
> database somewhere."

**Writing Samples (step 8)** — paste a real paragraph of sermon-style text
(write 100–150 words in the apostolic/prophetic voice beforehand, save it in a
notes file so you're not typing live). Let the preview refresh one final time.

> "This last preview is now grounded in an actual writing sample — this is the
> input that powers the deeper voice extraction that happens next."

**Personal Testimony (step 9)** — paste a short testimony (prepared in advance).

> "And this last step goes straight into the Testimony Vault — I'll come back to
> this."

Click **Complete Voice Interview**.

> "Behind the scenes, two background jobs just fired: one extracts the voice DNA
> — signature phrases, cadence, style tags, a voice summary — from the writing
> sample. The other chunks and embeds that sample and the testimony into a vector
> store, so they can be retrieved later by relevance, not just dumped into every
> prompt."

---

## 4:30–6:30 — Voice DNA + Voice Evolution Timeline

**Screen**: `/dashboard` → `/voice-profile`

> "While that processes, here's the dashboard — the 'desk'. And here's the full
> Voice DNA page."

Walk through, pointing at each section as it's mentioned:
- **Ghost brief** (voice summary) — "This 300-word summary is the compass every
  generation uses."
- **Cadence score** with the visual bar — "This tells the system whether this
  author writes in short, punchy declarations or longer, flowing sentences —
  extracted from the actual sample, not guessed."
- **Signature phrases** — point out the ones you typed are there, plus any the
  AI found in the sample itself.
- **Anchor scriptures** with themes.
- **Style tags**.

**Then the Voice Evolution Timeline**:

> "This is the part I'm most excited about. Every time this profile changes —
> after onboarding, after an edit gets accepted in a chapter — a new version gets
> snapshotted, like a commit history. Version 1 is what we just generated. As I
> write and edit chapters later, you'll see version 2 appear, showing exactly
> what changed: new phrases learned, a shift in cadence. The system is meant to
> get to know the author better the more they use it — not stay frozen at
> onboarding."

---

## 6:30–7:00 — Testimony Vault

**Screen**: `/testimonies`

> "Quick stop at the Testimony Vault — the story from onboarding is here, themed
> and embedded. Authors can add more at any time. I'll use this in a minute."

---

## 7:00–8:00 — Manuscript Studio

**Screen**: `/projects` → create new → `/projects/:id`

Create a manuscript live:
- Title: something specific, e.g. "Called: Finding Your Voice in the Wilderness"
- Genre: Prophetic
- Theme: one sentence
- Add Chapter 1 with a title + intent + 2–3 key points + an anchor scripture

> "I'm creating a short manuscript with one chapter to demo. Chapters can be
> drag-reordered — useful once an author has a dozen chapters and wants to
> restructure."

(Quickly demonstrate the drag if you have 2+ chapters — even add a placeholder
second chapter just to show the reorder, then delete it.)

---

## 8:00–11:30 — Chapter Editor: the centerpiece

**Screen**: Chapter Editor for Chapter 1

This is where most of your remaining time goes. Take it in this order:

### a) Generate Chapter Draft (8:00–9:30)

Click **Generate Chapter Draft in My Voice**. Let it stream for a while on
screen — don't skip this.

> "This single request is doing a lot. It's pulling the voice brief — theological
> lens, cadence, signature phrases, anchor scriptures. It's running a similarity
> search against my writing sample and testimony to find what's actually relevant
> to this chapter's intent — not dumping everything in. It's checking memory of
> any prior chapters for consistency. And it's writing in my preferred
> translation, citing only verified scriptures."

You can fast-forward part of the generation in editing, but show the
**beginning and end** live, including the full paragraph forming.

### b) Check My Voice (9:30–10:00)

Click **Check My Voice**.

> "This scores the generated text against my voice profile using embedding
> similarity, and gives specific feedback on anything that drifted."

Show the score and feedback.

### c) Weave In My Story (10:00–10:45)

Click **Weave In My Story**, pick the testimony.

> "Now watch this — it's pulling the testimony I gave during onboarding and
> weaving it into the chapter as a natural transition, not pasting it in as a
> block. This is retrieved via the embedding search I mentioned earlier — the
> system picked this testimony because it's thematically relevant to this
> chapter, not because I told it to."

Let it stream, then show the result reads naturally.

### d) Suggest Scripture Anchor (10:45–11:15)

Click **Suggest Scripture Anchor**. Show the 3 suggestions, click Insert on one.

> "These come from a verified scripture index plus the author's anchor list —
> the goal is zero hallucinated references, which matters enormously to this
> audience."

### e) Chat tab (11:15–11:30)

Switch to Chat, type one instruction: *"Make the closing paragraph more of a
prophetic declaration."* Let it respond briefly.

> "And there's a freeform assistant for anything else — same voice brief, just a
> conversational interface."

---

## 11:30–12:30 — Export + wrap-up

**Screen**: Click Export on the chapter or manuscript. Open the downloaded
`.docx` briefly to show formatting (title page, chapter headers, scripture
styling).

> "Export produces a clean, publisher-formatted Word document — title page,
> proper chapter breaks, scripture passages styled distinctly."

**Final 30 seconds — design rationale**:

> "On design — I deliberately avoided the typical 'AI tool' dark dashboard look.
> The palette is warm paper tones for anything an author reads or writes, a deep
> study-room charcoal for navigation, and a single accent color used sparingly —
> like sealing wax on a letter. Typography is a literary serif for headings, a
> manuscript serif for the actual writing surface, and a humanist sans for UI
> chrome. The goal was a study desk, not a SaaS dashboard — because that's what
> this tool actually is."

End on the Voice Evolution Timeline or the landing page — your choice.

---

## Recording checklist

- [ ] `LLM_PROVIDER=anthropic` set before recording
- [ ] Dramatiq worker running (so Voice DNA populates during the recording)
- [ ] Pre-written writing sample (100–150 words, apostolic/prophetic voice) ready to paste
- [ ] Pre-written testimony (80–120 words) ready to paste
- [ ] Browser zoomed appropriately for screen capture resolution
- [ ] Run `smoke_test.py` once beforehand on a throwaway account to confirm
      everything is warm (model loaded, DB connected) — cold starts add
      awkward pauses
- [ ] Have the architecture diagram/README open in a second tab for the 0:45–1:00 cut
- [ ] Practice the onboarding-to-preview transition once — that's the moment
      that needs to feel smooth

## Timing safety

If you're running long, cut from:
1. The placeholder second-chapter drag demo (skip entirely)
2. Shorten the "design rationale" close to 2 sentences
3. Speed up (2x in editing) the first 3–4 onboarding steps before signature phrases

Do **not** cut: the Live Voice Preview, the full chapter generation stream, or
the Weave In My Story moment — these three are your differentiation.
