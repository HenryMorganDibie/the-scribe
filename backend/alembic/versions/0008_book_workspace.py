"""Book workspace: chapter draft history, book bible, per-book style.

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chapter_versions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("chapter_id", sa.String(), sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_chapter_versions_chapter_created", "chapter_versions", ["chapter_id", "created_at"])

    op.create_table(
        "book_entries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", sa.String(), sa.ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_book_entries_project_kind", "book_entries", ["project_id", "kind"])
    op.create_index("ix_book_entries_chapter", "book_entries", ["chapter_id"])

    op.add_column("projects", sa.Column("target_audience", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("style_rules", postgresql.JSONB(), nullable=True))
    op.add_column("projects", sa.Column("style_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "style_notes")
    op.drop_column("projects", "style_rules")
    op.drop_column("projects", "target_audience")
    op.drop_index("ix_book_entries_chapter", table_name="book_entries")
    op.drop_index("ix_book_entries_project_kind", table_name="book_entries")
    op.drop_table("book_entries")
    op.drop_index("ix_chapter_versions_chapter_created", table_name="chapter_versions")
    op.drop_table("chapter_versions")
