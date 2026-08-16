# Influence

Next.js 프론트엔드는 로컬에서 실행하고, FastAPI·PostgreSQL·Redis는 Docker Compose로 실행하는 개발 환경입니다.

> 심사용 개발 과정: [Codex Build Log — `gamzerA`](CODEX_BUILD_LOG.md) · [HumanProof 디자인 원문 프롬프트](docs/prompts/humanproof-design-prompt.md)

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
- 인플루언서 DB 조회: http://localhost:8001/api/influencers

백엔드 로그는 `docker compose logs -f backend`로 확인합니다. 종료할 때는 루트에서 `docker compose down`을 실행합니다. DB와 Redis 데이터도 함께 초기화하려면 `docker compose down -v`를 사용합니다.

## 환경변수

루트 `.env`에서 백엔드 포트와 PostgreSQL 계정을 변경할 수 있습니다. 프론트엔드의 API 주소는 `influence-fe/.env.local`의 `NEXT_PUBLIC_API_URL`에서 설정합니다. PostgreSQL과 Redis는 컨테이너 네트워크 안에서만 접근하며, 필요하면 `docker compose exec db psql -U influence influence` 또는 `docker compose exec redis redis-cli`로 접속할 수 있습니다.

## 공개 웹 인플루언서 크롤링

별도의 유료 데이터 API 없이, 각 사이트가 `robots.txt`에서 허용한 공개 프로필
페이지의 JSON-LD·OpenGraph·HTML 메타데이터를 PostgreSQL에 저장합니다. 로그인,
CAPTCHA 우회, 프록시 회전, 비공개 데이터 수집은 하지 않습니다.

관리자 크롤링 API를 보호할 키와 정중한 요청 간격을 `.env`에 설정합니다.

```dotenv
COLLECTOR_ADMIN_KEY=충분히_긴_임의의_관리자_키
CRAWLER_USER_AGENT=InfluenceCrawler/1.0
CRAWLER_REQUEST_DELAY_SECONDS=2.0
CRAWLER_ALLOWED_DOMAINS=
```

백엔드를 재시작한 다음 공개 프로필 URL을 최대 50개까지 전달합니다. 운영에서는
`CRAWLER_USER_AGENT`에 연락 가능한 정책 URL을 포함하고,
`CRAWLER_ALLOWED_DOMAINS`로 허용 도메인을 제한하는 것을 권장합니다.

```bash
curl -X POST http://127.0.0.1:8001/api/admin/influencers/crawl \
  -H 'Content-Type: application/json' \
  -H 'X-Collector-Key: 설정한_관리자_키' \
  -d '{"urls":["https://허용된-사이트.example/creator"]}'
```

프로필 URL의 안정적인 해시를 ID로 사용하므로 같은 URL은 중복 없이 갱신됩니다.
팔로워 수처럼 페이지가 공개하지 않는 필드는 `null`로 보존합니다.

```bash
curl 'http://127.0.0.1:8001/api/influencers?min_followers=10000&verified=true&limit=20'
```

상세한 데이터 범위와 운영 방법은 [공개 웹 크롤링 안내](docs/web-crawling.md)를 참고합니다.

### AI 가상 인플루언서 공개 데이터셋

2026년 공개 순위·분석·연구 자료에서 확인한 Instagram AI/가상 인플루언서
58개를 출처, 관측일, 신뢰도와 함께 적재할 수 있습니다. 연락처와 게시물 원문은
포함하지 않습니다.

```bash
docker compose exec -T backend python3 -m app.seed_ai_virtual_influencers
curl 'http://127.0.0.1:8001/api/influencers?limit=100'
```

최신값과 과거 스냅샷의 구분은
[AI 가상 인플루언서 데이터셋 안내](docs/ai-virtual-influencer-dataset.md)를 참고합니다.

### Bright Data 공급자 사용

Instagram처럼 일반 크롤러를 차단하는 플랫폼은 직접 우회하지 않습니다. 별도의
공급자 계약과 정책 검토를 마친 경우 Bright Data 프로필 API를 선택할 수 있습니다.

Bright Data 계정이 준비되어 있다면 아래 명령이 공식 API 키 설정 페이지를 열고,
숨김 입력으로 받은 키를 무과금 계정 API에서 확인한 뒤 `.env` 저장, 백엔드 재생성,
준비 상태 확인까지 수행합니다. Bright Data 정책상 로그인·이메일/MFA 확인과 키 생성
승인은 계정 소유자가 대시보드에서 완료해야 하며, 생성 API 키는 한 번만 표시됩니다.

```bash
python3 scripts/setup_brightdata.py
```

CI에서는 키가 명령행 인자나 셸 기록에 남지 않도록 secret을 표준 입력으로 전달합니다.

```bash
printf '%s\n' "$BRIGHTDATA_API_TOKEN" | \
  python3 scripts/setup_brightdata.py --token-stdin
```

발급 도구는 [Bright Data 공식 인증 안내](https://docs.brightdata.com/api-reference/authentication)의
최소 권한과 만료일 설정을 따르며 `.env` 권한을 `0600`으로 제한합니다. macOS
Framework Python에 CA 인증서 경로가 없으면 토큰을 명령행에 노출하지 않고 시스템
`curl`의 신뢰 저장소로 인증 검사를 자동 재시도합니다.

```dotenv
INFLUENCER_PROVIDER=brightdata
BRIGHTDATA_API_TOKEN=서버에서만_보관할_API_토큰
BRIGHTDATA_INSTAGRAM_PROFILE_DATASET_ID=gd_l1vikfch901nx3by4
```

설정 후 백엔드를 다시 생성합니다.

```bash
docker compose up -d --force-recreate backend
```

기존 `/api/admin/influencers/crawl` 요청 형식은 그대로 사용합니다. 공급자 응답은
공통 `InfluencerProfile`로 정규화되며, API 토큰이 없으면 외부 호출 전에 HTTP
503으로 중단됩니다. 외부 공급자를 사용해도 플랫폼 약관, 개인정보 처리,
보존기간 및 삭제 요청에 대한 운영 책임은 서비스에 남습니다.

## AWS 배포

운영 환경은 Next.js를 AWS Amplify Hosting, FastAPI를 Amazon ECS Express
Mode와 ECR, PostgreSQL을 private Amazon RDS에 배포합니다. 생성 파일을 위한
private S3도 준비하며 Redis와 Runpod LLM endpoint는 실제 기능과 모델이
확정될 때 추가합니다.

`main` 브랜치의 백엔드·인프라 변경은 GitHub OIDC를 사용해 자동으로
배포합니다. 장기 AWS access key는 사용하지 않습니다. 최초 AWS bootstrap,
GitHub 변수, Amplify 연결 방법은 [AWS 배포 안내](infra/README.md)를
따릅니다.
