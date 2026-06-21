"""companion chat messages, document_embeddings.project_id

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_embeddings",
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
    )
    op.create_index("ix_doc_embeddings_project", "document_embeddings", ["project_id"])

    op.create_table(
        "companion_chat_messages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="CASCADE")),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("role", sa.String()),
        sa.Column("content", sa.Text()),
        sa.Column("referenced_chapter_ids", postgresql.ARRAY(sa.String())),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_companion_chat_project", "companion_chat_messages", ["project_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_companion_chat_project", table_name="companion_chat_messages")
    op.drop_table("companion_chat_messages")
    op.drop_index("ix_doc_embeddings_project", table_name="document_embeddings")
    op.drop_column("document_embeddings", "project_id")
