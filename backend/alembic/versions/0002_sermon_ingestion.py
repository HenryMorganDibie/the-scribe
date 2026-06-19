"""sermon ingestion, testimony mining, dna report

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sermons",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("source_type", sa.String()),
        sa.Column("original_filename", sa.String()),
        sa.Column("status", sa.String(), server_default="pending"),
        sa.Column("transcript", sa.Text()),
        sa.Column("word_count", sa.Integer(), server_default="0"),
        sa.Column("phrases_added", sa.Integer(), server_default="0"),
        sa.Column("testimonies_suggested", sa.Integer(), server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime()),
    )
    op.create_index("ix_sermons_user_status", "sermons", ["user_id", "status"])

    op.add_column("testimonies", sa.Column("status", sa.String(), server_default="approved"))
    op.add_column("testimonies", sa.Column("source", sa.String(), server_default="manual"))
    op.add_column("testimonies", sa.Column("source_sermon_id", sa.String(), sa.ForeignKey("sermons.id", ondelete="SET NULL"), nullable=True))

    op.add_column("voice_profiles", sa.Column("dna_narrative", sa.Text()))


def downgrade() -> None:
    op.drop_column("voice_profiles", "dna_narrative")
    op.drop_column("testimonies", "source_sermon_id")
    op.drop_column("testimonies", "source")
    op.drop_column("testimonies", "status")
    op.drop_index("ix_sermons_user_status", table_name="sermons")
    op.drop_table("sermons")
