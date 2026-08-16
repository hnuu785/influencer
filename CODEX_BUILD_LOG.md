# Codex Build Log — `gamzerA`

> HikerAPI 실험에서 시작해 정책을 지키는 공개 웹 수집기, Bright Data 공급자 어댑터, 58개 AI Instagram 인플루언서 데이터셋, 공유 패키지, Storylog 프론트 동기화와 HumanProof 디자인 테마까지 발전시킨 과정을 기록한다.

- 작업일: 2026-08-16
- 저장소: [`hnuu785/influencer`](https://github.com/hnuu785/influencer)
- 대상 브랜치: [`gamzerA`](https://github.com/hnuu785/influencer/tree/gamzerA)
- 이 작업 전 공개 기준 커밋: `932f0cf`
- 전체 대화 원문: [Storylog MVP 및 `gamzerA` 작업 로그](chat-log/2026-08-16-1305-storylog-mvp.md)
- 디자인 원문 프롬프트: [HumanProof 디자인 프롬프트](docs/prompts/humanproof-design-prompt.md)

이 문서는 성공 결과만 나열하지 않는다. 실제로 어떤 문제를 발견했고, 무엇을 계획해 Codex와 하위 에이전트에 위임했으며, 실패를 어떻게 분리 진단하고 복구했는지까지 남긴다. 비밀키·토큰·개인정보·숨은 추론은 기록하지 않았다.

## 1. 한눈에 보는 결과

`gamzerA`에서 완료한 핵심 결과는 다음과 같다.

1. 명시적인 공개 프로필만 받는 관리자 수집 API와 PostgreSQL 저장소를 만들었다.
2. HikerAPI 인증 실패 뒤 무한 재시도하지 않고 원인을 확인한 후 해당 기능을 제거했다.
3. `robots.txt`, 사설망 차단, 응답 크기 제한, 연락처 마스킹을 적용한 공개 웹 크롤러로 전환했다.
4. Instagram은 일반 크롤러로 우회하지 않고 `robots_denied`로 종료했다.
5. Bright Data를 교체 가능한 공급자 어댑터로 연결하고, API 키 설정·검증·백엔드 재기동을 자동화했다.
6. macOS Python 인증서 오류와 Docker 재기동 직후 연결 재설정 오류를 각각 재현하고 복구했다.
7. 공개 출처와 관측일을 가진 AI/가상 Instagram 인플루언서 데이터를 24개에서 58개로 확장했다.
8. 58개 레코드를 PostgreSQL에 멱등 적재하고 JSON·README·SHA-256 매니페스트·ZIP으로 내보냈다.
9. `main`의 Storylog 프론트를 `gamzerA`에 동기화하고 lint·production build를 통과시켰다.
10. 기능 코드는 유지한 채 HumanProof 팔레트와 반응형 테마를 CSS 한 파일에 적용하고 로컬에서 실행했다.

현재 상태를 과장하지 않는다. `gamzerA`의 공개 커밋 `932f0cf`에 복사된 Storylog 프론트와 인플루언서 전용 백엔드 사이에는 API 계약 차이가 있다. `/api/me`를 비롯한 Storylog API는 현재 `gamzerA` 백엔드에 없으므로 로그인 이후 흐름은 404가 발생한다. 병합 충돌은 분석·해결안을 만들었지만, 사용자가 “나머지는 그대로 두고 디자인 테마만 변경”으로 범위를 좁혀 병합 결과는 커밋하지 않았다.

## 2. 문제 정의

초기 목표는 “인플루언서 데이터를 최대한 수집해 DB를 만든다”였지만, 구현 과정에서 네 가지 문제가 드러났다.

### 2.1 수집 가능성과 수집 허용 범위는 다르다

Instagram HTML을 기술적으로 요청할 수 있어도 일반 크롤러의 접근이 허용된다는 뜻은 아니다. 로그인 우회, robots 우회, 비공개 데이터 수집은 제품 리스크가 된다.

### 2.2 API 키가 있다고 실제 호출이 가능한 것은 아니다

HikerAPI 키는 두 번 교체해도 HTTP 401을 반환했다. Bright Data는 키가 승인됐지만 역할에 따라 잔액 API가 제한됐고, 프로필 데이터셋 요청은 별도 권한 문제로 실패할 수 있었다.

### 2.3 데이터 개수보다 출처·시점·신뢰도가 중요하다

팔로워 수는 실시간 값이 아니라 공개 출처의 스냅샷이다. 따라서 레코드마다 출처, 관측일, 신뢰도, 비활성 상태를 함께 저장해야 했다.

### 2.4 프론트 빌드 성공과 런타임 호환성은 다르다

`main` 프론트는 컴파일되지만 Storylog 인증·기록·콘텐츠 API를 호출한다. `gamzerA` 백엔드는 인플루언서 수집·조회 API만 제공하므로 빌드 성공만으로 통합 완료라고 할 수 없다.

## 3. Codex 계획과 업무 위임

작업을 다음과 같이 검증 가능한 단위로 나눴다.

```text
수집 경계 정의
→ 최소 관리자 API 구현
→ 외부 인증을 1건으로 검증
→ 실패 원인 분리
→ 정책 준수 수집기로 전환
→ 공급자 어댑터와 설정 자동화
→ 출처 기반 시드 확장
→ DB 적재·공유 패키지
→ 프론트 동기화·호환성 감사
→ 디자인만 수술적으로 변경
→ lint/build/로컬 실행
```

### 위임 단위

| 위임 대상 | 맡긴 일 | 산출물 또는 판단 |
|---|---|---|
| Codex 주 작업자 | 수집기·어댑터·설정 자동화·데이터 적재·Git 게시 | 실제 코드, 테스트, 문서, 커밋 |
| `merge_audit` | `origin/main`과 `gamzerA`의 충돌 및 런타임 위험 감사 | 충돌 5개, 병합 기준, pgvector/의존성/운영 설정 위험 확인 |
| `ui_audit` | 동기화된 Storylog 프론트와 HumanProof 요구사항 차이 분석 | 누락 화면, API 의존성, fixture 경계, 컴포넌트 분리안 |
| `responsive_audit` | 360·390·430·768·1024·1440px 반응형·접근성 감사 | 모바일 여백, 레일 폭, 글자 크기, focus/touch target 개선안 |
| `develop_theme` | 기능을 건드리지 않는 테마 전용 CSS 구현 | `globals.css` 한 파일, lint/build 통과 |
| 배포 감사 | 현재 Next.js/ECS 조합의 배포 가능성 확인 | SameSite/CORS/운영 비밀값 문제로 공개 배포 완료 판정 보류 |

하위 에이전트의 결과는 그대로 채택하지 않고 실제 작업 트리, 테스트, 컨테이너 상태와 대조했다. 범위가 바뀌었을 때는 진행 중이던 백엔드 병합·재빌드를 중단하고, 공개 `gamzerA` 기준의 별도 작업공간으로 옮겨 기존 기록을 보존했다.

## 4. 단계별 구현·반복 기록

### 4.1 1단계 — HikerAPI 관리자 수집 경로

대표 프롬프트:

> “hiker api 로 인플루언서 db 수집”

#### 계획

- 임의 대량 수집이 아니라 명시된 공개 사용자명만 입력받는다.
- 관리자 비밀키가 없으면 외부 호출 전에 실패한다.
- 원본 공급자 응답, 이메일, 전화번호는 저장하지 않는다.
- 안정적인 Instagram 사용자 ID로 PostgreSQL upsert한다.
- 한 프로필 실패가 전체 요청을 무너뜨리지 않도록 부분 실패를 반환한다.

#### 구현

- HikerAPI `/v2/user/by/username` 연동
- `POST /api/admin/influencers/collect`
- `GET /api/influencers`
- 요청 정규화·중복 제거·프로필 검증·필터 조회
- 관리자 비밀키와 API 키를 서버 환경변수로만 관리

#### 검증

- 백엔드 테스트 `14 passed`
- Python compile 통과
- `git diff --check` 통과
- 관리자 키가 없을 때 외부 호출 전 HTTP 503 확인

관련 커밋: `0a69756`, `75b0a07`

### 4.2 2단계 — HikerAPI 키 오류를 추측이 아닌 증거로 분리

대표 프롬프트:

> “api key 발급 완료”
>
> “설정 완료”
>
> “키 교체 완료”

#### 첫 실패

Docker Compose의 PostgreSQL·Redis·FastAPI가 healthy이고 `/ready`도 200이었지만, 단일 `natgeo` 요청은 HikerAPI HTTP 401로 거절됐다. DB 행 수는 0이었다.

#### 반복 진단

1. 비밀값은 출력하지 않고 존재 여부와 길이만 확인했다.
2. 백엔드 컨테이너만 재생성해 변경된 환경변수를 주입했다.
3. 프로필 API와 무관한 `/sys/balance`도 401인지 확인했다.
4. 같은 거절이 확인되자 애플리케이션 헤더·DB·Docker 문제가 아니라 계정/토큰 인증 문제로 좁혔다.
5. 유료 프로필 요청을 더 반복하지 않았다.

#### 결과

키를 계속 추측하는 대신 HikerAPI 기능을 제품 핵심에서 제거하고, 허용된 공개 페이지와 공급자 어댑터로 방향을 전환했다.

관련 커밋: `695c0c7`, `412433a`, `a707647`

### 4.3 3단계 — HikerAPI 제거와 정책 준수 공개 웹 크롤러

대표 프롬프트:

> “hiker api로 수집하는 기능은 삭제하고 크롤링으로 가져올 수 있는 최대한으로 인플루언서 데이터 크롤링하여 db 구축해주세요.”

#### 계획

- HikerAPI 코드·키·문서·테스트를 제거한다.
- 명시된 HTTPS URL만 받는다.
- robots 규칙과 crawl delay를 준수한다.
- 사설망·자격증명 URL·안전하지 않은 redirect를 차단한다.
- 응답 크기와 redirect 횟수를 제한한다.
- JSON-LD, OpenGraph, 표준 meta만 구조화한다.
- 이메일·전화번호를 마스킹한다.

#### 구현 결과

- `influencer_profiles` PostgreSQL 스키마
- `POST /api/admin/influencers/crawl`
- `GET /api/influencers`
- 프로필 URL hash 기반 멱등 upsert
- URL별 성공·실패 코드
- 운영 가이드 [공개 웹 크롤링](docs/web-crawling.md)

#### 실제 프로필 데모

사용자가 제공한 `ye_ong_leee` Instagram URL은 추적 query를 제거한 뒤 검사했다. Instagram의 robots 규칙이 일반 크롤러를 허용하지 않아 결과를 `robots_denied`로 반환했고, 페이지를 우회하거나 DB에 저장하지 않았다.

#### 검증

- 백엔드 테스트 `21 passed`
- Python compile, Compose config, `git diff --check` 통과
- `/collect` 제거 및 `/crawl` OpenAPI 노출 확인
- DB `influencer_profiles` 0행 유지 확인

### 4.4 4단계 — Bright Data 공급자 어댑터와 토큰 설정 자동화

대표 프롬프트:

> “인플루언서 데이터 크롤링 수집 가능한 api 연동 방법”
>
> “그대로 실행해주세요.”
>
> “토큰 발행까지 자동화하세요”

#### 설계 판단

- 직접 웹 크롤러는 robots 허용 페이지에만 사용한다.
- Instagram URL은 계약·정책 검토를 마친 공급자 모드로 분리한다.
- 기존 관리자 API 요청 형식은 유지하고 내부 공급자만 교체한다.
- 로그인, 이메일/MFA, 키 생성 승인은 계정 소유자가 완료한다.
- 생성된 키는 숨김 입력으로 받아 `.env`에 mode `0600`으로 저장한다.

#### 구현

- `public_web | brightdata` 공급자 선택
- 서버 전용 Bearer 인증
- 추적 query 제거 및 공통 `InfluencerProfile` 정규화
- raw upstream payload 미저장
- 인증·크레딧·rate limit·timeout·oversize·invalid 응답 매핑
- `scripts/setup_brightdata.py` 한 번 실행으로 키 검증, 원자적 `.env` 갱신, backend 재생성, `/ready` 대기

#### 검증

- 어댑터 추가 시 `29 passed`
- 설정 도구 추가 시 `34 passed`
- 키가 없으면 외부 호출 전 503으로 fail closed
- Docker Compose와 Python compile 통과

관련 커밋: `590add8`

### 4.5 5단계 — 인증서와 연결 재설정 오류 복구

#### 오류 A: macOS Python TLS 인증서 실패

실제 오류:

```text
[SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate
```

확인 결과 macOS Framework Python의 기본 CA file/path가 비어 있었고, system `curl`은 같은 Bright Data TLS 인증서를 정상 검증했다.

수정:

- 인증서 오류일 때만 system trust를 사용하는 `curl` fallback 적용
- API 키를 프로세스 인자에 넣지 않고 표준 입력의 header-file 형식으로 전달
- HTTP 401/403 등 공급자 응답은 그대로 fail closed

검증:

- `36 passed`
- synthetic invalid token으로 Python CA 실패 → system trust fallback → controlled 401 흐름 확인
- 키가 출력·로그·Git에 남지 않음 확인

#### 오류 B: Docker backend 재생성 직후 `Connection reset by peer`

키는 이미 승인·저장됐고 컨테이너도 시작됐지만 `/ready` 확인 순간 연결이 재설정됐다. 토큰이나 DB 문제가 아니라 readiness race로 진단했다.

수정:

- reset, refused, remote disconnect, timeout, 일시적 URL 오류만 재시도
- 저장된 토큰을 노출하지 않고 설정 도구 전체를 다시 실행
- 준비 완료 후 승인된 사용자 프로필 요청은 정확히 한 번만 실행

결과:

- backend ready 완료
- 테스트 `39 passed`
- PostgreSQL·Redis `ok`
- Bright Data 프로필 요청은 별도 `upstream_error`로 종료
- 비용이 발생할 수 있는 자동 재시도는 하지 않음

### 4.6 6단계 — AI Instagram 인플루언서 24개에서 58개로 확장

대표 프롬프트:

> “나는 ai 인스타그래머에 대한 정보를 크롤링 해오려고해. 현재 인스타그램에서 유명한 ai 인플루언서 정보를 최대한 끍어와줘.”

#### 범위

- 생성형 AI 인물
- CGI 가상 인간
- 애니메이션 합성 캐릭터
- 브랜드 소유 가상 마스코트

실제 인간 AI 교육자, 비공개 데이터, 연락처, 게시물 원문, 미디어는 제외했다.

#### 데이터 계약

각 레코드에 다음을 포함했다.

- 정규화된 Instagram 프로필 URL
- 계정 유형·국가·운영 주체(공개된 경우)
- 팔로워·팔로잉·게시물·참여율 스냅샷(가용한 경우)
- 1차·보조 출처
- 관측일
- `high | medium | stale` 신뢰도
- 비활성 상태

#### 반복

1. 첫 공개 리서치 시드 24개를 만들었다.
2. 같은 importer를 두 번 실행해 24개로 유지되는 멱등성을 확인했다.
3. 출처를 확장해 58개 고유 계정으로 정리했다.
4. PostgreSQL에 58개를 upsert하고 조회 API의 팔로워 순위를 확인했다.

#### 검증

- 58개 실제/선언 레코드 일치
- 사용자명 58개 고유
- 신뢰도 `high=17`, `medium=36`, `stale=5`
- 모든 행에 provenance 존재
- backend `39 passed`
- Python compile, `git diff --check` 통과

관련 커밋: `590add8`, `932f0cf`

### 4.7 7단계 — 공유 가능한 데이터셋 패키지와 Git 게시

대표 프롬프트:

> “저장된 해당 데이터셋 공유 가능한 파일로 제작해줘.”
>
> “확장 데이터셋 git 푸시해주세요.”

#### 구현

- UTF-8 JSON 58개
- 한국어 README와 필드 설명
- 파일 크기와 SHA-256을 가진 `MANIFEST.json`
- 세 파일을 묶은 ZIP
- 동일 결과를 재현하는 Node export script

#### 오류와 복구

첫 Git 게시 시도에서 `gh auth status`가 활성 자격 증명을 invalid로 보고했다. 이때 파일을 stage하거나 임의 credential을 사용하지 않았다. 사용자가 인증을 복구한 뒤 전체 데이터·체크섬·테스트를 다시 검증하고 게시했다.

#### 검증

- ZIP 내부 3개 파일 무결성 통과
- 매니페스트 SHA-256과 실제 파일 일치
- 순위 연속성 및 팔로워 내림차순 확인
- private contact field 0개
- Node syntax, backend `39 passed`, `git diff --check` 통과

산출물: [AI Instagram Influencers 58 공유 폴더](outputs/ai-influencer-dataset-2026-08-16/)

### 4.8 8단계 — `main` 프론트 동기화와 호환성 감사

대표 프롬프트:

> “main에 있는 프론트 자료 가져와서 gamzerA의 프론트로 적용시킨 후 푸시해주세요.”

#### 완료한 일

- `origin/main`의 `page.tsx`, `globals.css`, `api.ts`, `types.ts`를 정확히 동기화
- 데이터셋 변경과 함께 `932f0cf`로 `gamzerA`에 push
- 기존 PR #1을 갱신

#### 검증

- 프론트 `npm run lint` 통과
- 프론트 `npm run build` 통과
- 복사한 프론트 파일 hash가 당시 `origin/main`과 일치
- backend `39 passed`

#### 발견한 런타임 문제

프론트가 호출하는 Storylog API:

```text
/api/me
/api/access/invite
/api/records
/api/packages
/api/publications
/api/export
```

`gamzerA`가 제공하는 핵심 API:

```text
POST /api/admin/influencers/crawl
GET  /api/influencers
```

따라서 초기 `/api/me`와 로그인 요청은 404가 된다. 이 사실을 Build 성공과 분리해 기록했다.

#### 병합 감사

- merge base: `bf9191e`
- 당시 `origin/main`과 `gamzerA`: 각각 7커밋 분기
- 실제 텍스트 충돌 5개:
  - `.env.example`
  - `chat-log/2026-08-16-1305-storylog-mvp.md`
  - `influence-be/app/config.py`
  - `influence-be/app/main.py`
  - `influence-be/requirements.txt`
- 프론트 트리는 충돌 없음
- 추가 위험: pgvector 이미지 전환, 병합 의존성 재빌드, 운영 비밀값과 `APP_ENV` 누락

충돌 해결안을 만들고 `git diff --check`까지 확인했지만, 사용자가 이후 기능 병합 대신 디자인 테마만 변경하도록 범위를 좁혔다. 따라서 이 병합은 공개 브랜치에 커밋하지 않았다.

### 4.9 9단계 — 기능을 유지한 HumanProof 디자인 테마

대표 프롬프트:

> “여기에서 나머지는 그대로 두고 디자인 테마만 변경시켜주세요.”

전체 원문은 [HumanProof 디자인 프롬프트](docs/prompts/humanproof-design-prompt.md)에 보존했다.

#### 범위 결정

- `page.tsx`, `api.ts`, `types.ts`, backend, metadata는 변경하지 않는다.
- 기존 class와 상호작용을 그대로 둔다.
- `influence-fe/app/globals.css`만 변경한다.

#### 반영한 테마

- 배경 `#F7F5F0`
- 표면 `#FFFFFF`
- 본문 `#171717`
- 보조 텍스트 `#6F6B65`
- 경계 `#E6E1D9`
- 포레스트 `#245C4F`
- 근거 블루 `#376FA3`
- 녹음 코랄 `#D9695F`
- 모바일 20px 거터
- 44px 이상 조작 영역
- 224px 데스크톱 레일, 76px 태블릿 레일
- 680–760px 중심 콘텐츠 폭
- `focus-visible`, 고대비, `prefers-reduced-motion`

#### 검증과 실행

- `npm ci`: 성공, 취약점 0
- `npm run lint`: 통과
- `npm run build`: 통과
- `git diff --check`: 통과
- 추적된 기능 파일 변경 없음
- `npm run dev`: 실행(프로젝트 script가 port 3001 지정)
- `http://127.0.0.1:3001/`: HTTP 200
- 제공된 CSS 번들에서 네 핵심 브랜드 색상 확인

자동 브라우저 세션은 이 실행 환경에서 제공되지 않아 스크린샷 기반 6개 폭 검증은 완료 증거로 적지 않는다. 반응형 규칙은 CSS와 production build 수준에서 확인했다.

## 5. 오류 → 원인 → 수정 → 검증 요약

| 오류 | 실제 원인 | 수정/판단 | 검증 |
|---|---|---|---|
| HikerAPI 401 | 공급자가 현재 키를 승인하지 않음 | `/sys/balance`로 앱과 무관함을 확인하고 추가 유료 호출 중단 | 컨테이너·DB 정상, 0행 유지 |
| Instagram `robots_denied` | 일반 크롤러 비허용 | 우회하지 않고 실패 코드 반환 | 요청 1, 수집 0, 저장 0 |
| Bright Data 키 없음 | 외부 호출 전 설정 누락 | fail closed 503 | billable call 0 |
| Python TLS 인증서 실패 | Framework Python CA 경로 없음 | system trust curl fallback | `36 passed`, controlled 401 |
| 키 승인 후 connection reset | backend 재생성 직후 readiness race | 일시적 네트워크 오류만 retry | `39 passed`, `/ready` 완료 |
| Bright Data `upstream_error` | 데이터셋/역할 등 공급자 측 접근 문제 | 자동 유료 재시도 중단 | 프로필 신규 저장 0 |
| GitHub auth invalid | 로컬 `gh` credential 불량 | stage/commit 없이 중단, 재인증 후 재검증 | `932f0cf` push 완료 |
| 프론트 `/api/me` 404 | Storylog 프론트와 crawler backend 계약 불일치 | 병합 감사 후 범위 변경에 따라 기능 코드는 보존 | build 성공과 runtime 미완료를 분리 기록 |
| PR #1 충돌 | `main`과 `gamzerA` 분기 | 충돌 5개와 semantic union 해결안 도출 | 공개 merge는 아직 미완료 |

## 6. 검증 전략

### 코드 검증

- Python compile
- Backend pytest: `14 → 21 → 29 → 34 → 36 → 39`로 기능 증가 시 반복
- Frontend ESLint
- Next.js production build
- Node export script syntax
- `docker compose config --quiet`
- `git diff --check`

### 런타임 검증

- Docker health와 `/ready`
- OpenAPI에서 폐기·신규 route 확인
- 외부 호출 전 fail-closed 확인
- DB row count와 멱등 upsert 확인
- 프론트 HTTP 200과 실제 CSS asset 확인

### 데이터 검증

- 레코드 수와 고유 사용자명
- 팔로워 순위와 숫자 범위
- 출처·관측일·신뢰도 존재 여부
- private contact field 부재
- ZIP 목록, 크기, SHA-256 매니페스트

## 7. 중요한 판단

### 정책을 우회해 개수를 늘리지 않았다

Instagram이 차단했을 때 헤드리스 브라우저·로그인 세션·프록시로 우회하지 않았다. 계정 소유자 export, 공식 API 또는 계약된 공급자를 별도 경로로 두었다.

### 실패를 비용이 발생하는 재시도로 덮지 않았다

HikerAPI와 Bright Data 모두 한 건으로 경계를 확인했다. 공급자 오류를 확인한 뒤 batch 요청을 멈췄다.

### 원시 공급자 데이터보다 정규화된 최소 필드만 저장했다

연락처와 raw payload를 저장하지 않고 프로필 URL, 공개 지표, 출처, 관측일, 신뢰도를 중심으로 정리했다.

### 데이터셋의 한계를 문서화했다

58개는 실시간 Instagram 원장 데이터가 아니다. 5개는 `stale`이고, 캠페인 의사결정 전에는 공급자 또는 공식 경로로 새로 확인해야 한다.

### 범위 변경 시 기존 작업을 버리지 않았다

병합 중인 원래 작업공간은 삭제하거나 reset하지 않았다. `origin/gamzerA@932f0cf`에서 별도 작업공간을 만들어 디자인과 Build Log를 진행했다.

## 8. 주요 커밋

| 커밋 | 의미 |
|---|---|
| `0a69756` | 관리자 전용 HikerAPI 수집·PostgreSQL 프로필 저장 |
| `75b0a07` | HikerAPI 설정 작업 기록 |
| `695c0c7` | 로컬 HikerAPI 검증 기록 |
| `412433a` | 교체 키 재검증 기록 |
| `a707647` | HikerAPI를 핵심에서 분리한 서비스 방향 |
| `590add8` | 정책 준수 public web/Bright Data 파이프라인과 AI influencer seed |
| `932f0cf` | 58개 데이터셋·공유 ZIP·`main` 프론트 동기화 |
| `dd94291` | HumanProof CSS 테마·원문 프롬프트·심사용 Codex Build Log |

## 9. 대표 프롬프트 인덱스

모든 원문은 [대화 로그](chat-log/2026-08-16-1305-storylog-mvp.md)에 보존돼 있다.

| 단계 | 대표 프롬프트 |
|---|---|
| API 수집 | “hiker api 로 인플루언서 db 수집” |
| 키 검증 | “api key 발급 완료”, “설정 완료”, “키 교체 완료” |
| 방향 전환 | “hiker api로 수집하는 기능은 삭제하고… 크롤링하여 db 구축” |
| 실계정 데모 | `ye_ong_leee` Instagram URL 제공 |
| 공급자 연동 | “인플루언서 데이터 크롤링 수집 가능한 api 연동 방법” |
| 자동화 | “토큰 발행까지 자동화하세요” |
| 오류 복구 | SSL 인증서 오류와 connection reset 전체 출력 제공 |
| 데이터 확장 | “현재 인스타그램에서 유명한 ai 인플루언서 정보를 최대한…” |
| 공유 | “저장된 해당 데이터셋 공유 가능한 파일로 제작해줘.” |
| Git 게시 | “확장 데이터셋 git 푸시해주세요.” |
| 프론트 동기화 | “main에 있는 프론트 자료… gamzerA의 프론트로 적용” |
| API/병합 | “404… PR #1… 충돌 해결이 필요합니다.” |
| 디자인 | HumanProof 390줄 상세 프롬프트 |
| 범위 정정 | “나머지는 그대로 두고 디자인 테마만 변경” |
| 실행 | “디자인 변경이 완성되었으면 그 파일 바로 실행” |

## 10. 주요 산출물

- [공개 웹 크롤링 운영 가이드](docs/web-crawling.md)
- [AI 가상 인플루언서 데이터셋 설명](docs/ai-virtual-influencer-dataset.md)
- [58개 원천 시드](influence-be/data/ai_virtual_influencers_expanded_2026-08-16.json)
- [공유 데이터셋 폴더](outputs/ai-influencer-dataset-2026-08-16/)
- [재현 가능한 export script](scripts/export_ai_influencers_share.mjs)
- [Bright Data 설정 자동화](scripts/setup_brightdata.py)
- [전체 작업 원문](chat-log/2026-08-16-1305-storylog-mvp.md)
- [HumanProof 디자인 프롬프트 원문](docs/prompts/humanproof-design-prompt.md)

## 11. 현재 상태와 남은 일

### 완료

- 정책 준수 인플루언서 수집·정규화·DB 저장 구조
- Bright Data 설정 자동화와 오류 복구
- 58개 공개 출처 기반 AI/가상 Instagram 프로필
- 공유 가능한 JSON/README/manifest/ZIP
- `932f0cf`까지 `gamzerA` 공개
- Storylog 프론트 production build
- 기능을 건드리지 않은 디자인 테마
- 로컬 `http://localhost:3001` 실행

### 미완료 또는 의도적으로 보류

- Bright Data 프로필 데이터셋 권한 문제 해결과 58개 live refresh
- Storylog API와 influencer API의 안전한 통합
- PR #1의 최종 conflict-free merge
- 운영 `APP_ENV`, 강한 session secret, OAuth URL, API URL 설정
- 인증 쿠키와 API를 같은 origin으로 연결한 안전한 공개 배포
- 실제 브라우저에서 360·390·430·768·1024·1440 스크린샷 회귀 검증

이 항목들은 구현된 것으로 표시하지 않는다. 현재 가장 안전한 다음 단계는 Storylog API를 포함한 기준 브랜치를 명시적으로 선택한 뒤, `gamzerA` 인플루언서 라우트를 semantic merge하고 통합 테스트를 통과시키는 것이다. 디자인 테마 자체는 기능 코드와 독립적으로 완료됐다.
