# Storylog

오늘의 실제 경험을 근거가 보이는 스토리 카드와 채널별 콘텐츠 초안으로 바꾸는 개인 브랜딩 MVP입니다. 사용자가 검토하고 승인하기 전에는 어떤 콘텐츠도 게시되지 않습니다.

상세한 제품 정의, MVP 범위, 지표와 로드맵은 [제품 브리프](./docs/product-brief.md)에서 확인할 수 있습니다.

## 현재 구현

- 빈 프롬프트 대신 네 가지 질문 카드로 기록 시작
- 사건·예상 밖의 점·교훈을 입력하는 가이드형 텍스트 기록
- 원본 근거가 표시되는 구조화된 스토리 카드
- LinkedIn·X·Instagram 채널별 초안
- “나다움”, 사실 오류, 공개 위험 피드백과 사람의 최종 승인
- 승인 콘텐츠를 UGC·제휴·브랜드 협업으로 연결하는 수익화 방향
- 향후 브랜드 매칭을 위한 크리에이터 목록 API

음성 전사, 사진·영상 근거 연결, 로그인·저장, 실제 SNS 게시는 다음 구현 범위이며 화면에 이를 명확히 표시합니다.

## 처음 실행

준비물은 Node.js 20.9 이상과 Docker Desktop입니다.

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
- 스토리 카드 API: `POST http://localhost:8001/api/story-cards`

백엔드 로그는 `docker compose logs -f backend`로 확인합니다. 종료할 때는 루트에서 `docker compose down`을 실행합니다. DB와 Redis 데이터까지 초기화하려면 `docker compose down -v`를 사용합니다.

## Docker 없이 UI·API만 실행

스토리 카드 데모는 데이터베이스 없이도 실행할 수 있습니다.

```bash
cd influence-be
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
```

다른 터미널에서 아래 명령을 실행합니다.

```bash
cd influence-fe
npm install
npm run dev
```

PostgreSQL과 Redis가 없으면 `/ready`는 `degraded`를 반환하지만 `/health`, 스토리 카드 생성과 화면 체험은 정상 동작합니다.

## API 예시

```bash
curl -X POST http://127.0.0.1:8001/api/story-cards \
  -H 'Content-Type: application/json' \
  -d '{
    "event": "오늘 회의에서 큰 기능보다 한 가지 사용자 행동을 먼저 검증하기로 했다.",
    "unexpected": "아이디어가 많을수록 좋을 거라 생각했지만 팀은 작은 실험에 더 빠르게 합의했다.",
    "lesson": "좋은 시작은 한 가지 가설을 끝까지 검증하는 데서 나온다.",
    "audience": "처음 제품을 만드는 사람",
    "channels": ["LinkedIn", "X", "Instagram"]
  }'
```

## 환경변수

루트 `.env`에서 백엔드 포트와 PostgreSQL 계정을 변경할 수 있습니다. 프론트엔드의 API 주소는 `influence-fe/.env.local`의 `NEXT_PUBLIC_API_URL`에서 설정합니다. PostgreSQL과 Redis는 컨테이너 네트워크 안에서만 접근하며, 필요하면 `docker compose exec db psql -U influence influence` 또는 `docker compose exec redis redis-cli`로 접속할 수 있습니다.

## AWS 배포

운영 환경은 Next.js를 AWS Amplify Hosting, FastAPI를 Amazon ECS Express Mode와 ECR, PostgreSQL을 private Amazon RDS에 배포합니다. 생성 파일을 위한 private S3도 준비하며 Redis와 Runpod LLM endpoint는 실제 기능과 모델이 확정될 때 추가합니다.

`main` 브랜치의 백엔드·인프라 변경은 GitHub OIDC를 사용해 자동으로 배포합니다. 장기 AWS access key는 사용하지 않습니다. 최초 AWS bootstrap, GitHub 변수, Amplify 연결 방법은 [AWS 배포 안내](infra/README.md)를 따릅니다.
