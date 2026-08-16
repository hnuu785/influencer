# Influence

Next.js 프론트엔드는 로컬에서 실행하고, FastAPI·PostgreSQL·Redis는 Docker Compose로 실행하는 개발 환경입니다.

## 사전 준비

- Node.js 20.9 이상
- Docker Desktop

## 처음 실행

```bash
cp .env.example .env
cp influence-fe/.env.local.example influence-fe/.env.local

docker compose up --build -d

cd influence-fe
npm install
npm run dev
```

- 프론트엔드: http://localhost:3001
- 백엔드 API: http://localhost:8001
- API 문서: http://localhost:8001/docs
- 전체 연결 상태: http://localhost:8001/health

백엔드 로그는 `docker compose logs -f backend`로 확인합니다. 종료할 때는 루트에서 `docker compose down`을 실행합니다. DB와 Redis 데이터도 함께 초기화하려면 `docker compose down -v`를 사용합니다.

## 환경변수

루트 `.env`에서 백엔드 포트와 PostgreSQL 계정을 변경할 수 있습니다. 프론트엔드의 API 주소는 `influence-fe/.env.local`의 `NEXT_PUBLIC_API_URL`에서 설정합니다. PostgreSQL과 Redis는 컨테이너 네트워크 안에서만 접근하며, 필요하면 `docker compose exec db psql -U influence influence` 또는 `docker compose exec redis redis-cli`로 접속할 수 있습니다.
