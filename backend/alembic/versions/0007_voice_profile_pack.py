"""Add a genre pack to voice profiles.

Every profile that exists today was created by the Christian-only product,
so existing rows are backfilled to 'christian'. New profiles default to
'general' and pick their pack during onboarding.

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The server default fills every existing row in the same statement...
    op.add_column(
        "voice_profiles",
        sa.Column("pack", sa.String(), nullable=False, server_default="christian"),
    )
    # ...then new rows default to the general pack.
    op.alter_column("voice_profiles", "pack", server_default="general")


def downgrade() -> None:
    op.drop_column("voice_profiles", "pack")
