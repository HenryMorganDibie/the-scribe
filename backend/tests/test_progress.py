"""Finishing tools (unit level): streaks, pace, next steps, consistency-issue parsing."""
import json
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.routes.projects import ChapterUpdate, ProjectUpdate
from app.services.consistency import parse_issues
from app.services.progress import Day, compute_progress, next_steps, progress_summary_for_prompt, streaks

TODAY = date(2026, 10, 15)


def d(days_ago: int, added: int = 100, removed: int = 0) -> Day:
    return Day(TODAY - timedelta(days=days_ago), added, removed)


def project(**kwargs):
    defaults = dict(target_word_count=None, deadline=None, daily_word_goal=None, target_chapters=3)
    return SimpleNamespace(**{**defaults, **kwargs})


def chapter(n, status="draft", words=0, intent="An intent", key_points=None):
    return SimpleNamespace(
        id=f"c{n}", chapter_number=n, position=n - 1, title=f"Chapter {n}",
        status=status, word_count=words, intent=intent, key_points=key_points or [],
    )


# ── Streaks ─────────────────────────────────────────────────────────

def test_streak_counts_consecutive_days_ending_today():
    assert streaks([d(0), d(1), d(2), d(5)], TODAY) == (3, 3)


def test_streak_survives_until_today_ends():
    assert streaks([d(1), d(2)], TODAY) == (2, 2)  # nothing yet today — still alive


def test_streak_broken_by_a_missed_day():
    assert streaks([d(2), d(3), d(4), d(5)], TODAY) == (0, 4)


def test_deleting_counts_as_writing_activity_and_empty_days_do_not():
    assert streaks([d(0, added=0, removed=50), d(1, added=0)], TODAY) == (1, 1)
    assert streaks([], TODAY) == (0, 0)


# ── Pace ────────────────────────────────────────────────────────────

def test_pace_spreads_remaining_words_over_days_left_including_today():
    p = compute_progress(
        project(target_word_count=60_000, deadline=TODAY + timedelta(days=9), daily_word_goal=1000),
        [chapter(1, words=40_000)], [d(0, 700)], TODAY,
    )
    assert p["words_left"] == 20_000
    assert p["days_left"] == 9
    assert p["needed_per_day"] == 2_000   # 20,000 over 10 days (today + 9)
    assert p["today_words"] == 700
    assert p["percent_complete"] == 66.7


def test_pace_past_deadline_and_no_goals():
    late = compute_progress(project(target_word_count=1000, deadline=TODAY - timedelta(days=3)), [chapter(1, words=400)], [], TODAY)
    assert late["needed_per_day"] == 600 and late["days_left"] == -3

    none = compute_progress(project(), [chapter(1, words=400)], [], TODAY)
    assert none["needed_per_day"] is None and none["percent_complete"] is None


def test_history_has_one_entry_per_day_oldest_first():
    p = compute_progress(project(), [], [d(0, 300), d(13, 50)], TODAY, history_days=14)
    assert len(p["history"]) == 14
    assert p["history"][0] == {"day": TODAY - timedelta(days=13), "words_added": 50}
    assert p["history"][-1] == {"day": TODAY, "words_added": 300}


def test_stage_counts_treat_unknown_status_as_outline():
    p = compute_progress(project(), [chapter(1, "complete"), chapter(2, "revised"), chapter(3, "weird")], [], TODAY)
    assert p["stage_counts"] == {"draft": 1, "in_progress": 0, "revised": 1, "complete": 1}


# ── Next steps ──────────────────────────────────────────────────────

def _steps(proj, chapters, today_words=0):
    return next_steps(proj, chapters, compute_progress(proj, chapters, [d(0, today_words)], TODAY), limit=10)


def test_next_steps_for_empty_book():
    assert _steps(project(), [])[0]["kind"] == "outline"


def test_next_steps_cover_outline_gaps_briefs_drafting_and_revising():
    chapters = [chapter(1, "in_progress", 2000), chapter(2, intent="", key_points=[]), chapter(3)]
    kinds = [s["kind"] for s in _steps(project(target_chapters=5), chapters)]
    assert kinds[:4] == ["outline", "brief", "draft", "revise"]


def test_next_steps_flag_pace_and_thin_chapters_and_finished_books():
    behind = project(target_word_count=50_000, deadline=TODAY + timedelta(days=4), daily_word_goal=500, target_chapters=3)
    steps = _steps(behind, [chapter(1, "complete", 3000), chapter(2, "complete", 3000), chapter(3, "in_progress", 400)])
    assert steps[0]["kind"] == "pace"
    assert any(s["kind"] == "thin" and s["chapter_id"] == "c3" for s in steps)

    done = _steps(project(target_chapters=2), [chapter(1, "complete", 3000), chapter(2, "complete", 3000)])
    assert [s["kind"] for s in done] == ["export"]


def test_progress_summary_reads_naturally():
    p = compute_progress(project(target_word_count=1000), [chapter(1, "revised", 500)], [], TODAY)
    text = progress_summary_for_prompt(p, [{"message": "Finish chapter 1."}])
    assert "Words: 500 of 1,000" in text and "Revised: 1" in text and "Finish chapter 1." in text


# ── Request validation ──────────────────────────────────────────────

def test_chapter_status_must_be_a_known_stage():
    assert ChapterUpdate(status="revised").status == "revised"
    with pytest.raises(ValidationError):
        ChapterUpdate(status="published")


def test_goals_reject_negative_values():
    with pytest.raises(ValidationError):
        ProjectUpdate(target_word_count=-5)


# ── Consistency issue parsing ───────────────────────────────────────

CHAPTER_TEXT = "Ada was thirty when she left Lagos.\nShe never  returned to the harbour."


def test_issues_must_quote_the_chapter_verbatim():
    raw = json.dumps([
        {"entry": "Ada Obi", "quote": "Ada was thirty when she left Lagos.", "issue": "Ada is 34 in the bible."},
        {"entry": "Harbour", "quote": "she never returned to the harbour", "issue": "Whitespace/case differences are fine."},
        {"entry": "Invented", "quote": "Ada flew to Paris.", "issue": "Not in the chapter — dropped."},
        {"entry": "Broken", "quote": "", "issue": "No quote — dropped."},
        "not an object",
    ])
    issues = parse_issues(f"```json\n{raw}\n```", CHAPTER_TEXT)
    assert [i["entry"] for i in issues] == ["Ada Obi", "Harbour"]


def test_unparseable_issue_output_is_empty():
    assert parse_issues("I found no issues!", CHAPTER_TEXT) == []
    assert parse_issues('{"issues": []}', CHAPTER_TEXT) == []
