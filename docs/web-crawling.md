# 공개 웹 인플루언서 DB 크롤링

사용자가 지정한 공개 프로필 URL을 조회해 PostgreSQL `influencer_profiles`
테이블에 저장하는 관리자용 기능이다. 사이트별 `robots.txt`를 먼저 확인하고,
일반 크롤러 접근이 허용된 HTML 페이지만 읽는다.

## 수집 범위

- 프로필 URL, 플랫폼, 사용자명
- 표시 이름과 공개 소개문
- 프로필 이미지와 공개 외부 링크
- 페이지 메타데이터에 명시된 팔로워·팔로잉·게시물 수
- 인증 여부와 직업·카테고리(구조화 데이터에 있을 때만)
- 수집 출처와 최초·최근 수집 시각

JSON-LD의 `Person`·`Organization`·`ProfilePage`, OpenGraph, 일반 HTML meta를
순서대로 사용한다. 이메일과 전화번호는 소개문에서 저장 전에 마스킹한다.
페이지가 공개하지 않는 값은 추정하지 않고 `null`로 저장한다.

## 안전 경계

- HTTPS 공개 주소만 허용한다.
- DNS 결과가 사설·루프백·링크 로컬 주소이면 차단한다.
- redirect 목적지도 같은 검사를 다시 수행한다.
- `robots.txt`를 가져올 수 없거나 접근을 금지하면 실패 상태로 기록한다.
- robots 규칙은 최대 1시간 캐시한 뒤 다시 확인한다.
- 기본 요청 간격은 호스트별 2초이며 robots의 crawl delay가 더 길면 이를 따른다.
- HTML 응답은 2MB로 제한하고 최대 redirect는 4회다.
- 로그인 세션, CAPTCHA 우회, 프록시 회전, 브라우저 위장 기능은 제공하지 않는다.

Instagram은 현재 일반 사용자 에이전트에 `Disallow: /`를 선언하므로 직접
프로필 크롤링 대상이 아니다. 서면 허가가 있다면 해당 허가 범위에 맞춘 별도
수집 경로를 구현해야 한다.

## 환경 설정

```dotenv
COLLECTOR_ADMIN_KEY=외부에_공개하지_않는_32자_이상_관리자_키
CRAWLER_USER_AGENT=InfluenceCrawler/1.0
CRAWLER_REQUEST_DELAY_SECONDS=2.0
CRAWLER_ALLOWED_DOMAINS=creator.example,another.example
```

`CRAWLER_ALLOWED_DOMAINS`가 비어 있으면 공개 DNS 주소를 가진 모든 호스트를
검사할 수 있지만, 운영 환경에서는 승인한 도메인만 명시하는 것을 권장한다.

## 실행

```bash
curl -X POST http://127.0.0.1:8001/api/admin/influencers/crawl \
  -H 'Content-Type: application/json' \
  -H 'X-Collector-Key: COLLECTOR_ADMIN_KEY의_값' \
  -d '{
    "urls": [
      "https://creator.example/about",
      "https://another.example/profile/creator"
    ]
  }'
```

응답의 `error_code`는 `robots_denied`, `robots_unavailable`, `not_found`,
`access_denied`, `rate_limited`, `timeout`, `network_error`, `dns_error`,
`private_address`, `unsupported_content`, `response_too_large`,
`profile_not_detected` 등이 될 수 있다. 일부 URL이 실패해도 성공한 프로필은
저장된다.

## 조회

```bash
curl 'http://127.0.0.1:8001/api/influencers'
curl 'http://127.0.0.1:8001/api/influencers?min_followers=100000'
curl 'http://127.0.0.1:8001/api/influencers?verified=true&limit=20&offset=0'
```

초기 데이터는 서비스 목적에 맞는 창작자의 공식 웹사이트나 robots가 허용한
프로필 URL을 직접 선별해 넣는다. 전체 웹 자동 발견보다 명시적인 seed 목록을
사용해야 데이터 출처와 삭제 요청을 추적하기 쉽다.

## Bright Data 공급자 모드

정책 검토와 공급자 계약을 마친 Instagram URL은 Bright Data 프로필 데이터셋을
통해 같은 DB 스키마로 수집할 수 있다.

```dotenv
INFLUENCER_PROVIDER=brightdata
BRIGHTDATA_API_TOKEN=발급받은_서버용_토큰
BRIGHTDATA_INSTAGRAM_PROFILE_DATASET_ID=gd_l1vikfch901nx3by4
BRIGHTDATA_BASE_URL=https://api.brightdata.com
```

대화형 발급·설정 도구를 사용하면 공식 키 관리 페이지 열기부터 토큰 검증, `.env`
갱신, Docker 백엔드 재생성까지 한 번에 처리할 수 있다.

```bash
python3 scripts/setup_brightdata.py
```

Bright Data는 공개 API 키 생성 REST API를 제공하지 않는다. 계정 소유자가
[공식 키 관리 화면](https://brightdata.com/cp/setting/users)에서 로그인·본인확인과
키 생성 승인을 완료해야 한다. 키에는 필요한 최소 권한과 만료일을 지정하고,
한 번 표시되는 값을 발급 도구의 숨김 프롬프트에 붙여 넣는다.

공급자 모드는 URL에서 추적 query를 제거한 뒤 Bright Data 동기 scrape API로
전송한다. 응답의 사용자명, 이름, 소개, 팔로워·팔로잉·게시물 수, 인증 여부,
이미지, 카테고리, 외부 URL만 공통 프로필에 매핑하며 전체 원본 응답은 저장하지
않는다. 이메일과 전화번호는 기존 크롤러와 동일하게 마스킹한다.

401·403은 `authentication_failed`, 402는 `payment_required`, 429는
`rate_limited`로 반환한다. 토큰이 비어 있으면 외부 요청 전에 HTTP 503으로
중단한다. API 토큰은 프론트엔드 코드나 Git에 포함하지 않는다.
