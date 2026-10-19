"""Finishing tools against a real Postgres: writing log, progress endpoint, repetition, consistency check.

Skipped unless TEST_DATABASE_URL is set (see tests/test_delete_integration.py).
"""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.api.routes import progress as progress_routes
from app.api.routes import projects
from app.models import DocumentEmbedding, WritingDay
from app.services import consistency, progress
from tests.test_workspace_integration import (  # noqa: F401 — fixtures are used by name
    TEST_DATABASE_URL, _create, _fake_vector, _save, _seed, db, fake_embeddings, migrated_database,
)

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")


async def _save_words(db, s, words: int):
    await projects.update_chapter(
        s.project.id, s.chapter.id, projects.ChapterUpdate(word_count=words),
        current_user=s.user, db=db,
    )


async def test_saves_build_one_log_row_per_day(db):
    s = await _seed(db)  # chapter starts at 2 words
    await _save_words(db, s, 502)    # +500
    await _save_words(db, s, 452)    # -50
    await _save_words(db, s, 1202)   # +750

    rows = (await db.execute(select(WritingDay).where(WritingDay.project_id == s.project.id))).scalars().all()
    assert len(rows) == 1
    assert (rows[0].words_added, rows[0].words_removed) == (1250, 50)


async def test_progress_endpoint_reports_goals_streak_and_next_steps(db):
    s = await _seed(db)
    await projects.update_project(
        s.project.id,
        projects.ProjectUpdate(target_word_count=10_000, daily_word_goal=500, deadline=progress.utc_today() + timedelta(days=4)),
        current_user=s.user, db=db,
    )
    await _save_words(db, s, 1002)
    await progress.record_words(db, s.project.id, s.user.id, 300, day=progress.utc_today() - timedelta(days=1))
    await db.commit()

    result = await progress_routes.project_progress(s.project.id, current_user=s.user, db=db)

    assert result["total_words"] == 1002
    assert result["today_words"] == 1000
    assert result["current_streak"] == 2
    assert result["needed_per_day"] == -(-(10_000 - 1002) // 5)
    assert result["next_steps"][0]["kind"] == "pace"  # ~1,800/day needed vs 500 goal

    # Clearing goals
    await projects.update_project(
        s.project.id, projects.ProjectUpdate(target_word_count=0, clear_deadline=True),
        current_user=s.user, db=db,
    )
    cleared = await progress_routes.project_progress(s.project.id, current_user=s.user, db=db)
    assert cleared["target_word_count"] is None and cleared["deadline"] is None


async def test_repetition_scan_finds_near_duplicates_across_chapters_only(db):
    s = await _seed(db)
    other = projects.Chapter(project_id=s.project.id, user_id=s.user.id, title="Dusk", chapter_number=2, position=1)
    db.add(other)
    await db.flush()
    repeated = "The lighthouse keeper climbed the stairs every night to light the great lamp"
    for chapter_id, content in [
        (s.chapter.id, repeated), (other.id, repeated + "."),            # near-duplicate pair
        (s.chapter.id, "Market traders argued about the price of fish"),  # unrelated
    ]:
        db.add(DocumentEmbedding(
            user_id=s.user.id, doc_type="chapter", source_id=chapter_id, project_id=s.project.id,
            content=content, embedding=_fake_vector(content),
        ))
    await db.commit()

    result = await progress_routes.repeated_passages(s.project.id, current_user=s.user, db=db)

    assert len(result["pairs"]) == 1
    pair = result["pairs"][0]
    assert {pair["a"]["chapter_title"], pair["b"]["chapter_title"]} == {"Dawn", "Dusk"}
    assert pair["similarity"] >= consistency.REPETITION_THRESHOLD


async def test_consistency_check_uses_bible_quota_and_drops_invented_quotes(db, monkeypatch):
    s = await _seed(db, content="<p>Ada was thirty when she left Lagos &amp; the sea.</p>")
    await _create(db, s, "character", "Ada Obi", "Ada is 34 and has never left Lagos")

    prompts, quota = [], []

    class FakeLLM:
        async def complete(self, messages, **_kwargs):
            prompts.append(messages[0]["content"])
            return SimpleNamespace(text='[{"entry": "Ada Obi", "quote": "Ada was thirty when she left Lagos & the sea.", "issue": "Age and leaving Lagos conflict."},'
                                        ' {"entry": "Ada Obi", "quote": "Ada sailed to Accra.", "issue": "invented"}]')

    async def fake_quota(*args):
        quota.append(args)

    monkeypatch.setattr(consistency, "get_llm_client", lambda: FakeLLM())
    monkeypatch.setattr(progress_routes, "consume_user_quota", fake_quota)

    result = await progress_routes.consistency_check(s.project.id, s.chapter.id, current_user=s.user, db=db)

    assert len(quota) == 1
    assert "Ada is 34" in prompts[0]
    assert result["checked_entries"] == 1
    assert [i["quote"] for i in result["issues"]] == ["Ada was thirty when she left Lagos & the sea."]


async def test_consistency_check_rejects_empty_chapter_before_quota(db, monkeypatch):
    s = await _seed(db, content="")
    quota = []

    async def fake_quota(*args):
        quota.append(args)

    monkeypatch.setattr(progress_routes, "consume_user_quota", fake_quota)
    with pytest.raises(Exception) as exc_info:
        await progress_routes.consistency_check(s.project.id, s.chapter.id, current_user=s.user, db=db)
    assert getattr(exc_info.value, "status_code", None) == 400 and quota == []
