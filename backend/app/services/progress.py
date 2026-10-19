"""
Book progress: the writing log, goals and pace, streaks, and "what's next".

Days are UTC days. The log records how much the manuscript grew or shrank
each day (from chapter saves), so it measures the book, not keystrokes —
an AI draft the author keeps counts, a restore of an old version does not.

Everything except `record_words` is a pure function over plain data, so
the rules are unit-testable without a database.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WritingDay, gen_uuid

# Chapter stages, in order. Stored in chapters.status (values kept from the
# original schema so existing rows stay valid).
STAGES = ("draft", "in_progress", "revised", "complete")
STAGE_LABELS = {"draft": "Outline", "in_progress": "Drafted", "revised": "Revised", "complete": "Done"}

SHORT_CHAPTER_RATIO = 0.4  # flag drafted chapters under 40% of the book's average length


def utc_today() -> date:
    return datetime.utcnow().date()


async def record_words(db: AsyncSession, project_id: str, user_id: str, delta: int, day: Optional[date] = None) -> None:
    """Add a word-count change to today's log row (upsert). Caller commits."""
    if not delta:
        return
    added, removed = (delta, 0) if delta > 0 else (0, -delta)
    stmt = insert(WritingDay).values(
        id=gen_uuid(),
        project_id=project_id, user_id=user_id, day=day or utc_today(),
        words_added=added, words_removed=removed,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_writing_days_project_day",
        set_={
            "words_added": WritingDay.words_added + stmt.excluded.words_added,
            "words_removed": WritingDay.words_removed + stmt.excluded.words_removed,
        },
    )
    await db.execute(stmt)


@dataclass
class Day:
    day: date
    words_added: int = 0
    words_removed: int = 0

    @property
    def active(self) -> bool:
        return bool(self.words_added or self.words_removed)


def streaks(days: Iterable[Day], today: date) -> tuple[int, int]:
    """(current, longest) runs of consecutive active days.

    The current streak survives until today ends: if nothing is written yet
    today, a run ending yesterday still counts.
    """
    active = sorted({d.day for d in days if d.active})
    if not active:
        return 0, 0

    longest = run = 1
    for prev, cur in zip(active, active[1:]):
        run = run + 1 if cur - prev == timedelta(days=1) else 1
        longest = max(longest, run)

    current = 0
    cursor = today if today in active else today - timedelta(days=1)
    active_set = set(active)
    while cursor in active_set:
        current += 1
        cursor -= timedelta(days=1)
    return current, longest


def compute_progress(project, chapters: list, days: list[Day], today: date, history_days: int = 14) -> dict:
    total_words = sum(c.word_count or 0 for c in chapters)
    by_day = {d.day: d for d in days}
    today_row = by_day.get(today, Day(today))
    current_streak, longest_streak = streaks(days, today)

    stage_counts = {stage: 0 for stage in STAGES}
    for c in chapters:
        stage_counts[c.status if c.status in stage_counts else "draft"] += 1

    target = project.target_word_count or None
    deadline = project.deadline
    days_left = (deadline - today).days if deadline else None
    words_left = max(target - total_words, 0) if target else None
    needed_per_day = None
    if words_left is not None and days_left is not None:
        # Includes today; a past deadline means "everything, now".
        needed_per_day = words_left if days_left <= 0 else -(-words_left // (days_left + 1))

    return {
        "total_words": total_words,
        "target_word_count": target,
        "percent_complete": round(min(total_words / target, 1.0) * 100, 1) if target else None,
        "deadline": deadline,
        "days_left": days_left,
        "words_left": words_left,
        "needed_per_day": needed_per_day,
        "daily_word_goal": project.daily_word_goal or None,
        "today_words": today_row.words_added,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "chapters_total": len(chapters),
        "target_chapters": project.target_chapters,
        "stage_counts": stage_counts,
        "history": [
            {"day": d, "words_added": by_day.get(d, Day(d)).words_added}
            for d in (today - timedelta(days=i) for i in range(history_days - 1, -1, -1))
        ],
    }


def next_steps(project, chapters: list, progress: dict, limit: int = 5) -> list[dict]:
    """Ranked, rule-based suggestions for what to do next on this book."""
    steps: list[dict] = []
    ordered = sorted(chapters, key=lambda c: c.position)

    if not ordered:
        return [{"kind": "outline", "message": "Add your first chapter — or build an outline from your sources."}]

    deadline_step = None
    needed, goal = progress.get("needed_per_day"), progress.get("daily_word_goal")
    if needed and progress.get("days_left") is not None:
        if progress["days_left"] < 0:
            deadline_step = {"kind": "pace", "message": f"The deadline has passed with {progress['words_left']:,} words to go — set a new date to plan your pace."}
        elif goal and needed > goal:
            deadline_step = {"kind": "pace", "message": f"To hit your deadline you need about {needed:,} words a day — more than your {goal:,}-word daily goal."}
    if deadline_step:
        steps.append(deadline_step)

    missing = (project.target_chapters or 0) - len(ordered)
    if missing > 0:
        steps.append({"kind": "outline", "message": f"Your outline has {len(ordered)} of {project.target_chapters} planned chapters — add the {missing} still missing."})

    for c in ordered:
        if not (c.intent or "").strip() and not (c.key_points or []):
            steps.append({"kind": "brief", "chapter_id": c.id, "message": f"Chapter {c.chapter_number}, \"{c.title}\", has no brief yet — add its intent and key points before drafting."})
            break

    in_progress = [c for c in ordered if c.status == "in_progress"]
    not_started = [c for c in ordered if c.status == "draft" and not (c.word_count or 0)]
    if not_started:
        c = not_started[0]
        steps.append({"kind": "draft", "chapter_id": c.id, "message": f"Draft chapter {c.chapter_number}, \"{c.title}\"."})
    if in_progress:
        c = in_progress[0]
        steps.append({"kind": "revise", "chapter_id": c.id, "message": f"Revise chapter {c.chapter_number}, \"{c.title}\", then mark it Revised."})

    written = [c.word_count for c in ordered if (c.word_count or 0) > 0]
    if len(written) >= 3:
        average = sum(written) / len(written)
        for c in ordered:
            if c.status != "draft" and 0 < (c.word_count or 0) < average * SHORT_CHAPTER_RATIO:
                steps.append({"kind": "thin", "chapter_id": c.id, "message": f"Chapter {c.chapter_number}, \"{c.title}\", is much shorter than the rest ({c.word_count:,} vs ~{int(average):,} words)."})
                break

    revised = [c for c in ordered if c.status == "revised"]
    if revised:
        c = revised[0]
        steps.append({"kind": "finish", "chapter_id": c.id, "message": f"Chapter {c.chapter_number} is revised — give it a final read and mark it Done."})

    if all(c.status == "complete" for c in ordered) and missing <= 0:
        steps.append({"kind": "export", "message": "Every chapter is done — export the manuscript and read it end to end."})

    return steps[:limit]


async def load_progress(db: AsyncSession, project, *, today: Optional[date] = None, history_days: int = 14) -> tuple[dict, list[dict]]:
    """Progress and next steps for one book, read from the database."""
    from app.models import Chapter

    today = today or utc_today()
    chapters = (await db.execute(select(Chapter).where(Chapter.project_id == project.id))).scalars().all()
    rows = (await db.execute(
        select(WritingDay).where(WritingDay.project_id == project.id).order_by(WritingDay.day)
    )).scalars().all()
    days = [Day(r.day, r.words_added, r.words_removed) for r in rows]
    progress = compute_progress(project, list(chapters), days, today, history_days)
    return progress, next_steps(project, list(chapters), progress)


def progress_summary_for_prompt(progress: dict, steps: list[dict]) -> str:
    """Compact text for Companion Chat so it can answer "what should I work on next?"."""
    stages = ", ".join(f"{STAGE_LABELS[s]}: {n}" for s, n in progress["stage_counts"].items())
    lines = [f"Words: {progress['total_words']:,}" + (f" of {progress['target_word_count']:,}" if progress["target_word_count"] else "")]
    if progress["deadline"]:
        lines.append(f"Deadline: {progress['deadline']} ({progress['days_left']} days left, ~{progress['needed_per_day'] or 0:,} words/day needed)")
    lines.append(f"Chapter stages — {stages}")
    lines.append(f"Writing streak: {progress['current_streak']} day(s)")
    if steps:
        lines.append("Suggested next steps:\n" + "\n".join(f"  - {s['message']}" for s in steps))
    return "\n".join(lines)
