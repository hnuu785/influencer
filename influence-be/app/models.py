from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    google_subject: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320))
    name: Mapped[str] = mapped_column(String(120))
    picture_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    locale: Mapped[str] = mapped_column(String(10), default="ko")
    consent_version: Mapped[str] = mapped_column(String(30), default="2026-08-16")
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class GoogleConnection(Base):
    __tablename__ = "google_connections"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    calendar_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    encrypted_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class BrandProfile(Base):
    __tablename__ = "brand_profiles"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    audience: Mapped[str] = mapped_column(Text, default="")
    tone: Mapped[str] = mapped_column(Text, default="담백하고 구체적으로")
    taboo_topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class StoryRecord(Base):
    __tablename__ = "story_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    state: Mapped[str] = mapped_column(String(50), default="CAPTURED")
    title: Mapped[str] = mapped_column(String(200), default="오늘의 기록")
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    calendar_context: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class SourceAsset(Base):
    __tablename__ = "source_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("story_records.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(20))
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retention_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rights_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class Transcript(Base):
    __tablename__ = "transcripts"

    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_assets.id", ondelete="CASCADE"), primary_key=True
    )
    text: Mapped[str] = mapped_column(Text)
    segments: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="ko")


class ConversationLog(Base):
    __tablename__ = "conversation_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("story_records.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(Text)
    answer_type: Mapped[str] = mapped_column(String(20))
    answer_text: Mapped[str] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(20), default="public_ok")
    order_index: Mapped[int] = mapped_column(Integer)


class StoryCard(Base):
    __tablename__ = "story_cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("story_records.id", ondelete="CASCADE"), index=True
    )
    event: Mapped[str] = mapped_column(Text)
    observation: Mapped[str] = mapped_column(Text)
    emotion: Mapped[str] = mapped_column(Text, default="")
    opinion: Mapped[str] = mapped_column(Text)
    evidence_level: Mapped[str] = mapped_column(
        String(40), default="personal_observation"
    )
    content_angles: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="waiting_for_approval")
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536), nullable=True
    )


class PatternReference(Base):
    __tablename__ = "pattern_references"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    format: Mapped[str] = mapped_column(String(20), index=True)
    hook_type: Mapped[str] = mapped_column(String(40))
    structure: Mapped[list[str]] = mapped_column(JSON)
    objective: Mapped[str] = mapped_column(String(80))
    topic_tags: Mapped[list[str]] = mapped_column(JSON)
    guidance: Mapped[str] = mapped_column(Text)
    rights_basis: Mapped[str] = mapped_column(String(80), default="team_authored")
    version: Mapped[int] = mapped_column(Integer, default=1)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536), nullable=True
    )


class InfluencerProfile(Base):
    __tablename__ = "influencer_profiles"
    __table_args__ = (
        UniqueConstraint(
            "platform", "username", name="uq_influencer_platform_username"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dataset_version: Mapped[str] = mapped_column(String(30), index=True)
    rank_by_follower_snapshot: Mapped[int] = mapped_column(Integer)
    platform: Mapped[str] = mapped_column(String(20), index=True)
    username: Mapped[str] = mapped_column(String(80), index=True)
    profile_url: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(String(255))
    follower_count: Mapped[int] = mapped_column(Integer, index=True)
    following_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    media_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engagement_rate_percent: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    profile_type: Mapped[str] = mapped_column(String(60), index=True)
    countries: Mapped[list[str]] = mapped_column(JSON, default=list)
    creator_or_manager: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[str] = mapped_column(String(100))
    observed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    observed_precision: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[str] = mapped_column(String(20), index=True)
    account_status: Mapped[str] = mapped_column(String(60), index=True)
    source_url: Mapped[str] = mapped_column(Text)
    secondary_source_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    follower_growth_3mo_percent: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    retrieval_text: Mapped[str] = mapped_column(Text)
    rights_basis: Mapped[str] = mapped_column(
        String(80), default="source_terms_unverified"
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536), nullable=True
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class ContentBrief(Base):
    __tablename__ = "content_briefs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    story_card_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("story_cards.id", ondelete="CASCADE"), unique=True
    )
    audience: Mapped[str] = mapped_column(Text)
    objective: Mapped[str] = mapped_column(Text)
    core_message: Mapped[str] = mapped_column(Text)
    proof_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    pattern_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    constraints: Mapped[list[str]] = mapped_column(JSON, default=list)


class ContentPackage(Base):
    __tablename__ = "content_packages"
    __table_args__ = (
        UniqueConstraint("brief_id", "format", name="uq_package_brief_format"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    brief_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("content_briefs.id", ondelete="CASCADE"), index=True
    )
    format: Mapped[str] = mapped_column(String(20))
    objective: Mapped[str] = mapped_column(String(80))
    hook_options: Mapped[list[str]] = mapped_column(JSON, default=list)
    storyboard: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    script_or_copy: Mapped[list[str]] = mapped_column(JSON, default=list)
    captions: Mapped[list[str]] = mapped_column(JSON, default=list)
    cta: Mapped[str] = mapped_column(Text)
    production_instructions: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    reference_refs: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="waiting_for_approval")
    approved_copy: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536), nullable=True
    )


class QualityReview(Base):
    __tablename__ = "quality_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    package_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("content_packages.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(20))
    target_ref: Mapped[str] = mapped_column(Text)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    message: Mapped[str] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(String(30), nullable=True)


class ExportPackage(Base):
    __tablename__ = "export_packages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("story_records.id", ondelete="CASCADE")
    )
    package_ids: Mapped[list[str]] = mapped_column(JSON)
    storage_path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="ready")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PublicationConfirmation(Base):
    __tablename__ = "publication_confirmations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("story_records.id", ondelete="CASCADE")
    )
    format: Mapped[str] = mapped_column(String(20))
    published_url: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "publication_id", "elapsed_hours", name="uq_metric_publication_elapsed"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    publication_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("publication_confirmations.id", ondelete="CASCADE")
    )
    elapsed_hours: Mapped[int] = mapped_column(Integer)
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    saves: Mapped[int] = mapped_column(Integer, default=0)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("story_records.id", ondelete="CASCADE"), index=True
    )
    state: Mapped[str] = mapped_column(String(50))
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
