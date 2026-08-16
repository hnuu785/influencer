# AI 가상 인플루언서 공개 프로필 데이터셋

기준일은 2026-08-16이다. Instagram에 대한 직접 자동 요청은 robots 정책과
HTTP 429 제한 때문에 사용하지 않았다. 공개 분석 서비스, 연구 문서, 언론 기사에
표시된 스냅샷만 수집했으며 이메일·전화번호·원본 페이지 전체 내용은 저장하지
않았다.

## 현재 적재 결과

- PostgreSQL `influencer_profiles`: 58개
- 2026년 7~8월 스냅샷을 교차 확인한 `high`: 17개
- 2026년 자료의 단일 순위·벤치마크 출처인 `medium`: 36개
- 과거 수치이거나 현재 비활성 상태인 `stale`: 5개
- 저장 필드: 계정명, 프로필 URL, 표시 이름, 팔로워·팔로잉·게시물 수, 분야,
  가상 인물 유형, 국가, 제작·운영 주체, 지표 관측일, 출처, 신뢰도

팔로워 수는 실시간 값이 아니라 각 출처의 관측 시점 값이다. `stale` 계정은
인기 후보 탐색에는 쓸 수 있지만 순위·캠페인 의사결정 전에 재수집해야 한다.

## 상위 계정

| 계정 | 팔로워 스냅샷 | 관측 시점 | 유형 | 신뢰도 |
|---|---:|---|---|---|
| `@magazineluiza` | 9,357,177 | 2026-07-17 | 브랜드 가상 캐릭터 | high |
| `@nobodysausage` | 5,417,157 | 2026 자료·지표일 미상 | 애니메이션 가상 캐릭터 | medium |
| `@casasbahia` | 3,587,456 | 2026 자료·지표일 미상 | 브랜드 가상 캐릭터 | medium |
| `@thegoodadvicecupcake` | 2,508,353 | 2026 자료·지표일 미상 | 애니메이션 가상 캐릭터 | medium |
| `@lilmiquela` | 2,272,412 | 2026-07-18 | CGI 가상 인플루언서 | high |
| `@grannyspills` | 2,101,419 | 2026-07 | 생성형 AI 캐릭터 | high |
| `@guggimon` | 1,472,160 | 2026 자료·지표일 미상 | 애니메이션 가상 캐릭터 | medium |
| `@janky` | 1,015,642 | 2026 자료·지표일 미상 | 애니메이션 가상 캐릭터 | stale·비활성 |
| `@itspuffpuff` | 876,655 | 2026 자료·지표일 미상 | 애니메이션 가상 캐릭터 | medium |
| `@iamxalara` | 726,616 | 2026-08 | 생성형 AI 캐릭터 | high |
| `@millasofiafin` | 676,877 | 2026-07-25 | 생성형 AI 캐릭터 | high |
| `@deannaritter98` | 657,400 | 2026-08 | 생성형 AI 캐릭터 | high |
| `@emilypellegrini` | 551,100 | 2026-01 | 생성형 AI 캐릭터 | medium |
| `@gioalemann` | 504,267 | 2024-08 | 생성형 AI 캐릭터 | stale |
| `@leyalovenature` | 498,134 | 2026-08 | CGI 가상 인플루언서 | high |
| `@iam_zlu` | 477,600 | 2026-07 | CGI 가상 인플루언서 | medium |
| `@noonoouri` | 459,503 | 2026-07-28 | CGI 가상 인플루언서 | high |
| `@fit_aitana` | 402,200 | 2026-07-22 | 생성형 AI 캐릭터 | high |
| `@naina_avtr` | 395,725 | 2026-07 | CGI 가상 인플루언서 | high |
| `@imma.gram` | 379,500 | 2026-07-24 | CGI 가상 인플루언서 | high |
| `@realqaiqai` | 341,018 | 2024-08 | 애니메이션 가상 캐릭터 | stale |
| `@sika.moon` | 310,230 | 2024-08 | 생성형 AI 캐릭터 | stale |
| `@miazelu` | 286,700 | 2026-08 | 생성형 AI 캐릭터 | high |
| `@aditi.aimuse` | 261,200 | 2026-08 | 생성형 AI 캐릭터 | high |
| `@kyraonig` | 238,500 | 2026-07 | CGI 가상 인플루언서 | high |
| `@shudu.gram` | 236,104 | 2026-07 | CGI 가상 인플루언서 | high |
| `@thecodemiko` | 196,000 | 2025 | 실시간 가상 아바타 | stale |
| `@kenza.layli` | 164,351 | 2026-07 | 생성형 AI 캐릭터 | high |
| `@rozy.gram` | 162,204 | 2026-07 | CGI 가상 인플루언서 | high |
| `@blawko22` | 115,000 | 2026-01 | CGI 가상 인플루언서 | medium |
| `@aliciaidris98` | 105,800 | 2026-03 | 생성형 AI 캐릭터 | medium |
| `@serahreikka` | 101,100 | 2026-03 | 생성형 AI 캐릭터 | medium |
| `@aina_avtr` | 97,800 | 2026-03 | CGI 가상 인플루언서 | medium |
| `@amara_gram` | 58,800 | 2026-01 | 생성형 AI 캐릭터 | medium |

## 재현 방법

시드 원본은 다음 두 파일에 있다. 각 레코드에는 지표를 가져온 `source_url`과
`observed_at`이 포함되며, 교차 확인한 경우 `secondary_source_urls`도 저장한다.

- `influence-be/data/ai_virtual_influencers_2026-08-16.json`: 최초 24개
- `influence-be/data/ai_virtual_influencers_expanded_2026-08-16.json`: 최신 공개
  순위·분석 자료에서 확장한 34개

```bash
docker compose exec -T backend python3 -m app.seed_ai_virtual_influencers
curl 'http://127.0.0.1:8001/api/influencers?limit=100'
```

upsert 키는 정규화한 Instagram 프로필 URL의 SHA-256이다. 같은 시드를 다시
실행해도 중복 행을 만들지 않는다.

## 다음 수집 단계

Bright Data 프로필 데이터셋 권한과 요청 형식이 확인되면 58개 URL을 20개 이하
배치로 재조회해 소개문, 프로필 이미지, 인증 여부, 팔로워·팔로잉·게시물 수를
최신화할 수 있다. 현재 계정의 첫 프로필 요청은 `upstream_error`였으므로 원인
HTTP 상태를 안전하게 확인하기 전에는 유료 배치를 실행하지 않는다. 게시물 본문·
이미지·댓글을 레퍼런스 데이터로 사용할 때는 프로필 테이블과 분리하고, 권리 상태·
개인정보 상태·수집 시각·삭제 상태를 별도 필드로 관리해야 한다.
