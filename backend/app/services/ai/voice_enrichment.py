"""Extract voice DNA from arbitrary text and additively merge it into a VoiceProfile."""
import json
from app.services.ai.llm_client import get_llm_client
from app.services.ai.json_utils import strip_json_fences


def _parse_dna_json(raw: str) -> dict:
    text = strip_json_fences(raw)
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
        existing = profile.cadence_score if profile.cadence_score is not None else new_cadence
        profile.cadence_score = round((existing + new_cadence) / 2, 3)

    # Voice summary — replace with the freshly generated one if present
    if new_dna.get("voice_summary"):
        profile.voice_summary = new_dna["voice_summary"]

    return {"phrases_added": len(added_phrases), "scriptures_added": len(added_scriptures)}
