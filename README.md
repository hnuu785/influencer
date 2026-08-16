# Influence

스토리로그 MVP입니다. Next.js 화면은 로컬에서 실행하고, FastAPI·PostgreSQL/pgvector·Redis는 Docker Compose로 실행합니다.

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
- 프로세스 상태: http://localhost:8001/health
- PostgreSQL·Redis 연결 상태: http://localhost:8001/ready

기본 초대 코드는 `STORYLOG-BETA`입니다. 별도 키 없이도 전체 사용자 흐름을 확인할 수 있도록 결정론적 체험 AI가 동작합니다.

백엔드 로그는 `docker compose logs -f backend`로 확인합니다. 종료할 때는 루트에서 `docker compose down`을 실행합니다. DB와 Redis 데이터도 함께 초기화하려면 `docker compose down -v`를 사용합니다.

## 환경변수

루트 `.env`에서 백엔드 포트, 초대 코드, PostgreSQL 계정을 변경할 수 있습니다. 프론트엔드의 API 주소는 `influence-fe/.env.local`의 `NEXT_PUBLIC_API_URL`에서 설정합니다. PostgreSQL과 Redis는 컨테이너 네트워크 안에서만 접근합니다.

실제 연동을 시험하려면 `.env`에 다음 값을 설정하고 백엔드를 다시 빌드합니다.

- `OPENAI_API_KEY`: GPT Transcribe, 임베딩, StoryCard·제작안·검수를 실제 OpenAI API로 처리
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`: Google 로그인과 선택적 Calendar 읽기 연결
- Google OAuth 리디렉션 URI: `http://localhost:8001/api/auth/google/callback`, `http://localhost:8001/api/calendar/callback`

OpenAI 키가 있으면 PostgreSQL/pgvector에서 개인 승인 이력과 권리 확인 시드 패턴을 검색한 뒤 필요한 문맥만 Responses API에 전달합니다. 키가 없으면 같은 API 계약을 유지하는 체험 모드로 동작합니다.

## AWS 배포

운영 환경은 Next.js를 AWS Amplify Hosting, FastAPI를 Amazon ECS Express
Mode와 ECR, PostgreSQL을 private Amazon RDS에 배포합니다. 생성 파일을 위한
private S3도 준비합니다. MVP의 AI 경로는 AWS RDS PostgreSQL/pgvector와
OpenAI API이며 vLLM·Runpod은 필수 의존성이 아닙니다.

`main` 브랜치의 백엔드·인프라 변경은 GitHub OIDC를 사용해 자동으로
배포합니다. 장기 AWS access key는 사용하지 않습니다. 최초 AWS bootstrap,
GitHub 변수, Amplify 연결 방법은 [AWS 배포 안내](infra/README.md)를
따릅니다.
