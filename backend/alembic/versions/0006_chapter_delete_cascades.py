"""Let chapters be deleted after AI generation or voice snapshots reference them.

generation_logs.chapter_id and voice_versions.chapter_id referenced chapters
with no ON DELETE rule, so deleting any chapter that had been generated or
voice-checked (and any project containing one) raised a foreign-key error.
Keep the log and timeline rows for history; just detach them from the chapter.

Revision ID: 0006
Revises: 0005
"""
from alembic import op


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_TABLES = ("generation_logs", "voice_versions")


def _replace_chapter_fk(table: str, on_delete: str) -> None:
    # The original constraints were created unnamed (Postgres picked the
    # names), so look the existing one up instead of guessing it.
    op.execute(f"""
        DO $$
        DECLARE fk_name text;
        BEGIN
            SELECT con.conname INTO fk_name
            FROM pg_constraint con
            JOIN pg_attribute att
              ON att.attrelid = con.conrelid AND att.attnum = ANY (con.conkey)
            WHERE con.contype = 'f'
              AND con.conrelid = '{table}'::regclass
              AND con.confrelid = 'chapters'::regclass
              AND att.attname = 'chapter_id';
            IF fk_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE {table} DROP CONSTRAINT %I', fk_name);
            END IF;
        END $$;
    """)
    op.create_foreign_key(
        f"{table}_chapter_id_fkey", table, "chapters",
        ["chapter_id"], ["id"], ondelete=on_delete,
    )


def upgrade() -> None:
    for table in _TABLES:
        _replace_chapter_fk(table, "SET NULL")


def downgrade() -> None:
    for table in _TABLES:
        _replace_chapter_fk(table, "NO ACTION")
