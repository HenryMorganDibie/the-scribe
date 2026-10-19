"""
Genre packs — the only place genre-specific wording lives.

The core product (voice profile, manuscripts, chapter memory, companion
chat, source ingestion) is genre-neutral. A pack supplies the words every
prompt uses for this kind of writer, plus feature switches such as scripture
verification. Existing DB columns are reused under pack-specific labels
(e.g. `theological_lens` is the "genre" for the general pack), so adding a
pack never moves data.

Packs: `general` (non-fiction — the default for new users), `fiction`, and
`christian` (the original pack).
"""
from dataclasses import dataclass
from typing import Literal, Optional

DEFAULT_PACK = "general"

# Request-validation type for API bodies that accept a pack id.
PackId = Literal["christian", "general", "fiction"]


@dataclass(frozen=True)
class Pack:
    id: str
    author_noun: str              # "a Christian author" / "an author"
    lens_label: str               # how `theological_lens` is labelled in prompts
    default_lens: str
    background_label: str         # how `ministry_background` is labelled
    default_audience: str
    rules_label: str              # how `theological_guardrails` is labelled
    default_rule: str
    uses_scripture: bool          # scripture index, anchor scriptures, translations
    reference_label: str          # chapter "anchor_scriptures" field label
    reference_rule: str           # citation rule injected into every voice brief
    story_label: str              # testimony vault entries
    story_examples: str           # what story mining looks for
    source_noun: str              # sermons table rows
    closing_instruction: str      # how a chapter should end
    chat_persona: str
    editor_role: str              # book-blueprint planner persona
    dna_subject: str              # "ministry DNA" / "writing DNA"
    focus_noun: str               # "{lens} ministry centered on X"
    preview_topic: str
    grounding_instruction: str    # chapter-generation rule for supporting each point
    section_noun: str             # what a chapter's planned units are called: "section" / "scene"
    is_fiction: bool = False      # scene plans, POV/tense/dialogue signals, story-craft prompts
    verifies_quotes: bool = False # quote verification against the book's sources


CHRISTIAN = Pack(
    id="christian",
    author_noun="a Christian author",
    lens_label="THEOLOGICAL LENS",
    default_lens="Spirit-filled",
    background_label="MINISTRY BACKGROUND",
    default_audience="Believers seeking deeper faith",
    rules_label="THEOLOGICAL GUARDRAILS",
    default_rule="Remain faithful to the stated theological lens and avoid asserting uncertain doctrine as fact.",
    uses_scripture=True,
    reference_label="Anchor Scriptures",
    reference_rule="Never cite a scripture not in the anchor list or verified index — hallucinated refs destroy trust.",
    story_label="Personal Story/Testimony",
    story_examples="healing testimonies, ministry experiences, leadership lessons, prophetic encounters, or personal struggles",
    source_noun="sermon",
    closing_instruction="Close with an invitation, declaration, or prophetic charge — consistent with their style",
    chat_persona="Be direct, warm, and ministerially aware.",
    editor_role="a Christian book-development editor",
    dna_subject="ministry DNA",
    focus_noun="ministry",
    preview_topic="the moment God calls someone into their purpose",
    grounding_instruction="Anchor each major point to scripture (from the list above only)",
    section_noun="section",
)

GENERAL = Pack(
    id="general",
    author_noun="an author",
    lens_label="GENRE / BOOK TYPE",
    default_lens="Non-fiction",
    background_label="AUTHOR BACKGROUND",
    default_audience="Thoughtful general readers",
    rules_label="STYLE RULES",
    default_rule="Stay consistent with the author's stated genre, audience and style; never present invented facts as true.",
    uses_scripture=False,
    reference_label="Key References",
    reference_rule="Never invent facts, statistics, quotes or citations — use only what the author has supplied, and flag anything that needs a source.",
    story_label="Personal Story / Anecdote",
    story_examples="personal anecdotes, case studies, client or field experiences, turning points, or lessons learned",
    source_noun="source",
    closing_instruction="Close in a way that fits the genre and the author's style — a takeaway, a turn, or a hook into the next chapter",
    chat_persona="Be direct, warm, and editorially sharp.",
    editor_role="a book-development editor",
    dna_subject="writing DNA",
    focus_noun="writing",
    preview_topic="a turning point that changes how someone sees their work or life",
    grounding_instruction="Ground each major point in the key references, stories and samples above — invent nothing",
    section_noun="section",
    verifies_quotes=True,
)

FICTION = Pack(
    id="fiction",
    author_noun="a novelist",
    lens_label="GENRE",
    default_lens="Literary fiction",
    background_label="AUTHOR BACKGROUND",
    default_audience="Readers of the genre",
    rules_label="STYLE RULES",
    default_rule="Keep point of view, tense and established story facts consistent; never break the story's internal logic.",
    uses_scripture=False,
    reference_label="Continuity Notes",
    reference_rule="Never contradict established story facts — characters, places, timeline; don't introduce major new named characters or places unless the brief asks for them.",
    story_label="Story Material",
    story_examples="anecdotes, vivid scenes, characters or real events that could inspire fiction",
    source_noun="source",
    closing_instruction="End on a hook, turn or open question that pulls the reader into the next chapter",
    chat_persona="Be direct, warm, and attentive to story craft — character, tension, pacing.",
    editor_role="a developmental editor for fiction",
    dna_subject="writing DNA",
    focus_noun="fiction",
    preview_topic="a character at the moment they make a choice they can't take back",
    grounding_instruction="Write in scenes: show, don't tell; keep point of view and tense consistent; let dialogue carry character",
    section_noun="scene",
    is_fiction=True,
)

PACKS: dict[str, Pack] = {p.id: p for p in (CHRISTIAN, GENERAL, FICTION)}


def get_pack(pack_id: Optional[str]) -> Pack:
    """Resolve a pack id, falling back to the default for unknown/missing ids."""
    if not isinstance(pack_id, str):
        return PACKS[DEFAULT_PACK]
    return PACKS.get(pack_id, PACKS[DEFAULT_PACK])


def pack_for(profile) -> Pack:
    """The pack for a voice profile (or anything with a `.pack` attribute)."""
    return get_pack(getattr(profile, "pack", None))
