"use client";

import { FormEvent, useMemo, useState } from "react";

type Channel = "LinkedIn" | "X" | "Instagram";

type StoryCard = {
  id: string;
  status: "STORY_MINED";
  visibility: "PRIVATE";
  title: string;
  event: string;
  observation: string;
  lesson: string;
  source_refs: { label: string; excerpt: string }[];
  angles: { id: string; label: string; focus: string }[];
  drafts: {
    channel: Channel;
    content: string;
    status: "NEEDS_REVIEW";
    source_refs: string[];
  }[];
  quality_check: {
    facts_grounded: boolean;
    source_visible: boolean;
    human_approval_required: boolean;
    note: string;
  };
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
const channels: Channel[] = ["LinkedIn", "X", "Instagram"];

const prompts = [
  { label: "오늘 새로 알게 된 것", hint: "처음 알게 된 사실이나 방법을 기록해 보세요." },
  { label: "예상과 달랐던 것", hint: "기대와 실제가 달랐던 순간에서 이야기가 시작됩니다." },
  { label: "누군가에게 말해 주고 싶은 것", hint: "같은 고민을 하는 사람에게 건넬 말을 적어 보세요." },
  { label: "오늘 선택에서 배운 것", hint: "선택과 결과, 다음에 바꿀 점을 이어서 적어 보세요." },
];

const example = {
  event: "오늘 팀 회의에서 새 기능을 크게 만드는 대신, 사용자가 실제로 반복하는 한 가지 행동부터 검증하기로 했다.",
  unexpected: "기능 아이디어가 많을수록 설득력이 높을 거라 생각했지만, 팀은 가장 작은 실험에 더 빠르게 합의했다.",
  lesson: "좋은 시작은 많은 기능이 아니라 한 가지 가설을 끝까지 검증하는 데서 나온다.",
};

function ArrowIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

function MicIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <rect x="8" y="3" width="8" height="13" rx="4" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6" />
    </svg>
  );
}

function TextIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M5 5h14M12 5v14M8 19h8" />
    </svg>
  );
}

function MediaIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <circle cx="9" cy="10" r="2" />
      <path d="m5 17 4-4 3 3 2-2 5 3" />
    </svg>
  );
}

export default function Home() {
  const [activePrompt, setActivePrompt] = useState(0);
  const [eventText, setEventText] = useState("");
  const [unexpected, setUnexpected] = useState("");
  const [lesson, setLesson] = useState("");
  const [audience, setAudience] = useState("비슷한 고민을 하는 사람");
  const [selectedChannels, setSelectedChannels] = useState<Channel[]>(channels);
  const [story, setStory] = useState<StoryCard | null>(null);
  const [activeChannel, setActiveChannel] = useState<Channel>("LinkedIn");
  const [activeAngle, setActiveAngle] = useState("lesson");
  const [feedback, setFeedback] = useState<"mine" | "fact" | "risk" | null>(null);
  const [approved, setApproved] = useState(false);
  const [copied, setCopied] = useState(false);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [capabilityNotice, setCapabilityNotice] = useState("");

  const activeDraft = useMemo(
    () => story?.drafts.find((draft) => draft.channel === activeChannel) ?? story?.drafts[0],
    [activeChannel, story],
  );

  function loadExample() {
    setEventText(example.event);
    setUnexpected(example.unexpected);
    setLesson(example.lesson);
  }

  function toggleChannel(channel: Channel) {
    setSelectedChannels((current) => {
      if (current.includes(channel)) {
        return current.length === 1 ? current : current.filter((item) => item !== channel);
      }
      return [...current, channel];
    });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("loading");
    setApproved(false);
    setFeedback(null);
    setCopied(false);

    try {
      const response = await fetch(`${apiUrl}/api/story-cards`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event: eventText,
          unexpected,
          lesson,
          audience,
          channels: selectedChannels,
        }),
      });

      if (!response.ok) throw new Error("Story card request failed");
      const nextStory = (await response.json()) as StoryCard;
      setStory(nextStory);
      setActiveChannel(nextStory.drafts[0].channel);
      setActiveAngle(nextStory.angles[0].id);
      setStatus("idle");
    } catch {
      setStatus("error");
    }
  }

  async function copyDraft() {
    if (!activeDraft) return;
    await navigator.clipboard.writeText(activeDraft.content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  function showComingSoon(type: "voice" | "media") {
    setCapabilityNotice(
      type === "voice"
        ? "음성 기록·자동 전사는 다음 구현 단계입니다. 지금은 텍스트 기록 흐름을 끝까지 검증합니다."
        : "사진·영상 근거 연결은 다음 구현 단계입니다. 지금은 텍스트 기록을 사용할 수 있습니다.",
    );
  }

  return (
    <div className="site-shell">
      <header className="site-header">
        <a className="brand" href="#top" aria-label="스토리로그 홈">
          <span className="brand-mark">S</span>
          <span>STORYLOG</span>
        </a>
        <nav aria-label="주요 메뉴">
          <a className="active" href="#capture">오늘의 기록</a>
          <a href="#workflow">작동 방식</a>
          <a href="#monetize">수익화</a>
          <a href={`${apiUrl}/docs`}>API</a>
        </nav>
        <a className="header-cta" href="#capture">
          오늘 기록하기 <ArrowIcon />
        </a>
      </header>

      <main id="top">
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow"><span /> FROM REAL DAY TO REAL INFLUENCE</p>
            <h1 id="hero-title">
              나의 하루가<br />
              <em>나다운 콘텐츠가 된다.</em>
            </h1>
            <p className="hero-description">
              잘 쓰려고 멈추지 마세요. 오늘 겪은 일을 편하게 남기면,
              스토리로그가 근거와 관점을 정리해 채널별 초안으로 연결합니다.
              게시 전 마지막 결정은 언제나 당신이 합니다.
            </p>
            <div className="hero-actions">
              <a className="primary-button" href="#capture">
                1분 기록 시작하기 <ArrowIcon />
              </a>
              <span className="plain-note">가입 없이 체험 · 원본은 비공개</span>
            </div>
          </div>

          <div className="hero-board" aria-label="기록이 콘텐츠가 되는 과정">
            <div className="board-top">
              <span>TODAY&apos;S STORY PIPELINE</span>
              <strong>3 MIN</strong>
            </div>
            <article className="source-preview">
              <span>01 · PRIVATE SOURCE</span>
              <p>“오늘 회의에서 기능을 늘리기보다<br />한 가지 행동부터 검증하기로 했다.”</p>
              <small>나만 볼 수 있는 원본 기록</small>
            </article>
            <div className="board-connector"><i /><b>실제 표현만 추출</b></div>
            <article className="story-preview">
              <div><span>02 · STORY CARD</span><b>근거 1개</b></div>
              <h2>좋은 시작은 한 가지<br />가설에서 나온다</h2>
              <p>경험 · 관찰 · 배운 점</p>
            </article>
            <div className="draft-preview">
              <span>03 · NEEDS YOUR APPROVAL</span>
              <strong>LinkedIn</strong><strong>X</strong><strong>Instagram</strong>
            </div>
          </div>
        </section>

        <section className="promise-strip" id="workflow" aria-label="서비스 핵심 원칙">
          <div><span>01</span><strong>기록이 먼저</strong><p>빈 프롬프트 대신 오늘을 묻는 질문으로 시작</p></div>
          <div><span>02</span><strong>근거가 보이게</strong><p>AI가 만든 문장과 내 원본을 언제든 비교</p></div>
          <div><span>03</span><strong>승인은 사람이</strong><p>사실·표현·공개 범위를 확인한 뒤에만 게시</p></div>
        </section>

        <section className="capture-section" id="capture" aria-labelledby="capture-title">
          <div className="section-heading">
            <div>
              <p className="section-kicker">TODAY&apos;S CAPTURE</p>
              <h2 id="capture-title">오늘은 어떤 이야기가<br />있었나요?</h2>
            </div>
            <p>완성된 글이 아니어도 괜찮아요.<br />사실과 느낌을 평소 말투로 남겨 주세요.</p>
          </div>

          <div className="capture-modes" aria-label="기록 방식 선택">
            <button type="button" onClick={() => showComingSoon("voice")}>
              <span className="mode-icon"><MicIcon /></span>
              <span><b>말로 남기기</b><small>음성 자동 전사 · 다음 단계</small></span>
              <i>SOON</i>
            </button>
            <button className="available" type="button" onClick={() => setCapabilityNotice("")}>
              <span className="mode-icon"><TextIcon /></span>
              <span><b>글로 남기기</b><small>지금 바로 사용 가능</small></span>
              <i>LIVE</i>
            </button>
            <button type="button" onClick={() => showComingSoon("media")}>
              <span className="mode-icon"><MediaIcon /></span>
              <span><b>사진·영상 추가</b><small>미디어 근거 연결 · 다음 단계</small></span>
              <i>SOON</i>
            </button>
          </div>
          {capabilityNotice && <p className="capability-notice" role="status">{capabilityNotice}</p>}

          <div className="prompt-label">
            <span>무엇을 쓸지 막막하다면, 하나를 골라 보세요.</span>
            <button type="button" onClick={loadExample}>예시 기록 불러오기 ↗</button>
          </div>
          <div className="prompt-grid">
            {prompts.map((prompt, index) => (
              <button
                className={activePrompt === index ? "active" : ""}
                key={prompt.label}
                type="button"
                onClick={() => setActivePrompt(index)}
              >
                <span>0{index + 1}</span>
                <strong>{prompt.label}</strong>
                <small>{prompt.hint}</small>
              </button>
            ))}
          </div>

          <div className="studio-layout">
            <form className="capture-form" onSubmit={handleSubmit}>
              <div className="form-topline">
                <div>
                  <span>PRIVATE SOURCE</span>
                  <h3>{prompts[activePrompt].label}</h3>
                </div>
                <b><i /> 나만 보기</b>
              </div>

              <label>
                <span>무슨 일이 있었나요?</span>
                <textarea
                  value={eventText}
                  onChange={(event) => setEventText(event.target.value)}
                  placeholder={prompts[activePrompt].hint}
                  minLength={10}
                  maxLength={2000}
                  required
                />
                <small>{eventText.length} / 2,000</small>
              </label>

              <label>
                <span>예상과 달랐던 점은 무엇인가요? <i>선택</i></span>
                <textarea
                  className="compact"
                  value={unexpected}
                  onChange={(event) => setUnexpected(event.target.value)}
                  placeholder="뜻밖이었던 반응, 감정, 결과를 적어 주세요."
                  maxLength={1000}
                />
              </label>

              <label>
                <span>그래서 무엇을 배웠나요?</span>
                <textarea
                  className="compact"
                  value={lesson}
                  onChange={(event) => setLesson(event.target.value)}
                  placeholder="다음에는 어떻게 해 보고 싶은지 한 문장으로 남겨 보세요."
                  minLength={3}
                  maxLength={1000}
                  required
                />
              </label>

              <div className="form-options">
                <label>
                  <span>누구에게 들려줄까요?</span>
                  <input value={audience} onChange={(event) => setAudience(event.target.value)} minLength={2} maxLength={100} required />
                </label>
                <fieldset>
                  <legend>초안 채널</legend>
                  <div>
                    {channels.map((channel) => (
                      <button
                        className={selectedChannels.includes(channel) ? "selected" : ""}
                        type="button"
                        key={channel}
                        onClick={() => toggleChannel(channel)}
                      >
                        {selectedChannels.includes(channel) ? "✓ " : "+ "}{channel}
                      </button>
                    ))}
                  </div>
                </fieldset>
              </div>

              <div className="privacy-note">
                <span>🔒</span>
                <p><b>원본은 공개되지 않습니다.</b> 생성된 초안은 사용자가 승인하기 전까지 게시되지 않아요.</p>
              </div>

              <button className="submit-button" type="submit" disabled={status === "loading"}>
                {status === "loading" ? "스토리를 정리하는 중..." : "내 스토리 카드 만들기"}
                {status !== "loading" && <ArrowIcon />}
              </button>
              {status === "error" && <p className="form-error">API에 연결할 수 없습니다. 백엔드 실행 상태를 확인해 주세요.</p>}
            </form>

            <div className={`story-result ${story ? "has-story" : ""}`} aria-live="polite">
              {!story ? (
                <div className="empty-story">
                  <div className="empty-card-mark">✦</div>
                  <span>YOUR STORY CARD</span>
                  <h3>내 기록 속에서<br />이야깃거리를 발견해요.</h3>
                  <p>경험·관찰·배운 점을 분리하고, 모든 초안에 원본 근거를 남깁니다.</p>
                  <div className="empty-state-list">
                    <i>CAPTURED</i><b>→</b><i>STORY_MINED</i><b>→</b><i>NEEDS_REVIEW</i>
                  </div>
                </div>
              ) : (
                <>
                  <div className="story-header">
                    <div><span>{story.status.replace("_", " ")}</span><h3>{story.title}</h3></div>
                    <b>🔒 {story.visibility}</b>
                  </div>

                  <div className="story-facts">
                    <article><span>경험</span><p>{story.event}</p></article>
                    <article><span>관찰</span><p>{story.observation}</p></article>
                    <article><span>배운 점</span><p>{story.lesson}</p></article>
                  </div>

                  <div className="source-box">
                    <span>↳ SOURCE EVIDENCE · {story.source_refs[0].label}</span>
                    <blockquote>“{story.source_refs[0].excerpt}”</blockquote>
                  </div>

                  <div className="angle-picker">
                    <span>이야기 각도</span>
                    <div>
                      {story.angles.map((angle) => (
                        <button
                          className={activeAngle === angle.id ? "selected" : ""}
                          key={angle.id}
                          type="button"
                          onClick={() => setActiveAngle(angle.id)}
                          title={angle.focus}
                        >
                          {angle.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="draft-studio">
                    <div className="draft-tabs">
                      {story.drafts.map((draft) => (
                        <button
                          className={activeDraft?.channel === draft.channel ? "active" : ""}
                          key={draft.channel}
                          type="button"
                          onClick={() => setActiveChannel(draft.channel)}
                        >
                          {draft.channel}
                        </button>
                      ))}
                    </div>
                    <div className="draft-meta"><span>CHANNEL DRAFT</span><b>REVIEW NEEDED</b></div>
                    <textarea aria-label={`${activeDraft?.channel ?? "채널"} 초안`} value={activeDraft?.content ?? ""} readOnly />
                    <div className="draft-source"><span>근거 연결됨</span><b>오늘의 텍스트 기록 1</b></div>
                  </div>

                  <div className="quality-note">
                    <span>✓ 사실 근거</span><span>✓ 원본 표시</span><span>✓ 승인 필수</span>
                    <p>{story.quality_check.note}</p>
                  </div>

                  <div className="feedback-row" aria-label="스토리 카드 피드백">
                    <button className={feedback === "mine" ? "active" : ""} type="button" onClick={() => setFeedback("mine")}>이건 나를 잘 표현해요</button>
                    <button className={feedback === "fact" ? "active warning" : ""} type="button" onClick={() => setFeedback("fact")}>사실과 달라요</button>
                    <button className={feedback === "risk" ? "active warning" : ""} type="button" onClick={() => setFeedback("risk")}>공개가 걱정돼요</button>
                  </div>

                  <div className="approval-row">
                    <button className="copy-button" type="button" onClick={copyDraft}>{copied ? "복사했어요 ✓" : "초안 복사"}</button>
                    <button className="approve-button" type="button" onClick={() => setApproved(true)} disabled={approved}>
                      {approved ? "승인 완료 ✓" : "검토하고 승인하기"}
                    </button>
                  </div>
                  {approved && <p className="approved-message">APPROVED · 게시 가능한 콘텐츠 자산으로 저장할 준비가 되었습니다.</p>}
                </>
              )}
            </div>
          </div>
        </section>

        <section className="metric-section" aria-labelledby="metric-title">
          <div>
            <p className="section-kicker">THE ONE METRIC THAT MATTERS</p>
            <h2 id="metric-title">기록 수보다 중요한 건<br /><em>내가 승인한 콘텐츠 수.</em></h2>
          </div>
          <div className="metric-flow">
            <article><span>01</span><b>기록 완료</b><small>오늘을 남겼는가</small></article>
            <i>→</i>
            <article><span>02</span><b>스토리 채택</b><small>“이건 내 이야기”인가</small></article>
            <i>→</i>
            <article><span>03</span><b>초안 승인</b><small>믿고 공개할 수 있는가</small></article>
            <i>→</i>
            <article><span>04</span><b>게시·복사</b><small>세상에 전달했는가</small></article>
          </div>
        </section>

        <section className="monetize-section" id="monetize" aria-labelledby="monetize-title">
          <div className="monetize-intro">
            <p className="section-kicker">FROM STORY TO OPPORTUNITY</p>
            <h2 id="monetize-title">수익화는 팔로워보다<br />쌓인 이야기에서 시작됩니다.</h2>
            <p>반복해서 승인한 콘텐츠는 나의 관점과 전문성을 보여 주는 자산이 됩니다. 먼저 신뢰를 만들고, 작은 수익 실험으로 연결하세요.</p>
          </div>

          <div className="revenue-grid">
            <article>
              <span className="path-number">01</span><div className="path-icon">✦</div>
              <span className="readiness">CONTENT ASSET</span><h3>나다운 콘텐츠 축적</h3>
              <p>실제 경험과 승인 기록을 쌓아 내가 꾸준히 말할 수 있는 주제를 발견합니다.</p><strong>매주 승인 콘텐츠 수를 핵심 지표로</strong>
            </article>
            <article>
              <span className="path-number">02</span><div className="path-icon">↗</div>
              <span className="readiness">FIRST REVENUE</span><h3>UGC·제휴 실험</h3>
              <p>대표 콘텐츠를 포트폴리오로 묶고, 실제로 사용한 제품과 경험부터 제안합니다.</p><strong>작은 유료 제작·추천 전환부터 검증</strong>
            </article>
            <article>
              <span className="path-number">03</span><div className="path-icon">◎</div>
              <span className="readiness">LATER STAGE</span><h3>브랜드 협업 연결</h3>
              <p>충분한 콘텐츠·성과 데이터가 쌓인 뒤 브랜드와 맞는 크리에이터를 연결합니다.</p><strong>B2B2C 매칭은 신뢰 검증 이후</strong>
            </article>
          </div>
        </section>

        <section className="final-cta">
          <span>YOUR DAY IS ALREADY A STORY.</span>
          <h2>인플루언서가 된 다음 기록하는 게 아니라,<br /><em>기록하며 영향력을 만듭니다.</em></h2>
          <a href="#capture">오늘의 기록 남기기 <ArrowIcon /></a>
        </section>
      </main>

      <footer>
        <a className="brand" href="#top"><span className="brand-mark">S</span><span>STORYLOG</span></a>
        <p>실제 경험이 나다운 영향력이 되도록.</p>
        <span>© 2026 Storylog</span>
      </footer>
    </div>
  );
}
