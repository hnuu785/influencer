const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

export default function Home() {
  return (
    <main>
      <section>
        <p className="eyebrow">INFLUENCE</p>
        <h1>개발 환경이 준비되었습니다.</h1>
        <p>
          Next.js는 로컬에서 실행 중이며, FastAPI·PostgreSQL·Redis는 Docker로
          구성됩니다.
        </p>
        <div className="links">
          <a href={`${apiUrl}/docs`}>API 문서</a>
          <a href={`${apiUrl}/health`}>연결 상태</a>
        </div>
      </section>
    </main>
  );
}
