export type ContentFormat = "reel" | "carousel" | "story";

export type User = {
  id: string;
  email: string;
  name: string;
  picture_url: string | null;
  calendar_connected: boolean;
  ai_mode: "openai" | "demo";
};

export type CalendarEvent = {
  id: string;
  title: string;
  start_at: string;
  end_at: string;
  selected: boolean;
  source: "google" | "development";
};

export type SourceAsset = {
  id: string;
  type: "text" | "audio" | "photo" | "video";
  filename: string | null;
  size_bytes: number;
  duration_ms: number | null;
  transcript: string | null;
};

export type RecordData = {
  id: string;
  state: string;
  title: string;
  sources: SourceAsset[];
  calendar_context: CalendarEvent[];
};

export type InterviewQuestion = {
  id: string;
  text: string;
  purpose: string;
  optional: boolean;
};

export type StoryCard = {
  id: string;
  event: string;
  observation: string;
  emotion: string;
  opinion: string;
  evidence_level: string;
  content_angles: string[];
  source_excerpt: string;
  status: string;
  source_refs: Array<Record<string, unknown>>;
};

export type StoryboardBeat = {
  order: number;
  label: string;
  timing: string;
  visual: string;
  content: string;
  production_note: string;
};

export type QualityIssue = {
  id: string;
  format: ContentFormat;
  category: "factuality" | "privacy" | "similarity";
  severity: "info" | "warning" | "high";
  target_ref: string;
  source_ref: string | null;
  message: string;
  resolution: string | null;
};

export type ContentPackage = {
  id: string;
  format: ContentFormat;
  objective: string;
  hook_options: string[];
  storyboard: StoryboardBeat[];
  script_or_copy: string[];
  captions: string[];
  cta: string;
  production_instructions: string[];
  status: string;
  approved_copy: string | null;
  source_refs: Array<Record<string, unknown>>;
  reference_refs: string[];
  quality_issues: QualityIssue[];
};

export type Publication = {
  id: string;
  format: ContentFormat;
  published_url: string;
  published_at: string;
};
