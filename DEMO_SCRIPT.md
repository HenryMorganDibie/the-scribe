# The Scribe — Demo Video Storyboard

Target length: 13–15 minutes (hard limit: 15). Goal: prove this is a real,
production-architected system — not a prompt wrapper — while hitting every
bonus-point criterion (aesthetics, creative AI integration, thought process,
design system).

Record with `LLM_PROVIDER=anthropic` for this session — Claude's voice
consistency over long generations is the difference that will show, and this
is the version reviewers should see.

**This script has grown since the product did.** The build now spans nine
distinct AI-powered capabilities. Fifteen minutes cannot deep-dive all of
them — so this version groups related features into single beats and cuts
anything that doesn't change a reviewer's mind. If you're short on time
during recording, see the **Timing safety** cut list at the end before you
cut anything not listed there.

---

## 0:00–0:45 — Cold open: the problem statement

**Screen**: Landing page (`/`).

**Say**:
> "Most AI writing tools work the same way: paste a sample, generate text. The
> problem is that a generic AI cannot write someone's testimony, cannot cite the
> scriptures they actually return to, and cannot sound like the person standing
> behind their pulpit. The Scribe is built around a different idea — it learns
> an author's voice first, from everything they've already preached and
> written, and only then writes in it. I'll show you the whole pipeline: from a
> raw sermon recording to a finished, voice-matched manuscript chapter."

Scroll the landing page slowly — let the capability list be visible for a
few seconds. This previews the whole demo and shows you planned the
architecture before the UI.

---

## 0:45–1:00 — Architecture in 15 seconds

**Screen**: Cut to the architecture diagram from the README (markdown
preview or a slide).

**Say**:
> "Quickly — the stack. React frontend, FastAPI backend, Postgres with
> pgvector for retrieval, Claude for generation. Every generation request —
> chapter drafts, the companion chat, voice scoring — gets built from the
> same place: a 'voice brief' assembled from the author's profile, their
> retrieved sermons and writing samples, and their testimonies. I'll show you
> each piece as it gets used."

Keep this tight — one breath, then move on.

---

## 1:00–3:30 — Sign up + Voice Onboarding + Live Voice Preview (the wow moment)

**Screen**: `/signup` → `/onboarding`

**Say** (while filling the first couple of steps quickly):
> "I'll sign up as a fictional author — a pastor with a prophetic, exhortative
> voice."

Move through the early steps at a brisk pace (speed this up in editing, and
say so on screen: "speeding through the first few steps").

**Slow down at "Signature Phrases."** Type in 2–3 real phrases, like:
- "This is your set time"
- "Let that sink in"
- "Can I be honest with you?"

**Say**: "Now watch the right panel."

Click Next — **let the Live Voice Preview stream fully on screen, in real
time, without cutting**. This is one of the two most important moments in
the video.

> "That paragraph was generated from nothing but the phrases I just typed
> and the theological lens I picked two steps ago. The author watches their
> own voice come into focus before they've even finished the interview."

Continue through anchor scriptures and one short writing sample (prepared
in advance, 100–150 words of sermon-style text), letting the preview
refresh once more — narrate over it rather than waiting in silence.

Complete onboarding.

> "Two background jobs just fired: one extracts a full voice DNA profile —
> signature phrases, cadence, style, a voice summary. The other embeds that
> writing sample into a vector store so it can be retrieved by relevance
> later, not just dumped into every prompt."

---

## 3:30–5:00 — Sermon Upload & Automatic Knowledge Extraction

**Screen**: `/sermons` → upload

This is your second major differentiator and needs real screen time.

**Say**:
> "Most authors don't have polished writing samples sitting around — they
> have years of preached sermons. So instead of asking for more typing, The
> Scribe can ingest the actual sermons."

Upload a short pre-prepared sermon file (PDF, DOCX, or a short audio clip —
audio is the more impressive choice if your file is short, since it shows
transcription happening). Narrate while it processes:

> "This is being transcribed if it's audio, then run through the same voice
> extraction pipeline as onboarding — pulling recurring phrases, anchor
> scriptures, and theological emphasis straight out of real preaching, not a
> curated sample."

Show the result — extracted phrases/scriptures appearing, and the sermon
listed with its processed status.

> "And it doesn't stop at voice — it also reads the sermon for personal
> stories."

---

## 5:00–6:00 — Automatic Testimony Mining

**Screen**: Testimony suggestions from the sermon (or `/testimonies` if
mining surfaces there)

**Say**:
> "The same sermon gets scanned for testimonies — healing stories, ministry
> experiences, prophetic encounters — and The Scribe suggests them for the
> Testimony Vault. One click to approve, instead of an author manually
> transcribing their own story from memory."

Click approve on one suggested testimony. Keep this beat tight — it's a
strong feature but a quick one to show.

---

## 6:00–6:45 — Ministry DNA Report

**Screen**: `/ministry-dna`

**Say**:
> "Once there's enough ingested material — sermons, samples, testimonies —
> The Scribe can generate a full Ministry DNA report: most recurring themes,
> most-quoted scriptures, dominant ministry focus, and how voice and emphasis
> have shifted over time."

Show the metrics, the narrative summary, and the timeline chart if populated.

> "This is the kind of self-awareness about your own ministry voice that
> would normally take a research assistant weeks to compile."

---

## 6:45–7:45 — Voice DNA + Voice Evolution Timeline

**Screen**: `/voice-profile`

> "Here's the full Voice DNA page — ghost brief, cadence, signature phrases,
> anchor scriptures with themes, style tags, all extracted, not guessed."

Point at each section briefly as mentioned.

**Then the Voice Evolution Timeline**:

> "Every time this profile changes — onboarding, a new sermon, an accepted
> edit in a chapter — a new version gets snapshotted, like a commit history.
> The system is meant to get to know the author better the more they use it,
> not stay frozen at signup."

---

## 7:45–8:45 — Manuscript Studio + create a chapter

**Screen**: `/projects` → create new → `/projects/:id`

Create a manuscript live: title, genre, theme, one chapter with a title +
intent + key points + an anchor scripture.

> "I'm creating a short manuscript with one chapter to demo the rest of the
> pipeline."

---

## 8:45–11:30 — Chapter Editor: generation + voice tools

**Screen**: Chapter Editor for Chapter 1

### a) Generate Chapter Draft (8:45–9:45)

Click **Generate Chapter Draft in My Voice**. Let it stream for a while on
screen — don't skip this.

> "This pulls the full voice brief, runs a similarity search against
> everything I've fed it — the writing sample, the sermon, testimonies — for
> what's actually relevant to this chapter's intent, checks memory of any
> prior chapters, and writes in my preferred translation citing only
> verified scriptures."

Show the beginning and end of the stream live; you can fast-forward the
middle in editing.

### b) Weave In My Story (9:45–10:30)

Click **Weave In My Story**, pick a testimony (ideally the one mined from
the sermon earlier — ties the whole demo together).

> "This is the testimony the system found in my sermon a few minutes ago,
> now being woven into the chapter as a natural transition — not pasted in
> as a block, but retrieved because it's thematically relevant to this exact
> chapter."

### c) Check My Voice (10:30–11:00)

Click **Check My Voice**. Show the score and feedback.

> "This scores the generated text against my voice profile and gives
> specific feedback on anything that drifted."

### d) Suggest Scripture Anchor (11:00–11:30)

Click **Suggest Scripture Anchor**. Show suggestions, insert one.

> "These come from a verified scripture index plus my anchor list — the goal
> is zero hallucinated references."

---

## 11:30–13:00 — Manuscript Companion Chat + Voice Drift Analytics

This is the newest pair of features and closes out the AI-capability portion
of the demo strongly — don't rush it, but keep both beats brisk.

### a) Manuscript Companion Chat (11:30–12:30)

**Screen**: Click "Companion Chat" from Manuscript Studio.

> "Separate from the chapter assistant, this one has read the entire
> manuscript — every chapter, not just the one I'm editing."

Click one of the suggested prompts, e.g. *"Where have I used this scripture
before?"* or type a custom question referencing the chapter you just wrote.
Let it stream, then **click one of the chapter citation chips** under the
answer to show it jumps straight to that chapter.

> "It's retrieving across the whole book via the same vector search, plus a
> structural map of every chapter — title, status, scriptures — so it can
> answer things like 'have I covered this already' or 'which chapter
> discusses X' even when the wording doesn't match closely enough for
> semantic search alone."

### b) Voice Drift Analytics (12:30–13:00)

**Screen**: Voice DNA page → "Drift Analytics"

> "And this tracks voice match over time — not just one score, but cadence,
> scripture usage, and phrase usage as separate dimensions, charted across
> every check I run."

Show the trend card and the score-over-time chart. If you only have one
data point so far, narrate what it will become rather than dwelling on an
empty chart: "Right now there's one data point — this fills in as I write
more and run more checks."

---

## 13:00–14:00 — Export + design rationale

**Screen**: Click Export on the chapter or manuscript. Open the downloaded
`.docx` briefly to show formatting.

> "Export produces a clean, publisher-formatted Word document — title page,
> proper chapter breaks, scripture passages styled distinctly."

**Final 30–45 seconds — design rationale**:

> "On design — I deliberately avoided the typical 'AI tool' dark dashboard
> look. The palette is warm paper tones for anything an author reads or
> writes, a deep study-room charcoal for navigation, and a single accent
> color used sparingly — like sealing wax on a letter. The goal was a study
> desk, not a SaaS dashboard, because that's what this tool actually is."

End on the Voice Evolution Timeline, the Ministry DNA report, or the landing
page — your choice of strongest closing visual.

---

## Recording checklist

- [ ] `LLM_PROVIDER=anthropic` set before recording
- [ ] Pre-written writing sample (100–150 words, apostolic/prophetic voice) ready to paste
- [ ] One short sermon file ready to upload (audio preferred if short — shows transcription; PDF/DOCX as fallback)
- [ ] Pre-written testimony available as a fallback if sermon mining doesn't surface one cleanly
- [ ] Browser zoomed appropriately for screen capture resolution
- [ ] Confirm Render is deployed from the correct branch (`main`) and migrations are current before recording — see README's "Deploying" section
- [ ] Run through the full flow once, off-camera, to confirm everything is warm (no cold-start pauses) and that there's at least one chapter with a voice-check score logged before recording Drift Analytics
- [ ] Have the architecture diagram/README open in a second tab for the 0:45–1:00 cut
- [ ] Practice the onboarding-to-preview transition once — that moment needs to feel smooth

## Timing safety

This script is already tight at 13–14 minutes with nine features covered. If
you're running long, cut from, in this order:

1. Shorten the "design rationale" close to 1–2 sentences
2. Speed up (2x in editing) the early onboarding steps before signature phrases
3. Trim the Ministry DNA beat to 30 seconds — show the report, skip narrating every metric
4. Trim Testimony Mining to showing the suggestion + one click approve, no extra narration
5. If truly desperate: cut Voice Drift Analytics to a 15-second flash of the chart with one sentence, since it's the newest/smallest feature relative to the others

**Do not cut**: the Live Voice Preview, the Sermon Upload extraction moment,
the full chapter generation stream, the Weave In My Story moment, or the
Manuscript Companion Chat citation-click. These five are what separate this
from "I called an LLM API in a loop" — they are the demo.
