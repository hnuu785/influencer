# AI 가상 인플루언서 공개 프로필 데이터셋

기준일은 2026-08-16이다. Instagram에 대한 직접 자동 요청은 robots 정책과
HTTP 429 제한 때문에 사용하지 않았다. 공개 분석 서비스, 연구 문서, 언론 기사에
표시된 스냅샷만 수집했으며 이메일·전화번호·원본 페이지 전체 내용은 저장하지
않았다.

## 현재 적재 결과

- PostgreSQL `influencer_profiles`: 24개
- 2026년 7~8월 스냅샷을 교차 확인한 `high`: 13개
- 2026년 초 또는 단일 순위 출처인 `medium`: 7개
- 2024~2025년 수치만 확인된 `stale`: 4개
- 저장 필드: 계정명, 프로필 URL, 표시 이름, 팔로워·팔로잉·게시물 수, 분야,
  가상 인물 유형, 국가, 제작·운영 주체, 지표 관측일, 출처, 신뢰도

팔로워 수는 실시간 값이 아니라 각 출처의 관측 시점 값이다. `stale` 계정은
인기 후보 탐색에는 쓸 수 있지만 순위·캠페인 의사결정 전에 재수집해야 한다.

## 상위 계정

| 계정 | 팔로워 스냅샷 | 관측 시점 | 유형 | 신뢰도 |
|---|---:|---|---|---|
| `@lilmiquela` | 2,272,412 | 2026-07-18 | CGI 가상 인플루언서 | high |
| `@grannyspills` | 2,101,419 | 2026-07 | 생성형 AI 캐릭터 | high |
| `@millasofiafin` | 676,877 | 2026-07-25 | 생성형 AI 캐릭터 | high |
| `@emilypellegrini` | 551,100 | 2026-01 | 생성형 AI 캐릭터 | medium |
| `@gioalemann` | 504,267 | 2024-08 | 생성형 AI 캐릭터 | stale |
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

시드 원본은 `influence-be/data/ai_virtual_influencers_2026-08-16.json`에 있다.
각 레코드에는 지표를 가져온 `source_url`과 `observed_at`이 포함된다.

```bash
docker compose exec -T backend python3 -m app.seed_ai_virtual_influencers
curl 'http://127.0.0.1:8001/api/influencers?limit=100'
```

upsert 키는 정규화한 Instagram 프로필 URL의 SHA-256이다. 같은 시드를 다시
실행해도 중복 행을 만들지 않는다.

## 다음 수집 단계

Bright Data 토큰이 설정되면 24개 프로필 URL을 공급자 API로 재조회해 소개문,
프로필 이미지, 인증 여부, 팔로워·팔로잉·게시물 수를 최신화할 수 있다. 게시물
본문·이미지·댓글을 레퍼런스 데이터로 사용할 때는 프로필 테이블과 분리하고,
권리 상태·개인정보 상태·수집 시각·삭제 상태를 별도 필드로 관리해야 한다.
