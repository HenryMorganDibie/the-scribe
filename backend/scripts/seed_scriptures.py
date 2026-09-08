"""
Seed the scripture index: a small hand-curated list of apostolic/prophetic/
Spirit-filled scriptures (NKJV, with themes for matching), plus the full
KJV text of the whole Bible for verification/grounding.

KJV is public domain (unlike NKJV, which is under copyright and not cleared
for bulk storage at this scale) — see backend/scripts/data/kjv_verses.json,
sourced from https://github.com/farskipper/kjv (public domain, 1769 Oxford
edition text). That dataset marks KJV's own translator conventions inline:
"# " prefixes a new-paragraph verse, and "[word]" marks a word the
translators added for readability that isn't in the original-language text.
_clean_kjv_text() strips both markers for plain storage/display.

Run: python scripts/seed_scriptures.py
"""
import asyncio
import json
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
KJV_JSON_PATH = os.path.join(DATA_DIR, "kjv_verses.json")

# Order matters: index < len(OLD_TESTAMENT_BOOKS) => testament "old". Renamed
# "Solomon's Song" (the source dataset's book name) to the more familiar
# "Song of Solomon" for storage/display.
OLD_TESTAMENT_BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua",
    "Judges", "Ruth", "1 Samuel", "2 Samuel", "1 Kings", "2 Kings",
    "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah", "Esther", "Job",
    "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon", "Isaiah",
    "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
    "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai",
    "Zechariah", "Malachi",
]
NEW_TESTAMENT_BOOKS = [
    "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians",
    "2 Corinthians", "Galatians", "Ephesians", "Philippians", "Colossians",
    "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus",
    "Philemon", "Hebrews", "James", "1 Peter", "2 Peter", "1 John",
    "2 John", "3 John", "Jude", "Revelation",
]
BOOK_RENAME = {"Solomon's Song": "Song of Solomon"}
TESTAMENT_BY_BOOK = {b: "old" for b in OLD_TESTAMENT_BOOKS}
TESTAMENT_BY_BOOK.update({b: "new" for b in NEW_TESTAMENT_BOOKS})

_REF_RE = re.compile(r"^(.+) (\d+):(\d+)$")
_BRACKET_RE = re.compile(r"\[([^\]]*)\]")

CURATED_SCRIPTURES = [
    {"reference": "Isaiah 61:1-3", "book": "Isaiah", "chapter": 61, "verse_start": 1, "verse_end": 3,
     "themes": ["calling", "anointing", "healing", "freedom"], "testament": "old",
     "text_nkjv": "The Spirit of the Lord GOD is upon Me, because the LORD has anointed Me to preach good tidings to the poor; He has sent Me to heal the brokenhearted, to proclaim liberty to the captives, and the opening of the prison to those who are bound..."},
    {"reference": "Jeremiah 29:11", "book": "Jeremiah", "chapter": 29, "verse_start": 11,
     "themes": ["purpose", "hope", "future", "calling"], "testament": "old",
     "text_nkjv": "For I know the thoughts that I think toward you, says the LORD, thoughts of peace and not of evil, to give you a future and a hope."},
    {"reference": "Acts 1:8", "book": "Acts", "chapter": 1, "verse_start": 8,
     "themes": ["holy spirit", "power", "witness", "evangelism"], "testament": "new",
     "text_nkjv": "But you shall receive power when the Holy Spirit has come upon you; and you shall be witnesses to Me in Jerusalem, and in all Judea and Samaria, and to the end of the earth."},
    {"reference": "Joel 2:28-29", "book": "Joel", "chapter": 2, "verse_start": 28, "verse_end": 29,
     "themes": ["prophecy", "holy spirit", "dreams", "visions", "outpouring"], "testament": "old",
     "text_nkjv": "And it shall come to pass afterward that I will pour out My Spirit on all flesh; your sons and your daughters shall prophesy, your old men shall dream dreams, your young men shall see visions."},
    {"reference": "Romans 8:28", "book": "Romans", "chapter": 8, "verse_start": 28,
     "themes": ["faith", "purpose", "sovereignty", "trust"], "testament": "new",
     "text_nkjv": "And we know that all things work together for good to those who love God, to those who are the called according to His purpose."},
    {"reference": "Philippians 4:13", "book": "Philippians", "chapter": 4, "verse_start": 13,
     "themes": ["strength", "faith", "perseverance", "victory"], "testament": "new",
     "text_nkjv": "I can do all things through Christ who strengthens me."},
    {"reference": "John 10:10", "book": "John", "chapter": 10, "verse_start": 10,
     "themes": ["abundant life", "spiritual warfare", "identity"], "testament": "new",
     "text_nkjv": "The thief does not come except to steal, and to kill, and to destroy. I have come that they may have life, and that they may have it more abundantly."},
    {"reference": "Proverbs 4:7", "book": "Proverbs", "chapter": 4, "verse_start": 7,
     "themes": ["wisdom", "understanding", "knowledge"], "testament": "old",
     "text_nkjv": "Wisdom is the principal thing; therefore get wisdom. And in all your getting, get understanding."},
    {"reference": "Matthew 6:33", "book": "Matthew", "chapter": 6, "verse_start": 33,
     "themes": ["kingdom", "seeking God", "provision", "priority"], "testament": "new",
     "text_nkjv": "But seek first the kingdom of God and His righteousness, and all these things shall be added to you."},
    {"reference": "Hebrews 11:1", "book": "Hebrews", "chapter": 11, "verse_start": 1,
     "themes": ["faith", "belief", "hope", "substance"], "testament": "new",
     "text_nkjv": "Now faith is the substance of things hoped for, the evidence of things not seen."},
    {"reference": "1 Corinthians 14:1", "book": "1 Corinthians", "chapter": 14, "verse_start": 1,
     "themes": ["prophecy", "love", "spiritual gifts"], "testament": "new",
     "text_nkjv": "Pursue love, and desire spiritual gifts, but especially that you may prophesy."},
    {"reference": "Ephesians 2:10", "book": "Ephesians", "chapter": 2, "verse_start": 10,
     "themes": ["purpose", "creation", "good works", "identity"], "testament": "new",
     "text_nkjv": "For we are His workmanship, created in Christ Jesus for good works, which God prepared beforehand that we should walk in them."},
    {"reference": "2 Timothy 1:7", "book": "2 Timothy", "chapter": 1, "verse_start": 7,
     "themes": ["courage", "fear", "power", "love", "sound mind"], "testament": "new",
     "text_nkjv": "For God has not given us a spirit of fear, but of power and of love and of a sound mind."},
    {"reference": "Revelation 12:11", "book": "Revelation", "chapter": 12, "verse_start": 11,
     "themes": ["testimony", "overcoming", "spiritual warfare", "blood of Jesus"], "testament": "new",
     "text_nkjv": "And they overcame him by the blood of the Lamb and by the word of their testimony, and they did not love their lives to the death."},
    {"reference": "Isaiah 43:19", "book": "Isaiah", "chapter": 43, "verse_start": 19,
     "themes": ["new season", "restoration", "breakthrough", "revival"], "testament": "old",
     "text_nkjv": "Behold, I will do a new thing, now it shall spring forth; shall you not know it? I will even make a road in the wilderness and rivers in the desert."},
]


def _clean_kjv_text(raw: str) -> str:
    """Strip the source dataset's paragraph marker and italic-word brackets."""
    text = raw[2:] if raw.startswith("# ") else raw
    text = _BRACKET_RE.sub(r"\1", text)
    return text.strip()


def load_full_kjv() -> list[dict]:
    """Parse backend/scripts/data/kjv_verses.json into per-verse row dicts."""
    with open(KJV_JSON_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    rows = []
    for key, text in raw.items():
        m = _REF_RE.match(key)
        if not m:
            continue
        book, chapter, verse = m.group(1), int(m.group(2)), int(m.group(3))
        book = BOOK_RENAME.get(book, book)
        testament = TESTAMENT_BY_BOOK.get(book)
        if testament is None:
            continue
        rows.append({
            "book": book,
            "chapter": chapter,
            "verse_start": verse,
            "reference": f"{book} {chapter}:{verse}",
            "text_kjv": _clean_kjv_text(text),
            "testament": testament,
        })
    return rows


async def seed():
    from app.db.session import AsyncSessionLocal
    from app.models import Scripture
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        # Curated scriptures first — small enough for a per-row upsert, and
        # this establishes the NKJV text + themes for any reference the bulk
        # KJV import below might also touch.
        curated_added = 0
        for s in CURATED_SCRIPTURES:
            existing = (
                await db.execute(select(Scripture).where(Scripture.reference == s["reference"]))
            ).scalar_one_or_none()
            if existing:
                continue
            db.add(Scripture(
                book=s["book"],
                chapter=s["chapter"],
                verse_start=s["verse_start"],
                verse_end=s.get("verse_end"),
                reference=s["reference"],
                text_nkjv=s.get("text_nkjv"),
                themes=s["themes"],
                testament=s["testament"],
            ))
            curated_added += 1
        await db.commit()

        # Full KJV — fetch existing rows ONCE (not per-row) so repeat runs
        # (this script is in Render's preDeployCommand, so it runs on every
        # deploy) stay fast once the table is fully seeded.
        existing = {
            row.reference: row
            for row in (await db.execute(select(Scripture.id, Scripture.reference, Scripture.text_kjv))).all()
        }

        kjv_rows = load_full_kjv()
        new_rows = []
        kjv_backfill = []  # (id, text_kjv) for a curated row that predates this bulk import
        for r in kjv_rows:
            match = existing.get(r["reference"])
            if match is None:
                new_rows.append(r)
            elif match.text_kjv is None:
                kjv_backfill.append((match.id, r["text_kjv"]))

        CHUNK = 2000
        for i in range(0, len(new_rows), CHUNK):
            chunk = new_rows[i:i + CHUNK]
            db.add_all(Scripture(**row) for row in chunk)
            await db.commit()

        for id_, text_kjv in kjv_backfill:
            row = await db.get(Scripture, id_)
            row.text_kjv = text_kjv
        if kjv_backfill:
            await db.commit()

        print(f"Seeded {curated_added} new curated scriptures, {len(new_rows)} new full-KJV verses, "
              f"backfilled text_kjv on {len(kjv_backfill)} pre-existing curated rows "
              f"({len(kjv_rows) - len(new_rows) - len(kjv_backfill)} already fully seeded).")


if __name__ == "__main__":
    asyncio.run(seed())
