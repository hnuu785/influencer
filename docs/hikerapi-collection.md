# HikerAPI 인플루언서 DB 수집

공개 Instagram 프로필을 HikerAPI에서 조회해 PostgreSQL `influencers` 테이블에 저장하는 관리자용 수집 기능이다. HikerAPI 공식 `/v2/user/by/username` 엔드포인트와 `x-access-key` 헤더를 사용한다.

## 수집 데이터

저장하는 필드는 다음과 같다.

- Instagram 사용자 ID와 사용자명
- 표시 이름과 소개문
- 프로필 이미지 URL과 외부 링크
- 팔로워·팔로잉·게시물 수
- 비공개·인증·비즈니스 계정 여부
- 비즈니스 카테고리
- 수집 출처와 최초·최근 수집 시각

공개 프로필에 포함되더라도 전화번호, 이메일, 전체 HikerAPI 원본 응답은 저장하지 않는다. 사용자 ID를 기본키로 사용하므로 사용자명이 바뀌어도 같은 계정으로 갱신된다.

## 환경 설정

루트 `.env`에 다음 값을 설정한다.

```dotenv
HIKERAPI_ACCESS_KEY=발급받은_HikerAPI_키
COLLECTOR_ADMIN_KEY=외부에_공개하지_않는_관리자_키
HIKERAPI_BASE_URL=https://api.hikerapi.com
```

`COLLECTOR_ADMIN_KEY`는 HikerAPI 키와 다른 값이어야 한다. 수집 엔드포인트가 외부에 노출됐을 때 다른 사용자가 유료 요청을 발생시키지 못하도록 보호하는 용도다. `.env`는 `.gitignore`에 포함되어 있다.

## 수집 실행

```bash
curl -X POST http://127.0.0.1:8001/api/admin/influencers/collect \
  -H 'Content-Type: application/json' \
  -H 'X-Collector-Key: COLLECTOR_ADMIN_KEY의_값' \
  -d '{
    "usernames": ["natgeo", "instagram", "nasa"]
  }'
```

요청당 사용자명은 1~50개다. `@`는 자동 제거되고 대소문자는 소문자로 정규화되며 중복 사용자명은 한 번만 요청한다. HikerAPI 호출 전에 DB 연결과 테이블 생성을 먼저 확인하므로 DB 장애 상태에서 유료 요청이 낭비되지 않는다. 프로필은 순차적으로 조회해 순간적인 호출량을 제한한다.

응답 예시는 다음과 같다.

```json
{
  "requested": 3,
  "collected": 2,
  "failed": 1,
  "items": [
    {"username": "natgeo", "status": "collected", "instagram_user_id": "787132", "error_code": null},
    {"username": "instagram", "status": "collected", "instagram_user_id": "25025320", "error_code": null},
    {"username": "missing", "status": "failed", "instagram_user_id": null, "error_code": "not_found"}
  ]
}
```

실패 코드는 `authentication_failed`, `not_found`, `rate_limited`, `timeout`, `network_error`, `upstream_error`, `invalid_response` 중 하나다. 일부 계정이 실패해도 성공한 계정은 저장된다.

## 조회

```bash
curl 'http://127.0.0.1:8001/api/influencers'
curl 'http://127.0.0.1:8001/api/influencers?min_followers=100000'
curl 'http://127.0.0.1:8001/api/influencers?verified=true&limit=20&offset=0'
```

기본 정렬은 팔로워 수 내림차순이다. 한 번에 최대 100개를 조회할 수 있다.

## 운영 권장 방식

1. 초기에는 서비스 주제와 맞는 공개 계정 20~50개를 직접 선별해 수집한다.
2. 하루 한 번 또는 일주일에 한 번 같은 사용자명을 다시 수집해 팔로워·게시물 수를 갱신한다.
3. `last_collected_at`이 오래된 계정부터 갱신해 API 비용을 제어한다.
4. 향후 해시태그·키워드 검색으로 후보를 찾더라도 검색 결과를 바로 저장하지 말고 팔로워 범위, 공개 계정 여부, 카테고리 기준을 먼저 적용한다.
5. 최근 게시물 기반 참여율은 프로필 수집과 별도 작업으로 분리한다. 프로필당 추가 API 요청이 필요하므로 초기 수집에서는 계산하지 않는다.

운영 환경에서는 HikerAPI 키와 관리자 키를 AWS Secrets Manager에 보관하고 ECS task secret으로 주입해야 한다. 현재 CloudFormation에는 해당 비밀값이 자동 연결되지 않으므로 프로덕션 배포 전에 별도 연결이 필요하다.
