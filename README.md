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
- 프로세스 상태: http://localhost:8001/health
- PostgreSQL·Redis 연결 상태: http://localhost:8001/ready
- 인플루언서 DB 조회: http://localhost:8001/api/influencers

백엔드 로그는 `docker compose logs -f backend`로 확인합니다. 종료할 때는 루트에서 `docker compose down`을 실행합니다. DB와 Redis 데이터도 함께 초기화하려면 `docker compose down -v`를 사용합니다.

## 환경변수

루트 `.env`에서 백엔드 포트와 PostgreSQL 계정을 변경할 수 있습니다. 프론트엔드의 API 주소는 `influence-fe/.env.local`의 `NEXT_PUBLIC_API_URL`에서 설정합니다. PostgreSQL과 Redis는 컨테이너 네트워크 안에서만 접근하며, 필요하면 `docker compose exec db psql -U influence influence` 또는 `docker compose exec redis redis-cli`로 접속할 수 있습니다.

## HikerAPI 인플루언서 수집

발급받은 HikerAPI 키와 별도의 관리자 키를 `.env`에 설정합니다. 실제 키는 Git에 커밋하지 않습니다.

```dotenv
HIKERAPI_ACCESS_KEY=발급받은_키
COLLECTOR_ADMIN_KEY=충분히_긴_임의의_관리자_키
```

백엔드를 재시작한 다음, 공개 Instagram 사용자명을 최대 50개까지 전달합니다. 수집 API는 유료 HikerAPI 요청을 발생시키므로 관리자 키가 없으면 비활성화됩니다.

```bash
curl -X POST http://127.0.0.1:8001/api/admin/influencers/collect \
  -H 'Content-Type: application/json' \
  -H 'X-Collector-Key: 설정한_관리자_키' \
  -d '{"usernames":["natgeo","instagram"]}'
```

수집된 계정은 사용자 ID 기준으로 중복 없이 갱신됩니다.

```bash
curl 'http://127.0.0.1:8001/api/influencers?min_followers=10000&verified=true&limit=20'
```

상세한 데이터 범위와 운영 방법은 [HikerAPI 수집 안내](docs/hikerapi-collection.md)를 참고합니다.

## AWS 배포

운영 환경은 Next.js를 AWS Amplify Hosting, FastAPI를 Amazon ECS Express
Mode와 ECR, PostgreSQL을 private Amazon RDS에 배포합니다. 생성 파일을 위한
private S3도 준비하며 Redis와 Runpod LLM endpoint는 실제 기능과 모델이
확정될 때 추가합니다.

`main` 브랜치의 백엔드·인프라 변경은 GitHub OIDC를 사용해 자동으로
배포합니다. 장기 AWS access key는 사용하지 않습니다. 최초 AWS bootstrap,
GitHub 변수, Amplify 연결 방법은 [AWS 배포 안내](infra/README.md)를
따릅니다.
