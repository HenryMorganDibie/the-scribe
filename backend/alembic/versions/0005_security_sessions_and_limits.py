"""Add server sessions and security event ledger.

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])
    op.create_table(
        "security_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("subject_hash", sa.String(length=64), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_security_events_action_created", "security_events", ["action", "created_at"])
    op.create_index("ix_security_events_action_user_created", "security_events", ["action", "user_id", "created_at"])
    op.create_index("ix_security_events_action_subject_created", "security_events", ["action", "subject_hash", "created_at"])
    op.create_index("ix_security_events_action_ip_created", "security_events", ["action", "ip_hash", "created_at"])


def downgrade() -> None:
    op.drop_table("security_events")
    op.drop_table("user_sessions")
