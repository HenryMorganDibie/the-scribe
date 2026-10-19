"""Ministry DNA Report: exact metrics from the DB + a short cached AI narrative."""
from collections import Counter
from app.services.ai.llm_client import get_llm_client
from app.services.packs import Pack, get_pack, pack_for


def compute_dna_metrics(profile, sermons: list, versions: list) -> dict:
    """Compute deterministic metrics from the profile, sermons, and voice versions."""
    corpus = "\n".join((s.transcript or "") for s in sermons).lower()

    anchors = profile.anchor_scriptures or []
    phrases = profile.signature_phrases or []

    # Most-quoted scriptures: mentions of the ref string across the corpus
    scripture_counts = []
    for s in anchors:
        if isinstance(s, dict) and s.get("ref"):
            ref = s["ref"]
            count = corpus.count(ref.lower())
            scripture_counts.append({"ref": ref, "count": count})
    scripture_counts.sort(key=lambda x: x["count"], reverse=True)

    # Most-used phrases: occurrences across the corpus
    phrase_counts = [
        {"phrase": p, "count": corpus.count(p.lower())}
        for p in phrases
    ]
    phrase_counts = [pc for pc in phrase_counts if pc["count"] > 0]
    phrase_counts.sort(key=lambda x: x["count"], reverse=True)

    # Recurring themes: tally across anchor scripture themes
    theme_counter = Counter()
    for s in anchors:
        if isinstance(s, dict):
            for t in (s.get("themes") or []):
                theme_counter[t] += 1
    top_themes = [{"theme": t, "count": c} for t, c in theme_counter.most_common()]

    # Dominant focus ("ministry_focus" is kept as the API key for compatibility)
    pack = pack_for(profile)
    lens = profile.theological_lens or pack.default_lens
    focus = lens
    if top_themes:
        focus = f"{lens} {pack.focus_noun} centered on {top_themes[0]['theme']}"

    # Voice change over time
    timeline = [
        {
            "version": v.version_number,
            "cadence_score": v.cadence_score,
            "phrase_count": v.phrase_count,
            "scripture_count": v.scripture_count,
        }
        for v in sorted(versions, key=lambda x: x.version_number)
    ]

    return {
        "top_scriptures": scripture_counts[:10],
        "top_phrases": phrase_counts[:10],
        "top_themes": top_themes[:10],
        "ministry_focus": focus,
        "timeline": timeline,
    }


async def generate_dna_narrative(metrics: dict, pack: Pack | None = None) -> str:
    """Write a short narrative summary of the computed metrics."""
    pack = pack or get_pack(None)
    scriptures = (
        f"Most-quoted scriptures: {', '.join(s['ref'] for s in metrics.get('top_scriptures', [])[:5]) or 'none yet'}\n"
        if pack.uses_scripture else ""
    )
    prompt = f"""Write a warm, 120-150 word narrative summarizing the {pack.dna_subject} of {pack.author_noun}.
Use these computed facts; do not invent numbers.

Dominant focus: {metrics.get('ministry_focus')}
Top themes: {', '.join(t['theme'] for t in metrics.get('top_themes', [])[:5]) or 'none yet'}
{scriptures}Signature phrases: {', '.join(p['phrase'] for p in metrics.get('top_phrases', [])[:5]) or 'none yet'}

Address the author as "you". No preamble — just the paragraph."""
    result = await get_llm_client().complete(messages=[{"role": "user", "content": prompt}], max_tokens=300)
    return result.text.strip()
