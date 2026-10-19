"""Book goals (target words, deadline, daily goal) and a per-day writing log.

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("target_word_count", sa.Integer(), nullable=True))
    op.add_column("projects", sa.Column("deadline", sa.Date(), nullable=True))
    op.add_column("projects", sa.Column("daily_word_goal", sa.Integer(), nullable=True))

    op.create_table(
        "writing_days",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("words_added", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("words_removed", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("project_id", "day", name="uq_writing_days_project_day"),
    )


def downgrade() -> None:
    op.drop_table("writing_days")
    op.drop_column("projects", "daily_word_goal")
    op.drop_column("projects", "deadline")
    op.drop_column("projects", "target_word_count")
