# 최종 제출 README 및 Codex Build Log

## 2026-08-16 16:54 KST

- 사용자: hnuu785
- 사용자 메시지(원문):

> 최종 제출 시 PPT(발표자료), 데모/MVP, Codex Build Log를 모두 Git Repository에 업로드하고, README에 각 자료의 위치를 명시해주세요.
>
> 발표자료 : PPT 등 발표에 사용한 자료 포함
> MVP : 프론트엔드뿐 아니라 백엔드/DB 등 필요한 구성요소가 배포되어 실제로 동작 가능한 상태를 기준으로 합니다.
> Codex Build Log : .md 형식을 권장하며, 팀원별 Codex 작업 로그를 각각의 Markdown 파일로 정리해 제출 부탁드립니다.
> ~/.codex/sessions/에서 해당 작업 세션에 대해 팀원 각각의 로그를 '팀번호_성함_번호_log.md' 형식으로 정리하여 올려주세요.
> 단순 Git commit 이력보다는 Codex에 업무를 위임하고 계획 → 구현 → 반복 수정 → 오류 복구 → 검증한 과정이 드러나도록 정리해주세요.
> Codex를 사용하며 겪은 시행착오와 수정 과정 역시 중요한 평가 대상입니다.
>
> README.md를 수정해줘.
>
> 그리고 Codex Build Log를 완성해야 해. 지금까지의 대화 내용에서 심사위원분들이 보기 편하게 정리할거야.
>
> Codex에 업무를 위임하고 계획·구현·반복·오류 복구·검증한 과정을 담은 **Codex Build Log**
>
> 심사위원이 잘 볼 수 있도록 md 파일로 정리
>
> - 심사 항목에 아예 **Codex Build Log** 가 들어가 있다. 그러니까 단순히 “Codex로 코드 많이 짰습니다.” 보다 우리의 **문제 → 계획 → 위임 → 결과 → 오류 → 수정 → 검증** 흐름이 보이는 게 좋다.
>   - Codex에 업무를 위임하고 계획·구현·반복·오류 복구·검증한 과정을 담은 **Codex Build Log**
> - Codex 대화나 작업 내역을 함부로 날리면 안됨 + 프롬프트도 평가에 들어감.
> - 고민과 해결이 과정이 잘 들어가야 한다.

- 응답 요약 및 결정: `~/.codex/sessions/2026/08/16/`에서 현재 저장소를 작업 디렉터리로 사용한 세션을 선별하고, 기존 `chat-log/`, Git 이력, 현재 코드, AWS stack과 실제 endpoint를 교차 확인했다. README 상단에 발표자료·MVP·Build Log의 위치와 완료 상태를 표로 추가했다. 제출용 Build Log는 문제 → 대표 프롬프트 → 계획·위임 → 구현 → 오류 → 수정 → 검증 순서로 개발환경, 기획, MVP, RAG, OAuth, 미디어/S3, AWS 배포를 재구성했다. 비밀값과 AWS 계정 식별자는 제외했다. 발표자료, Amplify 프론트엔드, 실제 팀 번호·실명이 아직 없다는 사실을 숨기지 않고 제출 전 남은 작업으로 표시했다.
- 변경 파일:
  - `README.md`
  - `presentation/README.md`
  - `docs/codex-build-log/팀번호미정_hnuu785_1_log.md`
  - `chat-log/2026-08-16-1648-final-submission-readme-build-log.md`
- 검증:
  - README의 저장소 내부 경로가 모두 존재함을 확인했다.
  - 백엔드 테스트: `16 passed`.
  - 프론트엔드 ESLint 및 production build: 통과.
  - Docker Compose 구성과 Git whitespace 검사: 통과.
  - 프로젝트 의존성으로 모든 CloudFormation template lint: 통과.
  - AWS Platform 및 ECS Express Service stack: `CREATE_COMPLETE`.
  - 배포 API의 `/health`, `/ready`, `/docs`: 모두 HTTP 200.
  - Amplify 앱 목록은 비어 있어 프론트엔드는 공개 배포 전임을 확인했다.
- 남은 이슈/후속 작업:
  - 팀 번호와 실명을 받아 Build Log를 정확한 `팀번호_성함_번호_log.md`로 바꿔야 한다.
  - 최종 PPT/PDF를 `presentation/`에 추가해야 한다.
  - Amplify 프론트엔드를 배포하고 CORS/S3 CORS 및 end-to-end smoke test를 완료해야 한다.
  - 현재 로컬의 S3 업로드 개선을 main에 반영한 뒤 실제 AWS presigned upload를 검증해야 한다.
  - 일반 웹 서비스로 잘못 생성된 아키텍처 이미지는 실제 Storylog 구성과 사용자 흐름에 맞게 교체해야 한다.

## 2026-08-16 16:56 KST

- 사용자: 조현우
- 사용자 메시지(원문): `24_조현우_7812_log.md`
- 응답 요약 및 결정: 사용자가 제공한 제출용 파일명을 팀 번호 24, 성명 조현우, 번호 7812로 해석했다. Build Log 파일을 `24_조현우_7812_log.md`로 변경하고, 문서 내부 식별 정보와 README 링크·안내 문구를 함께 수정했다.
- 변경 파일:
  - `README.md`
  - `docs/codex-build-log/24_조현우_7812_log.md`
  - `chat-log/2026-08-16-1648-final-submission-readme-build-log.md`
- 검증: 이전 임시 파일명이 남지 않았고 새 README 링크의 대상 파일이 존재하며 Markdown whitespace 검사를 통과했다.
- 남은 이슈/후속 작업: 발표자료 업로드, Amplify 프론트엔드 배포, 운영 S3 smoke test, 실제 시스템 아키텍처 이미지 교체가 남아 있다.
