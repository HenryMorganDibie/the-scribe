"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')

    op.create_table(
        'users',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('email', sa.String(), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('full_name', sa.String()),
        sa.Column('avatar_url', sa.String()),
        sa.Column('onboarded', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_users_email', 'users', ['email'])

    op.create_table(
        'voice_profiles',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), sa.ForeignKey('users.id', ondelete='CASCADE'), unique=True),
        sa.Column('ministry_background', sa.Text()),
        sa.Column('theological_lens', sa.String()),
        sa.Column('target_audience', sa.Text()),
        sa.Column('tone_preferences', postgresql.ARRAY(sa.String())),
        sa.Column('preferred_translation', sa.String(), server_default='NKJV'),
        sa.Column('signature_phrases', postgresql.ARRAY(sa.String())),
        sa.Column('anchor_scriptures', postgresql.JSONB()),
        sa.Column('cadence_score', sa.Float()),
        sa.Column('style_tags', postgresql.ARRAY(sa.String())),
        sa.Column('voice_summary', sa.Text()),
        sa.Column('writing_samples', postgresql.ARRAY(sa.Text())),
        sa.Column('onboarding_step', sa.Integer(), server_default='0'),
        sa.Column('onboarding_data', postgresql.JSONB()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'voice_versions',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('snapshot', postgresql.JSONB(), nullable=False),
        sa.Column('trigger', sa.String()),
        sa.Column('change_summary', sa.Text()),
        sa.Column('chapter_id', sa.String()),
        sa.Column('cadence_score', sa.Float()),
        sa.Column('phrase_count', sa.Integer()),
        sa.Column('scripture_count', sa.Integer()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'document_embeddings',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('doc_type', sa.String()),
        sa.Column('source_id', sa.String()),
        sa.Column('chunk_index', sa.Integer(), server_default='0'),
        sa.Column('content', sa.Text()),
        sa.Column('embedding', Vector(384)),
        sa.Column('metadata', postgresql.JSONB()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_doc_embeddings_user_type', 'document_embeddings', ['user_id', 'doc_type'])
    op.execute('CREATE INDEX ix_doc_embeddings_vector ON document_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)')

    op.create_table(
        'testimonies',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('story', sa.Text(), nullable=False),
        sa.Column('themes', postgresql.ARRAY(sa.String())),
        sa.Column('used_in_chapters', postgresql.ARRAY(sa.String())),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'scriptures',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('book', sa.String(), nullable=False),
        sa.Column('chapter', sa.Integer(), nullable=False),
        sa.Column('verse_start', sa.Integer(), nullable=False),
        sa.Column('verse_end', sa.Integer()),
        sa.Column('reference', sa.String(), nullable=False),
        sa.Column('text_nkjv', sa.Text()),
        sa.Column('text_kjv', sa.Text()),
        sa.Column('text_niv', sa.Text()),
        sa.Column('text_esv', sa.Text()),
        sa.Column('themes', postgresql.ARRAY(sa.String())),
        sa.Column('testament', sa.String()),
    )
    op.create_index('ix_scriptures_reference', 'scriptures', ['reference'])
    op.execute('CREATE INDEX ix_scriptures_themes ON scriptures USING gin (themes)')

    op.create_table(
        'projects',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('genre', sa.String()),
        sa.Column('theme', sa.Text()),
        sa.Column('target_chapters', sa.Integer(), server_default='10'),
        sa.Column('status', sa.String(), server_default='active'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'chapters',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('project_id', sa.String(), sa.ForeignKey('projects.id', ondelete='CASCADE')),
        sa.Column('user_id', sa.String(), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('chapter_number', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('intent', sa.Text()),
        sa.Column('key_points', postgresql.ARRAY(sa.Text())),
        sa.Column('anchor_scriptures', postgresql.ARRAY(sa.String())),
        sa.Column('testimony_ids', postgresql.ARRAY(sa.String())),
        sa.Column('content', sa.Text()),
        sa.Column('summary', sa.Text()),
        sa.Column('word_count', sa.Integer(), server_default='0'),
        sa.Column('status', sa.String(), server_default='draft'),
        sa.Column('voice_match_score', sa.Float()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'generation_logs',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), sa.ForeignKey('users.id')),
        sa.Column('chapter_id', sa.String(), sa.ForeignKey('chapters.id'), nullable=True),
        sa.Column('action', sa.String()),
        sa.Column('model', sa.String(), server_default='claude-sonnet-4-20250514'),
        sa.Column('tokens_in', sa.Integer()),
        sa.Column('tokens_out', sa.Integer()),
        sa.Column('cost_usd', sa.Float()),
        sa.Column('latency_ms', sa.Integer()),
        sa.Column('success', sa.Boolean(), server_default='true'),
        sa.Column('error_message', sa.Text()),
        sa.Column('voice_match_score', sa.Float()),
        sa.Column('retrieved_doc_ids', postgresql.ARRAY(sa.String())),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('generation_logs')
    op.drop_table('chapters')
    op.drop_table('projects')
    op.drop_table('scriptures')
    op.drop_table('testimonies')
    op.drop_table('document_embeddings')
    op.drop_table('voice_versions')
    op.drop_table('voice_profiles')
    op.drop_table('users')
