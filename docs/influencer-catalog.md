# 인플루언서 프로필 카탈로그

## 목적과 경계

이 카탈로그는 공개 출처의 Instagram 프로필 스냅샷을 탐색하기 위한 보조
RAG다. 국가·분야·계정 유형·팔로워·참여율 조건에 맞는 후보를 찾는 데
사용하며, 콘텐츠 훅이나 성과를 추정하는 근거로 사용하지 않는다.

프로필 카탈로그와 Storylog 포맷 패턴 RAG는 별도 테이블과 검색 흐름으로
유지한다. 프로필 레코드의 `rights_basis`는 출처 이용 조건이 확인되기 전까지
`source_terms_unverified`이며, 이 상태의 데이터는 포맷 패턴으로 승격할 수
없다.

## 수집과 정규화

- 계정 식별 키: `platform + username`
- 다중값: `category`와 `country`를 배열로 변환
- 관측 시점: 원문과 함께 `day`, `month`, `year`, `unspecified` 정밀도 저장
- 검색 문서: 이름, 사용자명, 분야, 유형, 국가, 운영 주체만 결합
- 숫자 지표: 임베딩하지 않고 구조화 필터와 정렬에 사용
- 신선도: `stale`은 기본 검색에서 제외
- 출처: 모든 응답에 `source_url`, `observed_at`, `confidence` 포함

서버 시작 시 번들 데이터셋을 검증하고 기존 계정을 업서트한다. 메타데이터의
레코드 수가 실제 배열과 다르거나 계정 식별 키가 중복되면 시작을 실패시켜
불완전한 카탈로그가 조용히 반영되지 않게 한다.

## 검색 API

`GET /api/influencers`는 로그인한 사용자에게 제공한다.

| 파라미터 | 역할 |
|---|---|
| `q` | 이름·분야·유형·국가·운영 주체 자연어 검색 |
| `category`, `country`, `profile_type` | 분류 필터 |
| `min_followers`, `max_followers` | 팔로워 범위 |
| `min_engagement` | 최소 참여율 |
| `confidence` | `high`, `medium`, `stale` 선택 |
| `include_stale` | 기본 제외된 stale 레코드 포함 |
| `limit` | 최대 100개 결과 제한 |

PostgreSQL과 OpenAI 임베딩이 사용 가능하면 구조화 필터 후 코사인 유사도로
정렬한다. API 키가 없는 체험 환경에서는 한국어 별칭을 포함한 키워드 검색을
사용한다. 응답의 `retrieval_mode`가 실제 적용된 방식을 나타낸다.

## 포맷 패턴 RAG 승격 조건

외부 레퍼런스에서 포맷 패턴을 추가하려면 다음 정보가 별도로 필요하다.

- Reel·Carousel·Story 포맷
- 훅 유형, 전개 구조, CTA와 목적
- 대상 독자와 주제 태그
- 계정 규모 구간과 정규화 성과
- 출처 URL과 데이터셋 버전
- `licensed`, `public_domain`, `team_authored`, `user_owned` 중 하나의 권리 근거

권리 근거가 `source_terms_unverified`인 입력은 RAG 등록 단계에서 거부한다.
외부 게시물 자동 수집은 상업적 저장·분석·파생 활용 권리가 확인되기 전까지
활성화하지 않는다.
