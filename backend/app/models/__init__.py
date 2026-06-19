"""
All database models for The Scribe.
Upgraded schema includes: pgvector embeddings, voice evolution timeline,
scripture index, voice drift scoring, expanded generation logs.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    String, Text, Boolean, Integer, Float, DateTime,
    ForeignKey, JSON, ARRAY, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db.session import Base


def gen_uuid():
    return str(uuid.uuid4())


# ─────────────────────────────────────────────
# USERS
# ─────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String)
    avatar_url: Mapped[Optional[str]] = mapped_column(String)
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    voice_profile: Mapped[Optional["VoiceProfile"]] = relationship(back_populates="user", uselist=False)
    voice_versions: Mapped[List["VoiceVersion"]] = relationship(back_populates="user")
    testimonies: Mapped[List["Testimony"]] = relationship(back_populates="user")
    projects: Mapped[List["Project"]] = relationship(back_populates="user")
    document_embeddings: Mapped[List["DocumentEmbedding"]] = relationship(back_populates="user")
    generation_logs: Mapped[List["GenerationLog"]] = relationship(back_populates="user")


# ─────────────────────────────────────────────
# VOICE PROFILE
# ─────────────────────────────────────────────
class VoiceProfile(Base):
    __tablename__ = "voice_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), unique=True)

    # Raw interview answers
    ministry_background: Mapped[Optional[str]] = mapped_column(Text)
    theological_lens: Mapped[Optional[str]] = mapped_column(String)  # apostolic|prophetic|spirit-filled|charismatic
    target_audience: Mapped[Optional[str]] = mapped_column(Text)
    tone_preferences: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))  # teaching|exhortation|narrative|devotional
    preferred_translation: Mapped[Optional[str]] = mapped_column(String, default="NKJV")

    # AI-extracted voice DNA
    signature_phrases: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    anchor_scriptures: Mapped[Optional[dict]] = mapped_column(JSONB)  # [{ref, text, frequency, themes}]
    cadence_score: Mapped[Optional[float]] = mapped_column(Float)  # 0.0 (punchy) → 1.0 (flowing)
    style_tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    voice_summary: Mapped[Optional[str]] = mapped_column(Text)  # The "ghost brief" — 300-word description
    dna_narrative: Mapped[Optional[str]] = mapped_column(Text)  # cached Ministry DNA Report narrative

    # Writing samples (raw text — embeddings stored separately)
    writing_samples: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))

    # Onboarding state
    onboarding_step: Mapped[int] = mapped_column(Integer, default=0)
    onboarding_data: Mapped[Optional[dict]] = mapped_column(JSONB)  # raw step answers before final extraction

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="voice_profile")


# ─────────────────────────────────────────────
# VOICE EVOLUTION TIMELINE
# Version-controlled voice profile snapshots
# Like git commits for the author's identity
# ─────────────────────────────────────────────
class VoiceVersion(Base):
    __tablename__ = "voice_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Snapshot of voice at this point in time
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)  # full voice profile snapshot

    # What triggered this version
    trigger: Mapped[str] = mapped_column(String)  # 'onboarding_complete'|'edit_accepted'|'manual_update'
    change_summary: Mapped[Optional[str]] = mapped_column(Text)  # AI-generated summary of what changed
    chapter_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("chapters.id"), nullable=True)

    # Voice quality metrics at this snapshot
    cadence_score: Mapped[Optional[float]] = mapped_column(Float)
    phrase_count: Mapped[Optional[int]] = mapped_column(Integer)
    scripture_count: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="voice_versions")


# ─────────────────────────────────────────────
# DOCUMENT EMBEDDINGS (pgvector)
# Stores vector embeddings for writing samples and testimonies
# Enables RAG: retrieve relevant context per chapter
# ─────────────────────────────────────────────
class DocumentEmbedding(Base):
    __tablename__ = "document_embeddings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))

    doc_type: Mapped[str] = mapped_column(String)  # 'writing_sample'|'testimony'|'chapter'
    source_id: Mapped[Optional[str]] = mapped_column(String)  # testimony_id or chapter_id if applicable
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)  # the chunk text
    embedding: Mapped[List[float]] = mapped_column(Vector(384))  # all-MiniLM-L6-v2 dim

    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)  # themes, scripture refs, etc.
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="document_embeddings")

    __table_args__ = (
        Index("ix_doc_embeddings_user_type", "user_id", "doc_type"),
    )


# ─────────────────────────────────────────────
# TESTIMONY VAULT
# ─────────────────────────────────────────────
class Testimony(Base):
    __tablename__ = "testimonies"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))

    title: Mapped[str] = mapped_column(String, nullable=False)
    story: Mapped[str] = mapped_column(Text, nullable=False)
    themes: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    used_in_chapters: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))  # chapter IDs

    status: Mapped[str] = mapped_column(String, default="approved")  # suggested|approved
    source: Mapped[str] = mapped_column(String, default="manual")    # manual|mined
    source_sermon_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("sermons.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="testimonies")


# ─────────────────────────────────────────────
# SCRIPTURE INDEX
# Pre-seeded, themed, translation-aware
# No hallucinated refs
# ─────────────────────────────────────────────
class Scripture(Base):
    __tablename__ = "scriptures"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    book: Mapped[str] = mapped_column(String, nullable=False)
    chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    verse_start: Mapped[int] = mapped_column(Integer, nullable=False)
    verse_end: Mapped[Optional[int]] = mapped_column(Integer)
    reference: Mapped[str] = mapped_column(String, nullable=False)  # "Isaiah 61:1"
    text_nkjv: Mapped[Optional[str]] = mapped_column(Text)
    text_kjv: Mapped[Optional[str]] = mapped_column(Text)
    text_niv: Mapped[Optional[str]] = mapped_column(Text)
    text_esv: Mapped[Optional[str]] = mapped_column(Text)
    themes: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))  # ['calling','healing','faith']
    testament: Mapped[str] = mapped_column(String)  # 'old'|'new'

    __table_args__ = (
        Index("ix_scriptures_reference", "reference"),
        Index("ix_scriptures_themes", "themes", postgresql_using="gin"),
    )


# ─────────────────────────────────────────────
# PROJECTS (manuscripts)
# ─────────────────────────────────────────────
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))

    title: Mapped[str] = mapped_column(String, nullable=False)
    genre: Mapped[Optional[str]] = mapped_column(String)  # teaching|devotional|prophetic|memoir
    theme: Mapped[Optional[str]] = mapped_column(Text)
    target_chapters: Mapped[int] = mapped_column(Integer, default=10)
    status: Mapped[str] = mapped_column(String, default="active")  # active|complete|archived

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="projects")
    chapters: Mapped[List["Chapter"]] = relationship(back_populates="project", order_by="Chapter.position")


# ─────────────────────────────────────────────
# CHAPTERS
# ─────────────────────────────────────────────
class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))

    title: Mapped[str] = mapped_column(String, nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Chapter brief
    intent: Mapped[Optional[str]] = mapped_column(Text)
    key_points: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    anchor_scriptures: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    testimony_ids: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))

    # Content
    content: Mapped[Optional[str]] = mapped_column(Text)  # Rich text (HTML from TipTap)
    summary: Mapped[Optional[str]] = mapped_column(Text)  # AI-generated summary for chapter memory
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="draft")  # draft|in_progress|complete

    # Voice quality
    voice_match_score: Mapped[Optional[float]] = mapped_column(Float)  # Last checked score

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="chapters")


# ─────────────────────────────────────────────
# GENERATION LOGS (expanded)
# ─────────────────────────────────────────────
class GenerationLog(Base):
    __tablename__ = "generation_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    chapter_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("chapters.id"), nullable=True)

    action: Mapped[str] = mapped_column(String)  # generate_chapter|continue|weave_story|voice_check|preview|chat
    model: Mapped[str] = mapped_column(String, default="claude-sonnet-4-20250514")

    tokens_in: Mapped[Optional[int]] = mapped_column(Integer)
    tokens_out: Mapped[Optional[int]] = mapped_column(Integer)
    cost_usd: Mapped[Optional[float]] = mapped_column(Float)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    voice_match_score: Mapped[Optional[float]] = mapped_column(Float)  # If voice check was run
    retrieved_doc_ids: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))  # RAG docs used

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="generation_logs")


# ─────────────────────────────────────────────
# SERMONS (ingested sources)
# ─────────────────────────────────────────────
class Sermon(Base):
    __tablename__ = "sermons"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))

    title: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String)  # pdf|docx|text|audio
    original_filename: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|extracting|analyzing|complete|failed

    transcript: Mapped[Optional[str]] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    phrases_added: Mapped[int] = mapped_column(Integer, default=0)
    testimonies_suggested: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    __table_args__ = (
        Index("ix_sermons_user_status", "user_id", "status"),
    )
