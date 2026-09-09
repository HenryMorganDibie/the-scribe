"""Add sermon-book provenance and author theological guardrails.

Revision ID: 0004
Revises: 4848eaa0f8a2
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0004"
down_revision = "4848eaa0f8a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("voice_profiles", sa.Column("theological_guardrails", postgresql.JSONB(), nullable=True))
    op.add_column("projects", sa.Column("source_sermon_ids", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "source_sermon_ids")
    op.drop_column("voice_profiles", "theological_guardrails")
