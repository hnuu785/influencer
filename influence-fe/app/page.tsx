"use client";

import {
  ChangeEvent,
  FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { api, ApiError, downloadExport, uploadMediaFiles } from "./api";
import type {
  CalendarEvent,
  ContentFormat,
  ContentPackage,
  InterviewQuestion,
  Publication,
  RecordData,
  StoryCard,
  User,
} from "./types";

type Step = "capture" | "interview" | "story" | "packages" | "publish";
type Notice = { tone: "error" | "success"; message: string } | null;
type Answer = {
  question: string;
  answer_type: "text" | "voice";
  answer_text: string;
  visibility: "public_ok" | "private" | "exclude";
};

const formatLabels: Record<ContentFormat, string> = {
  reel: "Reel",
  carousel: "Carousel",
  story: "Story",
};

const supportedImageTypes = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/gif",
]);

function validateFiles(files: File[]): string | null {
  const photos = files.filter((file) => file.type.startsWith("image/"));
  if (photos.some((file) => !supportedImageTypes.has(file.type))) {
    return "사진은 JPG, PNG, WebP, GIF 형식만 추가할 수 있습니다.";
  }
  if (photos.length > 5) return "사진은 최대 5장입니다.";
  if (photos.some((file) => file.size > 10 * 1024 * 1024)) {
    return "사진은 장당 10MB까지입니다.";
  }
  const audioBytes = files
    .filter((file) => file.type.startsWith("audio/"))
    .reduce((sum, file) => sum + file.size, 0);
  if (audioBytes > 50 * 1024 * 1024) return "음성은 합계 50MB까지입니다.";
  const videoBytes = files
    .filter((file) => file.type.startsWith("video/"))
    .reduce((sum, file) => sum + file.size, 0);
  if (videoBytes > 200 * 1024 * 1024) return "영상은 합계 200MB까지입니다.";
  return null;
}

function FileItem({ file, onRemove }: { file: File; onRemove: () => void }) {
  const [previewUrl] = useState<string | null>(() =>
    file.type.startsWith("image/") ? URL.createObjectURL(file) : null,
  );

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  return (
    <div className="file-item">
      {previewUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={previewUrl} alt={`${file.name} 미리보기`} />
      ) : (
        <span>{file.type.startsWith("video") ? "영상" : "음성"}</span>
      )}
      <p>
        <strong>{file.name}</strong>
        <small>{(file.size / 1024 / 1024).toFixed(1)} MB · 업로드 준비됨</small>
      </p>
      <button type="button" onClick={onRemove} aria-label={`${file.name} 제거`}>×</button>
    </div>
  );
}

const steps: Array<{ id: Step; label: string; description: string }> = [
  { id: "capture", label: "기록 담기", description: "원하는 자료를 한 번에" },
  { id: "interview", label: "생각 더하기", description: "비동기 AI 질문" },
  { id: "story", label: "StoryCard", description: "내 이야기 선택" },
  { id: "packages", label: "제작안", description: "3가지 포맷" },
  { id: "publish", label: "게시 확인", description: "성과 직접 기록" },
];

function messageFrom(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "요청을 처리하지 못했습니다.";
}

function InviteLogin({ onLogin }: { onLogin: (user: User) => void }) {
  const [code, setCode] = useState("STORYLOG-BETA");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setNotice(null);
    try {
      const invited = await api<{ invite_token: string }>("/api/access/invite", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      const start = await api<{
        mode: "google" | "development";
        authorization_url: string | null;
      }>("/api/auth/google/start?invite_token=" + encodeURIComponent(invited.invite_token));
      if (start.mode === "google" && start.authorization_url) {
        window.location.href = start.authorization_url;
        return;
      }
      const user = await api<User>("/api/auth/development", {
        method: "POST",
        body: JSON.stringify({ invite_token: invited.invite_token }),
      });
      onLogin(user);
    } catch (error) {
      setNotice({ tone: "error", message: messageFrom(error) });
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-copy">
        <div className="logo"><span>S</span> 스토리로그</div>
        <p className="eyebrow">PRIVATE BETA</p>
        <h1>기록은 편하게.<br /><em>콘텐츠는 나답게.</em></h1>
        <p className="lead">
          텍스트, 음성, 사진, 영상을 한 번에 남기면 실제 경험을 근거로
          Instagram 제작안을 정리해 드려요.
        </p>
        <div className="login-proof">
          <span>01</span><p><strong>자료를 섞어 기록</strong>네 가지 입력을 원하는 만큼 조합해요.</p>
          <span>02</span><p><strong>내 이야기만 선택</strong>StoryCard에서 관점과 근거를 확인해요.</p>
          <span>03</span><p><strong>바로 제작 가능한 패키지</strong>Reel, Carousel, Story 제작안을 받아요.</p>
        </div>
      </section>
      <section className="login-panel">
        <form className="login-card" onSubmit={submit}>
          <div className="login-icon">✦</div>
          <h2>베타에 입장하기</h2>
          <p>초대 코드를 확인한 뒤 Google 계정으로 안전하게 시작합니다.</p>
          <label>
            초대 코드
            <input
              aria-label="초대 코드"
              value={code}
              onChange={(event) => setCode(event.target.value)}
              autoComplete="one-time-code"
            />
          </label>
          <button className="primary wide" disabled={loading || !code.trim()}>
            {loading ? "확인 중..." : "Google로 계속하기"}
          </button>
          {notice && <p className={"form-notice " + notice.tone}>{notice.message}</p>}
          <small>
            Calendar 연결은 선택입니다. 연결해도 직접 고른 일정의 제목과 시간만 사용해요.
          </small>
        </form>
      </section>
    </main>
  );
}

function StepRail({
  user,
  step,
  onLogout,
}: {
  user: User;
  step: Step;
  onLogout: () => void;
}) {
  const currentIndex = steps.findIndex((item) => item.id === step);
  return (
    <aside className="step-rail">
      <div className="logo"><span>S</span> 스토리로그</div>
      <nav aria-label="제작 단계">
        {steps.map((item, index) => (
          <div
            className={
              "step-item " +
              (index === currentIndex ? "active " : "") +
              (index < currentIndex ? "done" : "")
            }
            key={item.id}
          >
            <i>{index < currentIndex ? "✓" : index + 1}</i>
            <p><strong>{item.label}</strong><span>{item.description}</span></p>
          </div>
        ))}
      </nav>
      <div className="rail-user">
        <div className="avatar">{user.name.slice(0, 1)}</div>
        <p><strong>{user.name}</strong><span>{user.ai_mode === "openai" ? "AI 연결됨" : "체험 모드"}</span></p>
        <button type="button" onClick={onLogout}>로그아웃</button>
      </div>
    </aside>
  );
}

function AudioRecorder({
  label,
  onRecorded,
}: {
  label: string;
  onRecorded: (file: File) => void;
}) {
  const [recording, setRecording] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  async function toggle() {
    if (recording) {
      recorder.current?.stop();
      return;
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const next = new MediaRecorder(stream);
    chunks.current = [];
    next.ondataavailable = (event) => chunks.current.push(event.data);
    next.onstop = () => {
      const blob = new Blob(chunks.current, { type: next.mimeType || "audio/webm" });
      onRecorded(new File([blob], "voice-" + Date.now() + ".webm", { type: blob.type }));
      stream.getTracks().forEach((track) => track.stop());
      setRecording(false);
    };
    recorder.current = next;
    next.start();
    setRecording(true);
  }

  return (
    <button type="button" className={"record-button " + (recording ? "recording" : "")} onClick={toggle}>
      <span>{recording ? "■" : "●"}</span>{recording ? "녹음 끝내기" : label}
    </button>
  );
}

function CaptureStep({
  onCreated,
  setBusy,
}: {
  onCreated: (record: RecordData, questions: InterviewQuestion[]) => void;
  setBusy: (busy: boolean) => void;
}) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [selectedEvents, setSelectedEvents] = useState<string[]>([]);
  const [rights, setRights] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  async function loadCalendar() {
    try {
      setNotice(null);
      const start = await api<{
        mode: "google" | "development";
        authorization_url: string | null;
      }>("/api/calendar/start");
      if (start.mode === "google" && start.authorization_url) {
        window.location.href = start.authorization_url;
        return;
      }
      setEvents(await api<CalendarEvent[]>("/api/calendar/events"));
    } catch (error) {
      setNotice({ tone: "error", message: messageFrom(error) });
    }
  }

  function addFiles(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files ?? []);
    const next = [...files, ...selected];
    const validationMessage = validateFiles(next);
    if (validationMessage) {
      setNotice({ tone: "error", message: validationMessage });
    } else {
      setFiles(next);
      setNotice(null);
    }
    event.target.value = "";
  }

  async function submit() {
    if (!text.trim() && files.length === 0 && selectedEvents.length === 0) {
      setNotice({ tone: "error", message: "텍스트, 파일, 일정 중 하나 이상을 담아 주세요." });
      return;
    }
    if (files.length && !rights) {
      setNotice({ tone: "error", message: "파일 사용 권한과 등장 인물 공개 동의를 확인해 주세요." });
      return;
    }
    const body = new FormData();
    body.append("text", text);
    body.append("rights_confirmed", String(rights));
    body.append(
      "calendar_context_json",
      JSON.stringify(events.filter((item) => selectedEvents.includes(item.id))),
    );
    setBusy(true);
    setNotice(null);
    try {
      const uploaded = await uploadMediaFiles(files);
      body.append("uploaded_files_json", JSON.stringify(uploaded.uploadTokens));
      if (uploaded.mode === "multipart") {
        files.forEach((file) => body.append("files", file));
      }
      const record = await api<RecordData>("/api/records", { method: "POST", body });
      const questions = await api<InterviewQuestion[]>("/api/records/" + record.id + "/questions");
      onCreated(record, questions);
    } catch (error) {
      setNotice({ tone: "error", message: messageFrom(error) });
    } finally {
      setBusy(false);
    }
  }

  const totalSize = files.reduce((sum, file) => sum + file.size, 0);
  return (
    <section className="workspace-card capture-workspace">
      <div className="section-title">
        <p className="eyebrow">TODAY&apos;S LOG</p>
        <h1>오늘의 재료를<br /><em>한곳에 담아보세요.</em></h1>
        <p>하나만 써도 되고, 네 종류를 전부 섞어도 괜찮아요.</p>
      </div>
      <div className="input-basket">
        <label className="text-box">
          <span>텍스트 기록 <small>{text.length} / 5,000</small></span>
          <textarea
            maxLength={5000}
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="오늘 새로 알게 된 것, 예상과 달랐던 것, 누군가에게 전하고 싶은 생각을 편하게 적어보세요."
          />
        </label>
        <div className="add-row">
          <input
            ref={fileInput}
            hidden
            multiple
            type="file"
            accept="audio/*,image/jpeg,image/png,image/webp,image/gif,video/*"
            onChange={addFiles}
          />
          <button type="button" className="add-source" onClick={() => fileInput.current?.click()}>
            <b>＋</b><span><strong>사진·영상·음성 추가</strong>여러 자료를 계속 담을 수 있어요</span>
          </button>
          <AudioRecorder label="지금 음성으로 남기기" onRecorded={(file) => setFiles((list) => [...list, file])} />
          <button type="button" className="calendar-button" onClick={loadCalendar}>▣ 일정 가져오기</button>
        </div>
        {files.length > 0 && (
          <div className="file-list">
            {files.map((file, index) => (
              <FileItem
                file={file}
                key={file.name + index}
                onRemove={() => setFiles((list) => list.filter((_, itemIndex) => itemIndex !== index))}
              />
            ))}
            <small className="file-summary">{files.length}개 · {(totalSize / 1024 / 1024).toFixed(1)} MB</small>
          </div>
        )}
        {events.length > 0 && (
          <div className="calendar-events">
            <strong>맥락으로 사용할 일정만 고르세요</strong>
            {events.map((item) => (
              <label key={item.id}>
                <input
                  type="checkbox"
                  checked={selectedEvents.includes(item.id)}
                  onChange={() => setSelectedEvents((current) =>
                    current.includes(item.id)
                      ? current.filter((id) => id !== item.id)
                      : [...current, item.id],
                  )}
                />
                <span>{new Date(item.start_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}</span>
                {item.title}
              </label>
            ))}
          </div>
        )}
        {files.length > 0 && (
          <label className="rights-check">
            <input type="checkbox" checked={rights} onChange={(event) => setRights(event.target.checked)} />
            이 파일을 콘텐츠에 사용할 권리가 있고, 등장 인물의 공개 동의를 확인했습니다.
          </label>
        )}
      </div>
      <div className="limit-note">
        <span>텍스트 5천 자</span><span>음성 합계 3분</span><span>사진 5장</span><span>영상 합계 3분·200MB</span>
      </div>
      {notice && <p className={"form-notice " + notice.tone}>{notice.message}</p>}
      <button className="primary next" onClick={submit}>이 기록으로 시작하기 <span>→</span></button>
    </section>
  );
}

function InterviewStep({
  record,
  questions,
  onDone,
  setBusy,
}: {
  record: RecordData;
  questions: InterviewQuestion[];
  onDone: (cards: StoryCard[]) => void;
  setBusy: (busy: boolean) => void;
}) {
  const [answers, setAnswers] = useState<Answer[]>(questions.map((item) => ({
    question: item.text,
    answer_type: "text",
    answer_text: "",
    visibility: "public_ok",
  })));
  const [topics, setTopics] = useState("AI, 제품 만들기");
  const [audience, setAudience] = useState("AI를 실제 업무에 적용하려는 한국어 실무자");
  const [tone, setTone] = useState("담백하고 구체적으로, 과장 없이");
  const [taboo, setTaboo] = useState("");
  const [notice, setNotice] = useState<Notice>(null);

  function updateAnswer(index: number, changes: Partial<Answer>) {
    setAnswers((current) => current.map((item, itemIndex) =>
      itemIndex === index ? { ...item, ...changes } : item,
    ));
  }

  async function transcribeVoice(index: number, file: File) {
    const body = new FormData();
    body.append("file", file);
    setBusy(true);
    try {
      const result = await api<{ text: string }>("/api/transcribe", { method: "POST", body });
      updateAnswer(index, { answer_type: "voice", answer_text: result.text });
    } catch (error) {
      setNotice({ tone: "error", message: messageFrom(error) });
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    const completed = answers.filter((item) => item.answer_text.trim());
    if (!completed.length) {
      setNotice({ tone: "error", message: "질문 하나 이상에 답해 주세요." });
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      const cards = await api<StoryCard[]>("/api/records/" + record.id + "/answers", {
        method: "POST",
        body: JSON.stringify({
          answers: completed,
          profile: {
            topics: topics.split(",").map((item) => item.trim()).filter(Boolean),
            audience,
            tone,
            taboo_topics: taboo.split(",").map((item) => item.trim()).filter(Boolean),
          },
        }),
      });
      onDone(cards);
    } catch (error) {
      setNotice({ tone: "error", message: messageFrom(error) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="workspace-card">
      <div className="section-title compact">
        <p className="eyebrow">A LITTLE MORE CONTEXT</p>
        <h1>당신의 생각을<br /><em>조금만 더 들려주세요.</em></h1>
        <p>실시간 통화가 아니에요. 편한 때에 글이나 음성으로 답하면 됩니다.</p>
      </div>
      <div className="question-list">
        {questions.map((question, index) => (
          <article className="question-card" key={question.id}>
            <div><span>0{index + 1}</span><p><strong>{question.text}</strong><small>{question.purpose}</small></p></div>
            <textarea
              value={answers[index]?.answer_text ?? ""}
              onChange={(event) => updateAnswer(index, { answer_text: event.target.value, answer_type: "text" })}
              placeholder="떠오르는 대로 답해주세요."
            />
            <div className="question-actions">
              <AudioRecorder label="음성으로 답하기" onRecorded={(file) => transcribeVoice(index, file)} />
              <select
                value={answers[index]?.visibility}
                onChange={(event) => updateAnswer(index, { visibility: event.target.value as Answer["visibility"] })}
              >
                <option value="public_ok">콘텐츠에 사용 가능</option>
                <option value="private">맥락으로만 사용</option>
                <option value="exclude">AI에게 보내지 않음</option>
              </select>
            </div>
          </article>
        ))}
      </div>
      <div className="brand-profile">
        <h2>처음 한 번만 알려주세요</h2>
        <p>다음 기록부터 개인 RAG가 승인 이력과 함께 이 기준을 찾아옵니다.</p>
        <div className="profile-grid">
          <label>주제 <input value={topics} onChange={(event) => setTopics(event.target.value)} /></label>
          <label>목표 독자 <input value={audience} onChange={(event) => setAudience(event.target.value)} /></label>
          <label>말투 <input value={tone} onChange={(event) => setTone(event.target.value)} /></label>
          <label>금지 표현 <input value={taboo} onChange={(event) => setTaboo(event.target.value)} placeholder="쉼표로 구분" /></label>
        </div>
      </div>
      {notice && <p className={"form-notice " + notice.tone}>{notice.message}</p>}
      <button className="primary next" onClick={submit}>StoryCard 만들기 <span>→</span></button>
    </section>
  );
}

function StoryStep({
  record,
  initialCards,
  onApproved,
  setBusy,
}: {
  record: RecordData;
  initialCards: StoryCard[];
  onApproved: (packages: ContentPackage[]) => void;
  setBusy: (busy: boolean) => void;
}) {
  const [cards, setCards] = useState(initialCards);
  const [selected, setSelected] = useState(initialCards[0]?.id ?? "");
  const [notice, setNotice] = useState<Notice>(null);

  function updateCard(id: string, field: keyof StoryCard, value: string) {
    setCards((current) => current.map((item) => item.id === id ? { ...item, [field]: value } : item));
  }

  async function reject(card: StoryCard) {
    setBusy(true);
    try {
      await api("/api/records/" + record.id + "/story-cards/" + card.id + "/decision", {
        method: "POST",
        body: JSON.stringify({ action: "reject", rejection_reason: "내 이야기 아님" }),
      });
      const remaining = cards.filter((item) => item.id !== card.id);
      setCards(remaining);
      setSelected(remaining[0]?.id ?? "");
    } catch (error) {
      setNotice({ tone: "error", message: messageFrom(error) });
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    const card = cards.find((item) => item.id === selected);
    if (!card) return;
    setBusy(true);
    setNotice(null);
    try {
      const packages = await api<ContentPackage[]>(
        "/api/records/" + record.id + "/story-cards/" + card.id + "/decision",
        {
          method: "POST",
          body: JSON.stringify({
            action: "approve",
            edits: {
              event: card.event,
              observation: card.observation,
              emotion: card.emotion,
              opinion: card.opinion,
              evidence_level: card.evidence_level,
              content_angles: card.content_angles,
              source_excerpt: card.source_excerpt,
            },
          }),
        },
      );
      onApproved(packages);
    } catch (error) {
      setNotice({ tone: "error", message: messageFrom(error) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="workspace-card wide-card">
      <div className="section-title compact centered">
        <p className="eyebrow">YOUR STORY, NOT GENERIC CONTENT</p>
        <h1>어떤 이야기가<br /><em>가장 나다운가요?</em></h1>
        <p>하나를 골라 직접 고친 뒤 승인하세요. 원문 근거도 함께 확인할 수 있어요.</p>
      </div>
      <div className="storycard-grid">
        {cards.map((card, index) => (
          <article className={"storycard " + (selected === card.id ? "selected" : "")} key={card.id} onClick={() => setSelected(card.id)}>
            <header><span>STORY 0{index + 1}</span><i>{selected === card.id ? "✓ 선택됨" : "선택"}</i></header>
            <label>경험<input value={card.event} onChange={(event) => updateCard(card.id, "event", event.target.value)} /></label>
            <label>관찰<textarea value={card.observation} onChange={(event) => updateCard(card.id, "observation", event.target.value)} /></label>
            <label>내 관점<textarea value={card.opinion} onChange={(event) => updateCard(card.id, "opinion", event.target.value)} /></label>
            <blockquote><small>원문 근거</small>{card.source_excerpt}</blockquote>
            <div className="story-tags">{card.content_angles.map((angle) => <span key={angle}>{angle}</span>)}</div>
            <button className="reject-link" onClick={(event) => { event.stopPropagation(); reject(card); }}>이 이야기는 제외</button>
          </article>
        ))}
      </div>
      {cards.length === 0 && <p className="empty-state">모든 후보를 제외했어요. 이전 단계에서 답변을 보완해 다시 만들어 주세요.</p>}
      {notice && <p className={"form-notice " + notice.tone}>{notice.message}</p>}
      <button className="primary next" disabled={!selected} onClick={approve}>이 StoryCard로 제작안 만들기 <span>→</span></button>
    </section>
  );
}

function PackagePreview({ item }: { item: ContentPackage }) {
  if (item.format === "reel") {
    return (
      <div className="phone-preview reel-preview">
        <div className="mock-top">Reel · 0:25</div>
        <div className="mock-visual">원본<br />장면</div>
        <strong>{item.hook_options[0]}</strong>
        <small>@yourstory</small>
      </div>
    );
  }
  if (item.format === "carousel") {
    return (
      <div className="carousel-preview">
        <div className="carousel-dots"><i /><i /><i /></div>
        <p>01</p><strong>{item.hook_options[0]}</strong><span>밀어서 확인 →</span>
      </div>
    );
  }
  return (
    <div className="phone-preview story-preview">
      <div className="mock-top">Your story · 지금</div>
      <div className="mock-visual">원본 사진</div>
      <strong>{item.hook_options[0]}</strong>
      <button>{item.cta}</button>
    </div>
  );
}

function PackagesStep({
  record,
  initialPackages,
  onContinue,
  setBusy,
}: {
  record: RecordData;
  initialPackages: ContentPackage[];
  onContinue: () => void;
  setBusy: (busy: boolean) => void;
}) {
  const [packages, setPackages] = useState(initialPackages);
  const [active, setActive] = useState<ContentFormat>("reel");
  const [selected, setSelected] = useState<string[]>([]);
  const [notice, setNotice] = useState<Notice>(null);
  const item = packages.find((entry) => entry.format === active) ?? packages[0];

  function updateCurrent(field: "script_or_copy" | "captions" | "cta", value: string) {
    setPackages((current) => current.map((entry) => entry.id === item.id
      ? {
          ...entry,
          [field]: field === "cta" ? value : value.split("\n").filter((line) => line.trim()),
          status: "waiting_for_approval",
        }
      : entry,
    ));
  }

  async function saveAndApprove() {
    setBusy(true);
    setNotice(null);
    try {
      let updated = await api<ContentPackage>("/api/packages/" + item.id, {
        method: "PATCH",
        body: JSON.stringify({
          script_or_copy: item.script_or_copy,
          captions: item.captions,
          cta: item.cta,
        }),
      });
      for (const issue of updated.quality_issues.filter((entry) => !entry.resolution)) {
        await api("/api/quality-issues/" + issue.id + "/resolve", {
          method: "POST",
          body: JSON.stringify({ resolution: "acknowledged" }),
        });
      }
      updated = await api<ContentPackage>("/api/packages/" + item.id + "/decision", {
        method: "POST",
        body: JSON.stringify({ action: "approve" }),
      });
      setPackages((current) => current.map((entry) => entry.id === updated.id ? updated : entry));
      setSelected((current) => current.includes(updated.id) ? current : [...current, updated.id]);
      setNotice({ tone: "success", message: formatLabels[updated.format] + " 제작안을 승인했습니다." });
    } catch (error) {
      setNotice({ tone: "error", message: messageFrom(error) });
    } finally {
      setBusy(false);
    }
  }

  async function exportZip() {
    if (!selected.length) {
      setNotice({ tone: "error", message: "먼저 하나 이상의 제작안을 승인해 주세요." });
      return;
    }
    setBusy(true);
    try {
      await downloadExport(record.id, selected);
      setNotice({ tone: "success", message: "선택한 제작안과 원본 자료를 ZIP으로 내려받았습니다." });
    } catch (error) {
      setNotice({ tone: "error", message: messageFrom(error) });
    } finally {
      setBusy(false);
    }
  }

  async function copyPackage() {
    const text = [
      formatLabels[item.format],
      "",
      "훅",
      ...item.hook_options,
      "",
      "대사·카피",
      ...item.script_or_copy,
      "",
      "CTA",
      item.cta,
    ].join("\n");
    await navigator.clipboard.writeText(text);
    setNotice({ tone: "success", message: "제작안을 클립보드에 복사했습니다." });
  }

  if (!item) return null;
  return (
    <section className="workspace-card package-workspace">
      <div className="package-heading">
        <div><p className="eyebrow">READY TO CREATE</p><h1>한 이야기,<br /><em>세 가지 제작안.</em></h1></div>
        <p>완성 미디어가 아닌 촬영·디자인 전 목업입니다.<br />Reel을 먼저 추천하지만 원하는 포맷만 골라도 돼요.</p>
      </div>
      <div className="format-tabs">
        {(["reel", "carousel", "story"] as ContentFormat[]).map((format) => {
          const entry = packages.find((candidate) => candidate.format === format);
          return (
            <button className={active === format ? "active" : ""} key={format} onClick={() => setActive(format)}>
              <span>{format === "reel" ? "▶" : format === "carousel" ? "▦" : "◯"}</span>
              <p><strong>{formatLabels[format]}</strong><small>{format === "reel" ? "발견·도달 · 추천" : format === "carousel" ? "저장·공유" : "관계·피드백"}</small></p>
              {entry?.status === "approved" && <i>✓</i>}
            </button>
          );
        })}
      </div>
      <div className="package-grid">
        <aside className="preview-panel">
          <p className="panel-kicker">제작 전 목업 미리보기</p>
          <PackagePreview item={item} />
          <div className="reference-note">
            <strong>참고한 포맷 패턴</strong>
            <p>{item.reference_refs.length ? "권리가 확인된 시드 패턴 " + item.reference_refs.length + "개" : "기본 " + formatLabels[item.format] + " 템플릿"}</p>
            <small>원문이나 캡션을 복사하지 않고 구조와 선정 이유만 참고합니다.</small>
          </div>
        </aside>
        <div className="package-editor">
          <div className="hook-box">
            <span>훅 선택지 3개</span>
            {item.hook_options.map((hook, index) => <p key={hook}><i>{index + 1}</i>{hook}</p>)}
          </div>
          <h2>Storyboard</h2>
          <div className="storyboard-list">
            {item.storyboard.map((beat) => (
              <article key={beat.order}>
                <header><span>{beat.timing}</span><strong>{beat.label}</strong></header>
                <p>{beat.content}</p>
                <small>{beat.visual} · {beat.production_note}</small>
              </article>
            ))}
          </div>
          <label className="editor-field">
            대사·카피 <small>줄마다 하나의 장면·슬라이드·프레임으로 다뤄집니다.</small>
            <textarea value={item.script_or_copy.join("\n")} onChange={(event) => updateCurrent("script_or_copy", event.target.value)} />
          </label>
          <label className="editor-field">
            자막·캡션
            <textarea value={item.captions.join("\n")} onChange={(event) => updateCurrent("captions", event.target.value)} />
          </label>
          <label className="editor-field">
            CTA
            <input value={item.cta} onChange={(event) => updateCurrent("cta", event.target.value)} />
          </label>
          {item.production_instructions.length > 0 && (
            <div className="production-notes"><strong>촬영·편집 체크리스트</strong>{item.production_instructions.map((note) => <p key={note}>✓ {note}</p>)}</div>
          )}
          {item.quality_issues.length > 0 && (
            <div className="warning-box">
              <strong>내보내기 전에 확인해 주세요</strong>
              {item.quality_issues.map((issue) => (
                <p key={issue.id}><span>{issue.category === "privacy" ? "개인정보" : issue.category === "factuality" ? "원문 근거" : "원본성"}</span>{issue.message}</p>
              ))}
              <small>승인을 누르면 현재 수정 내용을 저장하고 위 경고를 확인한 것으로 기록합니다.</small>
            </div>
          )}
          <div className="package-actions">
            <button className="secondary" onClick={copyPackage}>내용 복사</button>
            <button className="primary" onClick={saveAndApprove}>{item.status === "approved" ? "수정본 다시 승인" : formatLabels[item.format] + " 승인"}</button>
          </div>
        </div>
      </div>
      {notice && <p className={"form-notice " + notice.tone}>{notice.message}</p>}
      <div className="export-bar">
        <p><strong>{selected.length}개 포맷 승인됨</strong><span>승인한 포맷만 골라 ZIP으로 받을 수 있어요.</span></p>
        <button className="secondary" onClick={exportZip}>ZIP 내려받기</button>
        <button className="primary" disabled={!selected.length} onClick={onContinue}>Instagram에 직접 게시했어요 →</button>
      </div>
    </section>
  );
}

function PublishStep({
  record,
  onSaved,
  onDeleted,
  setBusy,
}: {
  record: RecordData;
  onSaved: () => void;
  onDeleted: () => void;
  setBusy: (busy: boolean) => void;
}) {
  const [format, setFormat] = useState<ContentFormat>("reel");
  const [url, setUrl] = useState("");
  const [publication, setPublication] = useState<Publication | null>(null);
  const [metrics, setMetrics] = useState({
    views: "0", likes: "0", comments: "0", shares: "0", saves: "0",
  });
  const [elapsed, setElapsed] = useState<24 | 72>(24);
  const [notice, setNotice] = useState<Notice>(null);

  async function savePublication() {
    setBusy(true);
    try {
      const result = await api<Publication>("/api/records/" + record.id + "/publication", {
        method: "POST",
        body: JSON.stringify({
          format,
          published_url: url,
          published_at: new Date().toISOString(),
        }),
      });
      setPublication(result);
      setNotice({ tone: "success", message: "게시 URL을 저장했습니다. 24시간 후 성과를 남겨보세요." });
    } catch (error) {
      setNotice({ tone: "error", message: messageFrom(error) });
    } finally {
      setBusy(false);
    }
  }

  async function saveMetric() {
    if (!publication) return;
    setBusy(true);
    try {
      await api("/api/publications/" + publication.id + "/metrics", {
        method: "POST",
        body: JSON.stringify({
          elapsed_hours: elapsed,
          views: Number(metrics.views),
          likes: Number(metrics.likes),
          comments: Number(metrics.comments),
          shares: Number(metrics.shares),
          saves: Number(metrics.saves),
        }),
      });
      setNotice({ tone: "success", message: elapsed + "시간 성과를 저장했습니다." });
      onSaved();
    } catch (error) {
      setNotice({ tone: "error", message: messageFrom(error) });
    } finally {
      setBusy(false);
    }
  }

  async function deleteCurrentRecord() {
    if (!window.confirm("이 기록과 연결된 StoryCard, 제작안, 파일을 모두 삭제할까요?")) return;
    setBusy(true);
    try {
      await api("/api/records/" + record.id, { method: "DELETE" });
      onDeleted();
    } catch (error) {
      setNotice({ tone: "error", message: messageFrom(error) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="workspace-card publish-workspace">
      <div className="section-title centered">
        <p className="eyebrow">YOU STAY IN CONTROL</p>
        <h1>직접 게시한 결과를<br /><em>다음 이야기에 연결하세요.</em></h1>
        <p>스토리로그가 자동 게시하지 않습니다. Instagram에서 게시한 URL과 성과만 남겨주세요.</p>
      </div>
      <div className="publish-grid">
        <article>
          <span className="card-number">01</span>
          <h2>게시 URL 등록</h2>
          <p>직접 완성하고 게시한 콘텐츠의 링크를 붙여넣으세요.</p>
          <div className="mini-tabs">
            {(["reel", "carousel", "story"] as ContentFormat[]).map((item) => <button className={format === item ? "active" : ""} onClick={() => setFormat(item)} key={item}>{formatLabels[item]}</button>)}
          </div>
          <input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://www.instagram.com/..." />
          <button className="primary wide" disabled={!url.trim()} onClick={savePublication}>게시 확인 저장</button>
        </article>
        <article className={!publication ? "disabled-card" : ""}>
          <span className="card-number">02</span>
          <h2>성과 스냅샷</h2>
          <p>조회수보다 꾸준한 게시와 포맷별 반응을 함께 봅니다.</p>
          <div className="mini-tabs">
            <button className={elapsed === 24 ? "active" : ""} onClick={() => setElapsed(24)}>24시간</button>
            <button className={elapsed === 72 ? "active" : ""} onClick={() => setElapsed(72)}>72시간</button>
          </div>
          <div className="metric-grid">
            {Object.entries(metrics).map(([key, value]) => (
              <label key={key}>
                {{ views: "조회", likes: "좋아요", comments: "댓글", shares: "공유", saves: "저장" }[key]}
                <input type="number" min="0" value={value} onChange={(event) => setMetrics((current) => ({ ...current, [key]: event.target.value }))} />
              </label>
            ))}
          </div>
          <button className="primary wide" disabled={!publication} onClick={saveMetric}>성과 저장</button>
        </article>
      </div>
      {notice && <p className={"form-notice " + notice.tone}>{notice.message}</p>}
      <div className="learning-note"><span>↗</span><p><strong>성과는 취향이 아닙니다</strong>반응 수치는 다음 추천의 참고로만 사용하고, 사용자가 승인한 관점과 말투를 우선합니다.</p></div>
      <button className="delete-record" onClick={deleteCurrentRecord}>이 기록과 파생 데이터 삭제</button>
    </section>
  );
}

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState<Step>("capture");
  const [record, setRecord] = useState<RecordData | null>(null);
  const [questions, setQuestions] = useState<InterviewQuestion[]>([]);
  const [cards, setCards] = useState<StoryCard[]>([]);
  const [packages, setPackages] = useState<ContentPackage[]>([]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let active = true;
    api<User>("/api/me")
      .then((currentUser) => { if (active) setUser(currentUser); })
      .catch(() => { if (active) setUser(null); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  const currentTitle = useMemo(() => steps.find((item) => item.id === step)?.label, [step]);

  async function logout() {
    await api("/api/auth/logout", { method: "POST" });
    setUser(null);
    setStep("capture");
  }

  if (loading) return <main className="splash"><div className="logo"><span>S</span> 스토리로그</div><p>작업 공간을 여는 중...</p></main>;
  if (!user) return <InviteLogin onLogin={setUser} />;

  return (
    <div className="app">
      <StepRail user={user} step={step} onLogout={logout} />
      <main className="main-stage">
        <header className="mobile-header">
          <div className="logo"><span>S</span> 스토리로그</div>
          <div className="mobile-header-actions">
            <small>{currentTitle}</small>
            <button type="button" onClick={logout}>로그아웃</button>
          </div>
        </header>
        {step === "capture" && (
          <CaptureStep
            setBusy={setBusy}
            onCreated={(created, nextQuestions) => {
              setRecord(created);
              setQuestions(nextQuestions);
              setStep("interview");
            }}
          />
        )}
        {step === "interview" && record && (
          <InterviewStep
            record={record}
            questions={questions}
            setBusy={setBusy}
            onDone={(nextCards) => { setCards(nextCards); setStep("story"); }}
          />
        )}
        {step === "story" && record && (
          <StoryStep
            record={record}
            initialCards={cards}
            setBusy={setBusy}
            onApproved={(nextPackages) => { setPackages(nextPackages); setStep("packages"); }}
          />
        )}
        {step === "packages" && record && (
          <PackagesStep record={record} initialPackages={packages} setBusy={setBusy} onContinue={() => setStep("publish")} />
        )}
        {step === "publish" && record && (
          <PublishStep
            record={record}
            setBusy={setBusy}
            onSaved={() => setSaved(true)}
            onDeleted={() => {
              setRecord(null);
              setCards([]);
              setPackages([]);
              setSaved(false);
              setStep("capture");
            }}
          />
        )}
        {saved && <div className="saved-toast">✓ 저장되었습니다</div>}
      </main>
      {busy && <div className="busy-layer"><div className="spinner" /><strong>스토리로그가 정리하고 있어요</strong><span>원문 근거와 개인 맥락을 함께 확인합니다.</span></div>}
    </div>
  );
}
