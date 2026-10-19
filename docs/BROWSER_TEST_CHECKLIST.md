# The Scribe — Browser test pass

A click-through of every flow, before inviting more writers. Tick items as you go. When something
fails, write a short note under it (see "Reporting a failure" at the bottom) and keep going.

Items marked **(regression)** check a bug that was fixed during the review and phases 0–3 —
they're the ones most worth confirming.

---

## Setup

- [ ] Backend running and migrated to head (`alembic upgrade head` — latest is `0011`)
- [ ] Frontend running (locally: backend on port 8001, frontend on port 5174 — or use the deployed Vercel URL)
- [ ] Browser devtools open on the **Network** and **Console** tabs (watch for red requests and errors)
- [ ] Have ready: a short PDF, a DOCX, a `.txt` or `.md` file, a short audio clip (`.mp3`/`.m4a`), and a video file (`.mp4`)
- [ ] Use **three new accounts**, one per book type: **Non-fiction**, **Fiction**, **Christian**
- [ ] If you have one, also an **existing account from before Phase 0** (it should come through as Christian)

---

## 1. Public pages and sign-in

- [ ] Logged out, open `/` — the landing page shows "AI workspace… finish your book" and **does not reload in a loop** **(regression)**
- [ ] Open `/login` and `/signup` while logged out — both stay put, no reload loop **(regression)**
- [ ] Log in with a **wrong password** — you get an error message; the page does **not** reload and the form keeps your email **(regression)**
- [ ] Sign up with a mixed-case email, e.g. `Test.User@Example.com` — then log out and log in as `test.user@example.com` — it works **(regression)**
- [ ] Try signing up again with the same email in different case — "Email already registered"
- [ ] Password under 15 characters is rejected with a clear message
- [ ] (If configured) Google sign-in creates an account and lands on onboarding
- [ ] Log out — you land on `/`, and opening `/dashboard` sends you to `/login`

## 2. Onboarding (do once per book type)

- [ ] First screen asks "What are you writing?" with three choices: **Non-fiction, Fiction, Christian writing**
- [ ] Back link on the next screen returns to the choice

**Non-fiction account — "Interview me"**
- [ ] Questions are about genre (no "Fiction" option), background, reader, tones, phrases, style rules, samples, one story
- [ ] **Style rules** step can be skipped (Next is enabled with nothing added)
- [ ] After a few steps the **Live Voice Preview** writes a paragraph — no theology, scripture or "God" in it
- [ ] The preview text has no stray `data:` prefixes or broken lines **(regression)**
- [ ] Finish — lands on the Dashboard; nav shows **Sources · Stories · Voice DNA**

**Fiction account — "Interview me"**
- [ ] Questions include fiction genres and **"How do you usually tell the story?"** (POV and tense)
- [ ] Preview reads like fiction
- [ ] Finish — nav shows **Research · Story Ideas · Voice DNA**
- [ ] Voice Profile page lists **"Point of view and tense: …"** as the first style rule

**Christian account — "I have sermons"**
- [ ] Choosing the sermon-first path skips the interview and lands on the Sermons page
- [ ] Nav shows **Sermons · Testimonies · Ministry DNA**

**Old account (if you have one)**
- [ ] Logs in and still sees the Christian labels and tools

## 3. Sources / Sermons page

- [ ] Upload a **PDF**, a **DOCX**, a **TXT or MD** file, and an **audio** clip — each shows a status that moves to *complete*
- [ ] Upload a **video** — rejected with a clear "extract the audio first" message
- [ ] Paste a transcript instead of a file — processes to *complete*
- [ ] A completed source shows "+N phrases · N stories"
- [ ] Delete a source — it disappears
- [ ] Labels match the book type (Sources / Research / Sermons)

## 4. Stories / Testimonies page

- [ ] Suggested stories mined from your sources appear under "Suggested from your …" — **Approve** moves one into the bank, **Dismiss** removes it
- [ ] Add a story by hand; edit it; delete it
- [ ] Wording matches the pack (Story Bank / Story Ideas / Testimony Vault)

## 5. Voice Profile and DNA

- [ ] Voice Profile shows the ghost brief, cadence, phrases; **Christian only:** translation and anchor scriptures
- [ ] **Edit Voice** → change **Book type** (e.g. Non-fiction → Fiction) and save — the **nav labels change immediately** without a reload
- [ ] Change it back
- [ ] Ministry DNA / Voice DNA page loads a narrative; the scripture list only appears for Christian

## 6. Manuscripts

- [ ] Create a manuscript — the genre list matches the book type
- [ ] **Build from Sources/Sermons** with two completed sources — a chapter blueprint is created and opens
- [ ] Rename / delete a manuscript from the list
- [ ] Delete a manuscript that has chapters you've generated with AI — it deletes without an error **(regression)**

## 7. Manuscript Studio (one book)

**Progress**
- [ ] Progress panel shows words, a 14-day chart, today's words, streak and chapter stages
- [ ] **Goals** → set target words, daily goal and a deadline → panel shows pace ("about N words a day")
- [ ] Clear a goal (empty the field) — it disappears
- [ ] **What's next** lists sensible steps; chapter-specific ones link to the chapter

**Chapters**
- [ ] Add a chapter; drag to reorder; the order sticks after a reload
- [ ] Change a chapter's stage from the row (Outline → Drafted → Revised → Done) — Progress updates
- [ ] Delete a chapter that has AI-generated text and a voice check — no error **(regression)**

**Book style & sources**
- [ ] **Book style → Edit**: set a reader, a rule and notes → saved and shown
- [ ] **Book sources → Manage**: link two sources → they show as linked

**Repetition**
- [ ] With 2+ saved chapters that share a paragraph, **Scan manuscript** finds the pair; with none, says nothing was found

## 8. Book Bible

- [ ] Open from **Book Bible** in the studio
- [ ] Add one of each kind: Character, Place, Term, **Timeline event**, Source, Research, Note
- [ ] Timeline events have **When** and **Order** fields; the Timeline filter lists them in order with `#N` and the when-label
- [ ] Edit an event's order — the list re-orders
- [ ] Attach a note to one chapter ("Only chapter …") — it shows the chapter name
- [ ] Delete an entry

## 9. Chapter editor (try with each book type)

**Writing and saving**
- [ ] Type, wait a few seconds — "Saving" appears, then the text survives a reload
- [ ] Type something, then **immediately** click "Back to manuscript" and re-open the chapter — the last words are still there **(regression)**
- [ ] Change the stage from the header dropdown — a "Marked …" toast appears

**AI actions**
- [ ] **Generate chapter** on an empty chapter — text streams in
- [ ] **Generate chapter** on a chapter with text — asks to confirm first, mentioning History
- [ ] **Continue writing** and **Weave in my story** add text in your voice
- [ ] **Voice check** shows a real percentage — **not "NaN%"** **(regression)**
- [ ] **Fiction only:** voice check also shows "Narration (approx.): first/third person · past/present tense · N% dialogue"
- [ ] **Check Consistency** with a deliberate contradiction (e.g. a character's age differs from the bible) — the issue is reported with a quote from your chapter
- [ ] **Non-fiction only:** **Verify Quotes** — a quote copied from a linked source shows *Verified*; a slightly changed one shows *Wording differs* with the source's wording; an invented one shows *No source found*
- [ ] **Christian only:** **Suggest Scripture Anchor** returns verses; this button is **absent** for Non-fiction and Fiction
- [ ] **Chat** tab answers; chat suggestions contain nothing pack-specific for non-Christian books

**Plan tab**
- [ ] Edit the intent and key points → **Save plan** → reload → still there
- [ ] Add 2–3 scenes (Fiction: with POV and setting) / sections (Non-fiction), reorder with the arrows, save
- [ ] Generate the chapter — it follows the plan; for Fiction, scenes are separated by `* * *`

**Notes tab**
- [ ] Add a note and a research item for this chapter — they appear; the book bible shows them attached to this chapter

**History tab**
- [ ] After generating over an existing draft, History shows a **"Before AI draft"** version
- [ ] **Preview** shows the old text; **Restore** asks to confirm, brings it back, and adds a **"Before restore"** version

## 10. Companion Chat

- [ ] Suggested prompts include **"What should I work on next?"** — the answer reflects your actual progress and next steps
- [ ] Ask "Which chapter discusses …?" — the answer cites chapters, and the citations link correctly
- [ ] Reload the page — your conversation history is still there, newest messages at the bottom

## 11. Exports

- [ ] Export the manuscript as **.docx** and **.pdf** — both download and open
- [ ] Give a book a title with smart quotes or an em dash (e.g. `Faith’s Reward — Part 1`) and export — download works, no error **(regression)**
- [ ] Export a single chapter from the editor (.docx and .pdf)

## 12. Sessions, limits and errors

- [ ] **Two tabs:** open the editor in tab A, reload tab B, then type and save in tab A — **saves still work, no 403** **(regression)**
- [ ] After logging out in one tab, actions in the other tab send you to `/login`
- [ ] (Optional, if you can lower `AI_DAILY_REQUEST_LIMIT` to e.g. 3) Exceed the AI limit — every AI action shows **"Daily usage limit reached…"** instead of silently doing nothing **(regression)**
- [ ] (Optional, if you can stop the AI provider or disconnect the network) Run an AI action — you get a toast saying the assistant couldn't finish, not a blank result

## 13. Background jobs

- [ ] Save a chapter with **Save**, wait ~30s, then ask Companion Chat about that chapter — it knows the new text
- [ ] (Optional) Stop the backend in the middle of a source upload, start it again, wait — after 30 minutes that upload shows **failed** with "please upload this file again" instead of spinning forever

## 14. Mobile width

- [ ] With the browser narrowed to phone width (or devtools device mode): the nav drawer opens and closes; Dashboard, Studio, Book Bible and Editor are usable; the editor's AI sidebar opens as a panel

---

## Reporting a failure

Under the failing item, note:

- **Account / book type** used
- **What you did** (the click path) and **what happened vs. what you expected**
- Any **red request** in the Network tab: its URL, status code and response body
- Any **Console** error text
- A screenshot if it's visual

Then add a line to `docs/ROADMAP.md` under Hardening for anything that needs fixing.
