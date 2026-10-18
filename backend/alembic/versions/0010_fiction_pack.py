"""Fiction pack: chapter scene plans, timeline events in the book bible.

Writers who chose "Fiction" as their genre in the general pack are moved to
the new fiction pack.

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chapters", sa.Column("scenes", postgresql.JSONB(), nullable=True))
    op.add_column("book_entries", sa.Column("when_label", sa.String(length=120), nullable=True))
    op.add_column("book_entries", sa.Column("timeline_order", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE voice_profiles SET pack = 'fiction' "
        "WHERE pack = 'general' AND theological_lens ILIKE 'fiction%'"
    )


def downgrade() -> None:
    op.execute("UPDATE voice_profiles SET pack = 'general' WHERE pack = 'fiction'")
    op.drop_column("book_entries", "timeline_order")
    op.drop_column("book_entries", "when_label")
    op.drop_column("chapters", "scenes")
