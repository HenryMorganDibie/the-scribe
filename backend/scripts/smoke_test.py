"""
End-to-end smoke test for The Scribe API.

Runs the full user journey against a running backend:
signup → onboarding → (background DNA extraction) → create project →
create chapter → generate chapter (streamed) → voice check → export.

Usage:
    cd backend
    source venv/bin/activate
    python scripts/smoke_test.py

Set LLM_PROVIDER=groq in your .env first if you want this to run for free
against Groq instead of Anthropic. The script prints which provider is active.

This is also useful as a *demo script* — run it on screen while narrating,
since it exercises every major feature in the right order with readable output.
"""
import asyncio
import sys
import time
import httpx

BASE_URL = "http://localhost:8000/api"

SAMPLE_WRITING = """
Let that sink in for a moment. You were not an accident. Before the foundations
of the earth were laid, He saw you — He knew the wilderness you would walk through,
and He called you anyway. This is your set time. Not next year. Not when you feel
ready. Now. Isaiah 61 says the Spirit of the Lord is upon you — to bind up the
brokenhearted, to proclaim liberty. That liberty starts with you believing it's
for you. Can I be honest with you? Most of us are waiting for permission that was
already given at the cross.
"""

TEST_USER = {
    "email": f"demo-{int(time.time())}@thescribe.test",
    "password": "demopass123",
    "full_name": "Demo Author",
}

ONBOARDING_DATA = {
    "ministry_background": "I pastor a small congregation focused on prophetic discipleship and have been in ministry for 8 years.",
    "theological_lens": "Prophetic",
    "target_audience": "Believers who feel called to something greater but are stuck in seasons of waiting.",
    "tone_preferences": ["Teaching", "Exhortation", "Prophetic Declaration"],
    "preferred_translation": "NKJV",
    "signature_phrases": ["This is your set time", "Let that sink in", "Can I be honest with you?"],
    "anchor_scriptures": ["Isaiah 61:1-3", "Jeremiah 29:11", "Joel 2:28-29"],
    "writing_samples": [SAMPLE_WRITING],
}


def log(step: str, detail: str = ""):
    print(f"\n{'='*60}")
    print(f"  {step}")
    if detail:
        print(f"  {detail}")
    print("=" * 60)


async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:

        # 1. Signup
        log("1/8  Signing up demo author", TEST_USER["email"])
        r = await client.post("/auth/signup", json=TEST_USER)
        r.raise_for_status()
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("✓ Account created. Token acquired.")

        # 2. Complete onboarding
        log("2/8  Completing voice onboarding interview")
        r = await client.post("/onboarding/complete", json={"data": ONBOARDING_DATA}, headers=headers)
        r.raise_for_status()
        print("✓ Onboarding complete.", r.json().get("message", ""))

        # 3. Live voice preview (SSE)
        log("3/8  Streaming live voice preview")
        async with client.stream("POST", "/onboarding/preview", headers=headers) as resp:
            preview_text = ""
            async for line in resp.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    preview_text += line[6:]
        print("✓ Preview generated:\n")
        print(f"  \"{preview_text.strip()}\"")

        # 4. Wait briefly for background voice DNA extraction (if worker running)
        log("4/8  Checking voice profile (background DNA extraction)")
        await asyncio.sleep(2)
        r = await client.get("/voice-profile", headers=headers)
        profile = r.json()
        if profile.get("voice_summary"):
            print("✓ Voice DNA extracted:")
            print(f"  Cadence score: {profile.get('cadence_score')}")
            print(f"  Signature phrases: {profile.get('signature_phrases')}")
        else:
            print("ℹ Voice DNA not yet processed — start the Dramatiq worker:")
            print("  dramatiq app.workers.tasks")
            print("  (Generation below will still work using raw onboarding data.)")

        # 5. Create project
        log("5/8  Creating manuscript")
        r = await client.post("/projects", json={
            "title": "Called: Finding Your Voice in the Wilderness",
            "genre": "prophetic",
            "theme": "God uses wilderness seasons to prepare the called, not punish them.",
            "target_chapters": 5,
        }, headers=headers)
        r.raise_for_status()
        project_id = r.json()["id"]
        print(f"✓ Project created: {project_id}")

        # 6. Create chapter
        log("6/8  Adding Chapter 1")
        r = await client.post(f"/projects/{project_id}/chapters", json={
            "title": "The Wilderness Season",
            "chapter_number": 1,
            "intent": "Help the reader see their current hardship as preparation, not punishment.",
            "key_points": [
                "God uses wilderness seasons to prepare leaders",
                "Isolation is not abandonment",
                "The set time is closer than it feels",
            ],
            "anchor_scriptures": ["Isaiah 61:1-3", "Jeremiah 29:11"],
            "testimony_ids": [],
        }, headers=headers)
        r.raise_for_status()
        chapter_id = r.json()["id"]
        print(f"✓ Chapter created: {chapter_id}")

        # 7. Generate chapter (streamed)
        log("7/8  Generating chapter draft in author's voice (this is the main feature)")
        start = time.time()
        full_text = ""
        async with client.stream("POST", "/generate/chapter", json={"chapter_id": chapter_id}, headers=headers) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    import json as json_mod
                    try:
                        chunk = json_mod.loads(line[6:])
                        if "text" in chunk:
                            full_text += chunk["text"]
                            print(chunk["text"], end="", flush=True)
                    except Exception:
                        pass
        elapsed = time.time() - start
        print(f"\n\n✓ Generated {len(full_text.split())} words in {elapsed:.1f}s")

        # 8. Voice check + export
        log("8/8  Running voice match check + exporting manuscript")
        r = await client.post("/generate/voice-check", json={"chapter_id": chapter_id, "text": full_text}, headers=headers)
        r.raise_for_status()
        check = r.json()
        print(f"✓ Voice match: {round(check['voice_match_score'] * 100)}% ({check['grade']})")
        print(f"  Feedback: {check['feedback']}")

        r = await client.post(f"/export/project/{project_id}", headers=headers)
        r.raise_for_status()
        with open("/tmp/the-scribe-demo-export.docx", "wb") as f:
            f.write(r.content)
        print(f"✓ Manuscript exported to /tmp/the-scribe-demo-export.docx ({len(r.content)} bytes)")

        log("DONE — full journey completed successfully")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except httpx.ConnectError:
        print("\n✗ Could not connect to http://localhost:8000")
        print("  Start the backend first: uvicorn app.main:app --reload")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"\n✗ HTTP {e.response.status_code}: {e.response.text}")
        sys.exit(1)
