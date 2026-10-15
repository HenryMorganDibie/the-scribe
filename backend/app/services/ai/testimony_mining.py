"""Mine personal stories / testimonies from a sermon transcript."""
import json
from app.services.ai.llm_client import get_llm_client
from app.services.ai.json_utils import strip_json_fences
from app.services.packs import Pack, get_pack


def _parse_testimonies(raw: str) -> list[dict]:
    text = strip_json_fences(raw)
    try:
        data = json.loads(text)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    cleaned = []
    for item in data:
        if isinstance(item, dict) and item.get("title") and item.get("story"):
            cleaned.append({
                "title": str(item["title"]),
                "story": str(item["story"]),
                "themes": item.get("themes") if isinstance(item.get("themes"), list) else [],
            })
    return cleaned


async def mine_testimonies(transcript: str, pack: Pack | None = None) -> list[dict]:
    """Extract candidate personal stories from a transcript. Returns [] on failure."""
    pack = pack or get_pack(None)
    prompt = f"""Read this {pack.source_noun} transcript and identify personal stories the author tells —
{pack.story_examples}.

TRANSCRIPT:
{transcript[:5000]}

Return a JSON array (max 5). Each item:
{{"title": "short title", "story": "the story retold in 2-4 sentences", "themes": ["theme1", "theme2"]}}

Only include genuine personal stories or experiences, not general teaching or explanation. If none, return [].
Return ONLY valid JSON. No markdown, no explanation."""
    result = await get_llm_client().complete(messages=[{"role": "user", "content": prompt}], max_tokens=1200)
    return _parse_testimonies(result.text)
