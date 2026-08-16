const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

export default function Home() {
  return (
    <main>
      <section>
        <p className="eyebrow">INFLUENCE</p>
        <h1>서비스 환경이 준비되었습니다.</h1>
        <p>
          Next.js 프론트엔드와 FastAPI API의 연결 상태를 확인할 수 있습니다.
        </p>
        <div className="links">
          <a href={`${apiUrl}/docs`}>API 문서</a>
          <a href={`${apiUrl}/ready`}>연결 상태</a>
        </div>
      </section>
    </main>
  );
}
