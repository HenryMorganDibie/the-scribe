"""
Seed the scripture index with key apostolic/prophetic/Spirit-filled scriptures.
Run: python scripts/seed_scriptures.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

SCRIPTURES = [
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


async def seed():
    from app.db.session import AsyncSessionLocal
    from app.models import Scripture
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        for s in SCRIPTURES:
            existing = await db.execute(select(Scripture).where(Scripture.reference == s["reference"]))
            if existing.scalar_one_or_none():
                continue

            scripture = Scripture(
                book=s["book"],
                chapter=s["chapter"],
                verse_start=s["verse_start"],
                verse_end=s.get("verse_end"),
                reference=s["reference"],
                text_nkjv=s.get("text_nkjv"),
                themes=s["themes"],
                testament=s["testament"],
            )
            db.add(scripture)

        await db.commit()
        print(f"Seeded {len(SCRIPTURES)} scriptures.")


if __name__ == "__main__":
    asyncio.run(seed())
