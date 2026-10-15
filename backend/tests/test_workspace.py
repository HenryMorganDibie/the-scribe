"""Book workspace (unit level): per-book style in the voice brief, entry formatting, source linking."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes import projects
from app.models import BookEntry, VoiceProfile
from app.services.ai.generation import build_voice_brief
from app.services.book_bible import format_entries


def _project(**kwargs):
    defaults = dict(target_audience=None, style_rules=None, style_notes=None)
    return SimpleNamespace(**{**defaults, **kwargs})


async def test_book_style_overrides_audience_and_adds_rules_and_notes():
    profile = VoiceProfile(
        user_id="u1", pack="general", target_audience="Founders",
        theological_guardrails=["British spelling"],
    )
    project = _project(
        target_audience="Teenagers who love sci-fi",
        style_rules=["Present tense", "  "],
        style_notes="Short chapters. End every chapter on a cliffhanger.",
    )

    brief = await build_voice_brief(profile, project=project)

    assert "TARGET AUDIENCE: Teenagers who love sci-fi" in brief
    assert "Founders" not in brief
    assert "British spelling" in brief and "Present tense" in brief  # book rules add to the author's
    assert "STYLE NOTES FOR THIS BOOK" in brief and "cliffhanger" in brief


async def test_book_without_overrides_inherits_author_defaults():
    profile = VoiceProfile(user_id="u1", pack="general", target_audience="Founders")
    brief = await build_voice_brief(profile, project=_project())

    assert "TARGET AUDIENCE: Founders" in brief
    assert "STYLE NOTES FOR THIS BOOK" not in brief


def test_format_entries_labels_kind_and_truncates_body():
    entries = [
        BookEntry(kind="character", title="Ada", body="Engineer, 34, distrusts her father."),
        BookEntry(kind="term", title="The Drift", body="x" * 1000),
        BookEntry(kind="place", title="Lagos", body=""),
    ]
    text = format_entries(entries, body_limit=50)

    assert "[Character] Ada: Engineer, 34" in text
    assert "[Term] The Drift: " + "x" * 50 in text and "x" * 51 not in text
    assert text.splitlines()[-1] == "  • [Place] Lagos"


class SourceSession:
    """Fake session: the project lookup is patched; this answers the Sermon id query."""

    def __init__(self, owned_ids):
        self.owned_ids = owned_ids
        self.commits = 0

    async def execute(self, _statement):
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: list(self.owned_ids)))

    async def commit(self):
        self.commits += 1


@pytest.fixture
def owned_project(monkeypatch):
    project = SimpleNamespace(id="p1", source_sermon_ids=None, style_rules=None, target_audience=None, style_notes=None)

    async def fake_owned_project(*_args, **_kwargs):
        return project

    monkeypatch.setattr(projects, "get_owned_project", fake_owned_project)
    return project


async def test_linking_sources_rejects_ids_outside_the_library(owned_project):
    db = SourceSession(owned_ids=["s1"])
    with pytest.raises(HTTPException) as exc_info:
        await projects.update_project(
            "p1", projects.ProjectUpdate(source_sermon_ids=["s1", "someone-elses"]),
            current_user=SimpleNamespace(id="u1"), db=db,
        )
    assert exc_info.value.status_code == 400
    assert owned_project.source_sermon_ids is None and db.commits == 0


async def test_linking_sources_and_style_are_saved_cleaned(owned_project):
    db = SourceSession(owned_ids=["s1", "s2"])
    await projects.update_project(
        "p1",
        projects.ProjectUpdate(
            source_sermon_ids=["s1", "s2", "s1"], style_rules=[" Present tense ", ""],
            target_audience="   ", style_notes=" Keep it short. ",
        ),
        current_user=SimpleNamespace(id="u1"), db=db,
    )
    assert owned_project.source_sermon_ids == ["s1", "s2"]
    assert owned_project.style_rules == ["Present tense"]
    assert owned_project.target_audience is None  # blank clears the override
    assert owned_project.style_notes == "Keep it short."
