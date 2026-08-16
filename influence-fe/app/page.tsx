"use client";

import { FormEvent, ReactNode, useMemo, useState } from "react";

type IconName =
  | "home" | "archive" | "pen" | "send" | "chart" | "settings"
  | "mic" | "text" | "image" | "sparkles" | "arrow" | "more"
  | "check" | "link" | "quote" | "close" | "chevron";

function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    home: <><path d="m3 10 9-7 9 7"/><path d="M5 9v11h14V9"/><path d="M9 20v-6h6v6"/></>,
    archive: <><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 4V2m8 2V2M4 9h16M8 13h3m-3 4h7"/></>,
    pen: <><path d="m4 20 4.2-1 10.6-10.6a2.4 2.4 0 0 0-3.4-3.4L4.8 15.6 4 20Z"/><path d="m14 6 4 4"/></>,
    send: <><path d="m3 3 18 9-18 9 3.5-9L3 3Z"/><path d="M6.5 12H21"/></>,
    chart: <><path d="M4 20V10m6 10V4m6 16v-7m5 7H2"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
    mic: <><rect x="8" y="3" width="8" height="12" rx="4"/><path d="M5 11a7 7 0 0 0 14 0m-7 7v3m-4 0h8"/></>,
    text: <><path d="M5 6V4h14v2M12 4v16m-4 0h8"/></>,
    image: <><rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="10" r="2"/><path d="m4 17 5-4 3 3 3-2 5 4"/></>,
    sparkles: <><path d="m12 3 1.2 3.8L17 8l-3.8 1.2L12 13l-1.2-3.8L7 8l3.8-1.2L12 3Z"/><path d="m19 14 .7 2.3L22 17l-2.3.7L19 20l-.7-2.3L16 17l2.3-.7L19 14ZM5 14l.7 2.3L8 17l-2.3.7L5 20l-.7-2.3L2 17l2.3-.7L5 14Z"/></>,
    arrow: <><path d="M5 12h14m-5-5 5 5-5 5"/></>,
    more: <><circle cx="5" cy="12" r="1" fill="currentColor"/><circle cx="12" cy="12" r="1" fill="currentColor"/><circle cx="19" cy="12" r="1" fill="currentColor"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    link: <><path d="m10 13 4-4"/><path d="M7.5 15.5 5 18a3.5 3.5 0 0 1-5-5l3-3a3.5 3.5 0 0 1 5 0"/><path d="m14.5 8.5 2.5-2.5a3.5 3.5 0 0 1 5 5l-3 3a3.5 3.5 0 0 1-5 0"/></>,
    quote: <><path d="M7 9H4v4h4V9c0-3-1-4-3-5m12 5h-3v4h4V9c0-3-1-4-3-5"/></>,
    close: <path d="m6 6 12 12M18 6 6 18"/>,
    chevron: <path d="m9 18 6-6-6-6"/>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

const channels = {
  linkedin: { label: "LinkedIn", mark: "in", color: "blue" },
  x: { label: "X", mark: "X", color: "black" },
  instagram: { label: "Instagram", mark: "◎", color: "pink" },
} as const;
type ChannelKey = keyof typeof channels;

const sampleDrafts: Record<ChannelKey, string> = {
  linkedin: `AI 음성 에이전트를 테스트하며 뜻밖의 사실을 발견했습니다.\n\n결과를 가른 건 모델의 성능보다 ‘어떤 질문을 던지느냐’였습니다. 같은 모델도 질문의 순서와 맥락을 조금 바꾸자 전혀 다른 답을 내놓았습니다.\n\n새로운 도구를 고르는 일보다, 좋은 질문을 설계하고 빠르게 실험하는 일이 먼저일지 모릅니다. 오늘의 작은 테스트가 제 일하는 방식을 다시 보게 했습니다.`,
  x: `AI 음성 에이전트를 테스트하며 느낀 것.\n\n모델 선택보다 질문 설계가 결과를 더 크게 바꿨다. 좋은 도구를 찾는 데 시간을 쓰기 전에, 좋은 질문을 만들고 빠르게 실험해 보는 것이 먼저다.`,
  instagram: `좋은 AI를 찾는 것보다 좋은 질문을 만드는 일이 먼저였다. 🎙️\n\n오늘 음성 에이전트를 테스트하며 얻은 의외의 배움. 같은 모델도 질문의 순서와 맥락에 따라 결과가 완전히 달라졌다.\n\n#AI에이전트 #프로덕트빌딩 #오늘의배움`,
};

function Sidebar({ active, onNavigate }: { active: string; onNavigate: (item: string) => void }) {
  const nav = [["홈", "home"], ["기록", "archive"], ["콘텐츠 스튜디오", "pen"], ["게시", "send"], ["인사이트", "chart"]] as const;
  return <aside className="sidebar">
    <button className="brand" onClick={() => onNavigate("홈")} aria-label="스토리로그 홈"><span className="brand-mark"><Icon name="sparkles" size={19}/></span><span>스토리로그</span></button>
    <nav>{nav.map(([label, icon]) => <button key={label} className={active === label ? "active" : ""} onClick={() => onNavigate(label)}><Icon name={icon} size={19}/><span>{label}</span>{label === "콘텐츠 스튜디오" && <span className="nav-badge">2</span>}</button>)}</nav>
    <div className="sidebar-bottom">
      <div className="plan-card"><span className="plan-icon"><Icon name="sparkles" size={17}/></span><strong>이번 주 3개의 이야기</strong><p>조금씩 쌓이고 있어요</p><div className="progress"><span/></div><small>3 / 5 기록</small></div>
      <button className="settings-button"><Icon name="settings" size={19}/> 설정</button>
      <div className="profile"><div className="avatar">민</div><div><strong>김민준</strong><span>AI Product Builder</span></div><Icon name="more" size={19}/></div>
    </div>
  </aside>;
}

function CaptureCard({ onCreated }: { onCreated: (text: string) => void }) {
  const [mode, setMode] = useState<"text" | "voice" | "media">("text");
  const [text, setText] = useState("");
  function submit(event: FormEvent) { event.preventDefault(); if (!text.trim()) return; onCreated(text.trim()); setText(""); }
  return <section className="capture-card">
    <div className="capture-heading"><span className="capture-spark"><Icon name="sparkles" size={20}/></span><div><strong>오늘, 어떤 순간이 마음에 남았나요?</strong><p>완성된 글이 아니어도 괜찮아요. 편하게 남겨보세요.</p></div></div>
    <form onSubmit={submit}>
      {mode === "text" ? <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="오늘 새로 알게 된 것, 예상과 달랐던 일, 누군가에게 말해주고 싶은 것을 적어보세요." aria-label="오늘의 기록"/> : <div className="capture-placeholder"><span className={mode === "voice" ? "record-orb" : "upload-orb"}><Icon name={mode === "voice" ? "mic" : "image"} size={25}/></span><div><strong>{mode === "voice" ? "눌러서 음성 기록 시작" : "사진이나 영상을 이곳에 추가"}</strong><p>{mode === "voice" ? "최대 3분, 떠오르는 대로 이야기해 보세요" : "JPG, PNG, MP4 · 최대 200MB"}</p></div></div>}
      <div className="capture-actions"><div className="mode-buttons"><button type="button" className={mode === "voice" ? "selected" : ""} onClick={() => setMode("voice")}><Icon name="mic" size={18}/> 말로 남기기</button><button type="button" className={mode === "text" ? "selected" : ""} onClick={() => setMode("text")}><Icon name="text" size={18}/> 글로 남기기</button><button type="button" className={mode === "media" ? "selected" : ""} onClick={() => setMode("media")}><Icon name="image" size={18}/> 사진·영상</button></div>{mode === "text" && <button className="submit-note" disabled={!text.trim()}>기록하기 <Icon name="arrow" size={17}/></button>}</div>
    </form>
  </section>;
}

type Story = { id: number; tag: string; time: string; title: string; description: string; quote: string; topics: string[]; source: "voice" | "text" };

function draftsFor(story: Story): Record<ChannelKey, string> {
  if (story.id === 1) return sampleDrafts;
  return {
    linkedin: `${story.quote}\n\n이 경험에서 제가 발견한 건 ‘${story.title}’라는 관점이었습니다. 익숙하게 지나칠 수 있는 순간도 기록하고 다시 바라보면, 다음 선택을 바꾸는 배움이 됩니다.`,
    x: `${story.quote}\n\n오늘의 한 줄: ${story.title}`,
    instagram: `${story.quote}\n\n오늘의 작은 순간에서 발견한 생각.\n\n#오늘의기록 #나만의관점`,
  };
}

function StoryCard({ story, onOpen }: { story: Story; onOpen: () => void }) {
  return <article className="story-card">
    <div className="story-meta"><span>{story.tag}</span><time>{story.time}</time><button aria-label="더 보기"><Icon name="more" size={20}/></button></div>
    <button className="story-content" onClick={onOpen}><h3>{story.title}</h3><p>{story.description}</p><blockquote><Icon name="quote" size={17}/><span>{story.quote}</span></blockquote></button>
    <div className="story-footer"><div>{story.topics.map((topic) => <span key={topic}>#{topic}</span>)}</div><button onClick={onOpen}>콘텐츠로 만들기 <Icon name="arrow" size={16}/></button></div>
  </article>;
}

function Studio({ story, onClose }: { story: Story; onClose: () => void }) {
  const [activeChannel, setActiveChannel] = useState<ChannelKey>("linkedin");
  const [drafts, setDrafts] = useState(() => draftsFor(story));
  const [approved, setApproved] = useState(false);
  const config = channels[activeChannel];
  const draft = drafts[activeChannel];
  return <div className="studio-overlay" role="dialog" aria-modal="true" aria-label="콘텐츠 스튜디오"><div className="studio-shell">
    <header className="studio-header"><div><span className="brand-mark small"><Icon name="sparkles" size={16}/></span><strong>콘텐츠 스튜디오</strong><span className="autosave"><i/> 저장됨</span></div><button onClick={onClose} aria-label="스튜디오 닫기"><Icon name="close" size={22}/></button></header>
    <div className="studio-grid">
      <aside className="source-panel"><span className="panel-label">원문과 근거</span><h2>{story.title}</h2><div className="source-type"><Icon name={story.source === "voice" ? "mic" : "text"} size={16}/> {story.source === "voice" ? "음성 기록 · 1분 12초" : "텍스트 기록"}</div><div className="transcript"><span>{story.source === "voice" ? "00:12" : "원문"}</span><p>“{story.quote}”</p></div>{story.source === "voice" && <div className="transcript"><span>00:31</span><p>“같은 모델이어도 질문을 어떻게 이어가느냐에 따라 답의 깊이가 정말 달랐어요.”</p></div>}<button className="source-link"><Icon name="link" size={16}/> 원문 전체 보기</button><div className="facts-card"><strong><Icon name="check" size={16}/> AI가 찾은 핵심</strong><dl><div><dt>관찰</dt><dd>{story.title}</dd></div><div><dt>배운 점</dt><dd>{story.description}</dd></div><div><dt>근거 수준</dt><dd>개인 경험</dd></div></dl></div></aside>
      <main className="editor-panel"><div className="editor-top"><div><span className="panel-label">선택한 콘텐츠 각도</span><h1>{story.title}</h1></div><button className="angle-button">각도 바꾸기 <Icon name="chevron" size={15}/></button></div>
        <div className="channel-tabs">{(Object.keys(channels) as ChannelKey[]).map((key) => <button key={key} className={activeChannel === key ? "active" : ""} onClick={() => { setActiveChannel(key); setApproved(false); }}><span className={`channel-mark ${channels[key].color}`}>{channels[key].mark}</span>{channels[key].label}{activeChannel === key && <i/>}</button>)}</div>
        <div className="draft-card"><div className="draft-profile"><div className="avatar">민</div><div><strong>김민준</strong><span>AI Product Builder · 지금</span></div><span className="ai-edited"><Icon name="sparkles" size={13}/> AI 초안</span></div><textarea value={draft} onChange={(e) => setDrafts({ ...drafts, [activeChannel]: e.target.value })} aria-label={`${config.label} 초안`}/><div className="draft-count">{draft.length}자 · 직접 수정할 수 있어요</div></div>
        <div className="quality-row"><div className="quality-score"><span>4.7</span><div><strong>품질 검사 통과</strong><p>개인성 · 사실성 · 말투가 좋아요</p></div></div><div className="quality-checks"><span><Icon name="check" size={14}/> 원문 근거 확인</span><span><Icon name="check" size={14}/> 민감 정보 없음</span><span><Icon name="check" size={14}/> 말투 적합</span></div></div>
        <div className="studio-actions"><button className="secondary-action">초안 저장</button><button className={approved ? "approve-button approved" : "approve-button"} onClick={() => setApproved(true)}><Icon name="check" size={18}/>{approved ? "승인 완료 · 게시 대기" : `${config.label} 초안 승인`}</button></div>
      </main>
    </div>
  </div></div>;
}

export default function Home() {
  const [active, setActive] = useState("홈");
  const [studioStory, setStudioStory] = useState<Story | null>(null);
  const [notice, setNotice] = useState("");
  const [stories, setStories] = useState<Story[]>([
    { id: 1, tag: "AI가 발견한 이야기", time: "오늘 · 10:42", title: "좋은 AI보다 좋은 질문이 먼저였다", description: "음성 에이전트 실험에서 모델의 성능보다 질문을 설계하는 방식이 결과를 더 크게 바꾼다는 것을 발견했어요.", quote: "기술보다 질문 설계가 더 중요하다는 게 의외였어요.", topics: ["AI에이전트", "질문설계"], source: "voice" },
    { id: 2, tag: "어제의 기록", time: "어제 · 21:18", title: "사용자는 기능이 아니라 안심을 선택한다", description: "새 기능을 설명할 때 성능보다 사용자가 통제권을 갖고 있다는 점에 더 크게 반응했던 인터뷰를 정리했어요.", quote: "자동화보다 중요한 건 언제든 멈출 수 있다는 믿음이었다.", topics: ["제품기획", "사용자인터뷰"], source: "text" },
  ]);
  const today = useMemo(() => new Intl.DateTimeFormat("ko-KR", { month: "long", day: "numeric", weekday: "long" }).format(new Date()), []);
  function createStory(text: string) { const compact = text.replace(/\s+/g, " "); const title = compact.length > 32 ? `${compact.slice(0, 31)}…` : compact; const story: Story = { id: Date.now(), tag: "방금 남긴 기록", time: "지금", title, description: "방금 남긴 기록에서 나만의 관점과 콘텐츠가 될 만한 문장을 찾고 있어요.", quote: compact, topics: ["오늘의기록", "새로운관점"], source: "text" }; setStories([story, ...stories]); setNotice("기록을 저장하고 스토리 카드를 만들었어요."); window.setTimeout(() => setNotice(""), 2800); }
  return <div className="app-shell">
    <Sidebar active={active} onNavigate={(item) => { setActive(item); if (item === "콘텐츠 스튜디오") setStudioStory(stories[0]); }}/>
    <main className="dashboard"><header className="topbar"><div className="mobile-brand"><span className="brand-mark"><Icon name="sparkles" size={18}/></span><strong>스토리로그</strong></div><div className="date-pill">{today}</div><div className="top-actions"><button className="streak">🔥 <strong>4일째 기록 중</strong></button><button className="notification" aria-label="알림">●</button></div></header>
      <div className="content-wrap"><section className="welcome"><p>안녕하세요, 민준님</p><h1>오늘의 이야기를 들려주세요.</h1><span>작은 순간도 쌓이면 나만의 콘텐츠가 됩니다.</span></section><CaptureCard onCreated={createStory}/>
        <section className="story-section"><div className="section-heading"><div><h2>콘텐츠가 될 이야기</h2><p>기록 속에서 발견한 민준님만의 관점이에요.</p></div><button>모두 보기 <Icon name="arrow" size={16}/></button></div><div className="story-grid">{stories.slice(0, 2).map((story) => <StoryCard key={story.id} story={story} onOpen={() => setStudioStory(story)}/>)}</div></section>
        <section className="week-section"><div><span className="week-icon"><Icon name="chart" size={21}/></span><div><strong>이번 주, 이야기가 이렇게 자랐어요</strong><p>기록 3개에서 콘텐츠 초안 7개를 만들고 2개를 승인했어요.</p></div></div><div className="week-stats"><span><strong>3</strong>기록</span><i/><span><strong>7</strong>초안</span><i/><span className="accent"><strong>2</strong>승인</span></div></section>
      </div>
    </main>
    {studioStory && <Studio story={studioStory} onClose={() => { setStudioStory(null); setActive("홈"); }}/>} {notice && <div className="toast"><Icon name="check" size={18}/>{notice}</div>}
  </div>;
}
