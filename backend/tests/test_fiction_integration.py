"""Phase 3 against a real Postgres: timeline ordering, scene plans, quote verification route.

Skipped unless TEST_DATABASE_URL is set (see tests/test_delete_integration.py).
"""
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.api.routes import book_bible as bible_routes
from app.api.routes import progress as progress_routes
from app.api.routes import projects
from app.models import Chapter, Sermon, VoiceProfile
from app.services import book_bible
from tests.test_workspace_integration import (  # noqa: F401 — fixtures are used by name
    TEST_DATABASE_URL, _create, _seed, db, fake_embeddings, migrated_database,
)

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")


async def _event(db, s, title, order=None, when=None):
    return await bible_routes.create_entry(
        s.project.id,
        bible_routes.EntryCreate(kind="event", title=title, timeline_order=order, when_label=when),
        current_user=s.user, db=db,
    )


async def _set_pack(db, user_id, pack):
    db.add(VoiceProfile(user_id=user_id, pack=pack))
    await db.commit()


async def test_timeline_is_in_story_order_and_in_book_context(db):
    s = await _seed(db)
    await _event(db, s, "The flood", order=20)
    await _event(db, s, "Undated rumour")
    await _event(db, s, "Ada is born", order=10, when="1990")

    events = await book_bible.timeline(db, s.project.id)
    assert [e.title for e in events] == ["Ada is born", "The flood", "Undated rumour"]

    context = await book_bible.book_context(db, s.project, "anything at all")
    assert "TIMELINE" in context and "1. Ada is born (1990)" in context
    # Events appear once — in the timeline, not again among the relevant facts.
    assert context.count("The flood") == 1

    flood = next(e for e in events if e.title == "The flood")
    await bible_routes.update_entry(
        s.project.id, flood.id, bible_routes.EntryUpdate(timeline_order=5, when_label="Spring"),
        current_user=s.user, db=db,
    )
    assert [e.title for e in await book_bible.timeline(db, s.project.id)][0] == "The flood"


async def test_scene_plan_round_trips_through_chapter_update(db):
    s = await _seed(db)
    await projects.update_chapter(
        s.project.id, s.chapter.id,
        projects.ChapterUpdate(scenes=[{"title": "Crossing", "pov": "Ada"}, {"title": "Landfall"}]),
        current_user=s.user, db=db,
    )
    scenes = (await db.execute(select(Chapter.scenes).where(Chapter.id == s.chapter.id))).scalar_one()
    assert [x["title"] for x in scenes] == ["Crossing", "Landfall"] and scenes[0]["pov"] == "Ada"


async def test_verify_quotes_checks_linked_sources_and_source_entries(db):
    s = await _seed(db, content=(
        "<p>As Lee said, “teams who wrote things down shipped faster and argued less.”</p>"
        "<p>And: &quot;pricing is a story you tell about the value you create&quot;.</p>"
        "<p>Someone once said \"the future belongs to people who never ever sleep\".</p>"
    ))
    await _set_pack(db, s.user.id, "general")
    sermon = Sermon(user_id=s.user.id, title="Interview with Lee", source_type="text", status="complete",
                    transcript="We found that teams who wrote things down shipped faster and argued less.")
    db.add(sermon)
    await db.flush()
    s.project.source_sermon_ids = [sermon.id]
    await db.commit()
    await _create(db, s, "source", "Keynote notes", "Pricing is a story you tell about the value you create for people.")

    result = await progress_routes.verify_quotes(s.project.id, s.chapter.id, current_user=s.user, db=db)

    assert result["checked_sources"] == 2
    by_status = {q["status"]: q for q in result["quotes"]}
    assert by_status["verified"]["source_title"] in {"Interview with Lee", "Keynote notes"}
    assert [q["status"] for q in result["quotes"]] == ["verified", "verified", "not_found"]


async def test_verify_quotes_is_not_offered_for_fiction(db):
    s = await _seed(db, content='<p>"I will never go back to that island again," she said.</p>')
    await _set_pack(db, s.user.id, "fiction")
    with pytest.raises(Exception) as exc_info:
        await progress_routes.verify_quotes(s.project.id, s.chapter.id, current_user=s.user, db=db)
    assert getattr(exc_info.value, "status_code", None) == 400
