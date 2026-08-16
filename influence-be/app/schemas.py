from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


ContentFormat = Literal["reel", "carousel", "story"]


class InviteRequest(BaseModel):
    code: str = Field(min_length=1, max_length=100)


class InviteResponse(BaseModel):
    invite_token: str
    expires_in_seconds: int


class AuthStartResponse(BaseModel):
    mode: Literal["google", "development"]
    authorization_url: str | None = None


class DevelopmentLoginRequest(BaseModel):
    invite_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    picture_url: str | None
    calendar_connected: bool
    ai_mode: Literal["openai", "demo"]


class CalendarEventSchema(BaseModel):
    id: str
    title: str
    start_at: datetime
    end_at: datetime
    selected: bool = False
    source: Literal["google", "development"] = "google"


class BrandProfileInput(BaseModel):
    topics: list[str] = Field(min_length=1, max_length=10)
    audience: str = Field(min_length=1, max_length=300)
    tone: str = Field(min_length=1, max_length=200)
    taboo_topics: list[str] = Field(default_factory=list, max_length=20)


class SourceAssetResponse(BaseModel):
    id: str
    type: Literal["text", "audio", "photo", "video"]
    filename: str | None
    size_bytes: int
    duration_ms: int | None
    transcript: str | None = None


class RecordResponse(BaseModel):
    id: str
    state: str
    title: str
    sources: list[SourceAssetResponse]
    calendar_context: list[CalendarEventSchema]


class InterviewQuestion(BaseModel):
    id: str
    text: str
    purpose: str
    optional: bool = True


class ConversationAnswerInput(BaseModel):
    question: str
    answer_type: Literal["text", "voice"]
    answer_text: str = Field(min_length=1, max_length=5000)
    visibility: Literal["public_ok", "private", "exclude"] = "public_ok"


class ConversationAnswersRequest(BaseModel):
    answers: list[ConversationAnswerInput] = Field(max_length=4)
    profile: BrandProfileInput


class StoryCardCandidate(BaseModel):
    event: str
    observation: str
    emotion: str = ""
    opinion: str
    evidence_level: Literal[
        "personal_observation", "direct_quote", "calendar_context"
    ] = "personal_observation"
    content_angles: list[str] = Field(min_length=1, max_length=3)
    source_excerpt: str


class StoryCardBatch(BaseModel):
    cards: list[StoryCardCandidate] = Field(min_length=1, max_length=3)


class StoryCardResponse(StoryCardCandidate):
    id: str
    status: str
    source_refs: list[dict]


class StoryCardDecisionRequest(BaseModel):
    action: Literal["approve", "reject"]
    edits: StoryCardCandidate | None = None
    rejection_reason: Literal[
        "내 이야기 아님", "말투가 다름", "쓸모 없음", "공개할 수 없음"
    ] | None = None
    note: str | None = Field(default=None, max_length=500)


class ContentBriefSchema(BaseModel):
    audience: str
    objective: str
    core_message: str
    proof_points: list[str]
    constraints: list[str]


class StoryboardBeat(BaseModel):
    order: int
    label: str
    timing: str
    visual: str
    content: str
    production_note: str


class GeneratedPackage(BaseModel):
    format: ContentFormat
    objective: str
    hook_options: list[str] = Field(default_factory=list, max_length=3)
    storyboard: list[StoryboardBeat] = Field(min_length=1, max_length=10)
    script_or_copy: list[str] = Field(min_length=1, max_length=20)
    captions: list[str] = Field(default_factory=list, max_length=20)
    cta: str
    production_instructions: list[str] = Field(min_length=1, max_length=12)


class PackageGenerationResult(BaseModel):
    brief: ContentBriefSchema
    packages: list[GeneratedPackage] = Field(min_length=3, max_length=3)


class GeneratedQualityIssue(BaseModel):
    format: ContentFormat
    category: Literal["factuality", "privacy", "similarity"]
    severity: Literal["info", "warning", "high"]
    target_ref: str
    source_ref: str | None = None
    message: str


class QualityBatch(BaseModel):
    issues: list[GeneratedQualityIssue] = Field(default_factory=list, max_length=12)


class QualityIssueResponse(GeneratedQualityIssue):
    id: str
    resolution: str | None


class ContentPackageResponse(GeneratedPackage):
    id: str
    status: str
    approved_copy: str | None
    source_refs: list[dict]
    reference_refs: list[str]
    quality_issues: list[QualityIssueResponse]


class PackageUpdateRequest(BaseModel):
    script_or_copy: list[str] = Field(min_length=1, max_length=20)
    captions: list[str] = Field(default_factory=list, max_length=20)
    cta: str = Field(min_length=1, max_length=500)


class PackageDecisionRequest(BaseModel):
    action: Literal["approve", "unapprove"]


class QualityResolutionRequest(BaseModel):
    resolution: Literal["edited", "excluded", "acknowledged"]


class ExportRequest(BaseModel):
    package_ids: list[str] = Field(min_length=1, max_length=3)


class PublicationRequest(BaseModel):
    format: ContentFormat
    published_url: HttpUrl
    published_at: datetime


class PublicationResponse(BaseModel):
    id: str
    format: ContentFormat
    published_url: str
    published_at: datetime


class MetricInput(BaseModel):
    elapsed_hours: Literal[24, 72]
    views: int = Field(ge=0)
    likes: int = Field(ge=0)
    comments: int = Field(ge=0)
    shares: int = Field(ge=0)
    saves: int = Field(ge=0)
