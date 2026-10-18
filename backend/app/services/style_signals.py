"""
Fiction style signals: point of view, tense and dialogue share of a passage.

Deliberately simple heuristics — word counts over the narration (dialogue
removed), not a parser. They're meant to catch drift ("this chapter slipped
into present tense"), and the UI labels them as approximate.
"""
import re

_DIALOGUE = re.compile(r'"[^"\n]{1,2000}"|“[^”]{1,2000}”')
_WORD = re.compile(r"[a-z']+")

_FIRST = {"i", "me", "my", "mine", "myself", "we", "us", "our", "ours", "i'm", "i'd", "i'll", "i've"}
_SECOND = {"you", "your", "yours", "yourself", "you're", "you'd", "you'll", "you've"}
_THIRD = {"he", "she", "him", "her", "his", "hers", "himself", "herself", "they", "them", "their", "theirs"}
_PAST = {"was", "were", "had", "did", "said", "went", "came", "saw", "thought", "knew", "felt", "took", "made", "got", "told", "looked", "turned", "asked"}
_PRESENT = {"is", "are", "am", "has", "does", "says", "goes", "comes", "sees", "thinks", "knows", "feels", "takes", "makes", "gets", "tells", "looks", "turns", "asks"}
_NOT_PAST_ED = {"need", "indeed", "seed", "speed", "bed", "red", "shed", "feed", "bleed", "breed", "proceed", "succeed", "exceed", "hundred", "sacred", "naked", "wicked"}


def fiction_signals(text: str) -> dict:
    dialogue_chars = sum(len(m.group(0)) for m in _DIALOGUE.finditer(text))
    total_chars = len(text.strip())
    narration = _DIALOGUE.sub(" ", text).lower()
    words = _WORD.findall(narration)

    first = sum(w in _FIRST for w in words)
    second = sum(w in _SECOND for w in words)
    third = sum(w in _THIRD for w in words)
    if not (first or second or third):
        pov = "unclear"
    elif second > first and second > third:
        pov = "second person"
    elif first >= 0.35 * (first + third):
        pov = "first person"
    else:
        pov = "third person"

    past = sum(w in _PAST or (w.endswith("ed") and len(w) > 4 and w not in _NOT_PAST_ED) for w in words)
    present = sum(w in _PRESENT for w in words)
    if past + present < 5:
        tense = "unclear"
    else:
        share = past / (past + present)
        tense = "past" if share >= 0.6 else "present" if share <= 0.4 else "mixed"

    return {
        "pov": pov,
        "tense": tense,
        "dialogue_ratio": round(dialogue_chars / total_chars, 3) if total_chars else 0.0,
    }
