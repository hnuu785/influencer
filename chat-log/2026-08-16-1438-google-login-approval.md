# Google 로그인 승인 문의

## 2026-08-16 14:38 KST

- 사용자: hnuu785
- 사용자 메시지: "구글로그인을 서비스에 달면 바로 달 수 있을까? 구글 클라우드에서 검사하고 승인하고 이런 과정 있지 않아?"
- 응답 요약 및 결정: 기본 로그인 범위(`openid`, `email`, `profile`)만 사용하는 경우 개발·테스트는 즉시 가능하고 민감/제한 범위 심사는 필수가 아님을 설명한다. 외부 공개 시 Google Auth Platform의 OAuth 클라이언트, 승인된 도메인/리디렉션 URI, 개인정보처리방침 등의 운영 설정과 선택적인 브랜드 인증이 필요하며, Gmail·Drive 등 민감/제한 범위 사용 시 별도 검증이 필요하다고 안내한다.
- 변경 파일: `chat-log/2026-08-16-1438-google-login-approval.md`
- 검증: Google 공식 OAuth 및 Google Auth Platform 최신 문서에서 범위별 검증 요건, 테스트 사용자 제한, 브랜드 인증 요건을 확인했다.
- 남은 이슈/후속 작업: 실제 서비스에서 요청할 OAuth scope와 배포 도메인이 확정되면 구체적인 승인 필요 여부 및 구현 절차를 점검할 수 있다.

## 2026-08-16 14:50 KST

- 사용자: hnuu785
- 사용자 메시지: "구글 로그인을 붙이기 위해 내가 해야하는 세팅에 대해 말해줘."
- 응답 요약 및 결정: 현재 Next.js/Amplify 프론트엔드와 FastAPI/ECS 백엔드 구조 및 제품 문서를 확인했다. 기획서상 로그인은 MVP 제외 항목임을 알리고, 범위를 변경해 진행한다면 Amazon Cognito User Pool을 중앙 인증자로 두고 Google을 소셜 IdP로 연결하는 구성을 권장한다. 사용자가 수행할 Google Auth Platform의 브랜딩·대상·범위·OAuth 클라이언트 설정과 Cognito 콜백 값, 테스트/운영 전환, 비밀값 취급을 단계별로 안내한다.
- 변경 파일: `chat-log/2026-08-16-1438-google-login-approval.md`
- 검증: 프로젝트의 `README.md`, 프론트엔드 패키지, FastAPI 설정, Amplify 및 AWS 인프라 파일, 제품 기획서를 확인했다. Google, AWS Cognito, Auth.js 및 Amplify 공식 문서에서 리디렉션 URI·JWT 검증·운영 설정을 확인했다.
- 남은 이슈/후속 작업: 로그인 기능을 이번 MVP에 포함할지 결정해야 한다. 포함한다면 운영 프론트엔드 URL과 서비스 도메인, 개인정보처리방침 URL을 확정한 후 Cognito/Google 설정과 코드·인프라 구현을 진행한다.

## 2026-08-16 14:56 KST

- 사용자: hnuu785
- 사용자 메시지: "구글 클라우드 콘솔에서 내가 세팅해야 하는 건 없어?"
- 응답 요약 및 결정: Google Cloud Console에서 필수로 수행해야 하는 작업을 Cognito 연동 기준으로 분리해 안내한다. 프로젝트 생성, Google Auth Platform의 Branding/Audience/Data Access 설정, Web application OAuth client 생성, Cognito 도메인과 `/oauth2/idpresponse` 등록, Client ID/Secret의 안전한 전달 및 테스트 사용자를 핵심으로 설명한다. 기본 로그인만 사용할 경우 별도의 Google API 활성화는 필요 없음을 명확히 한다.
- 변경 파일: `chat-log/2026-08-16-1438-google-login-approval.md`
- 검증: 직전 턴에서 확인한 Google Auth Platform 및 AWS Cognito 공식 최신 문서의 설정 경로와 리디렉션 URI 요구사항을 재사용했다.
- 남은 이슈/후속 작업: Cognito 로그인 도메인이 생성되어야 Google OAuth Client의 정확한 origin과 redirect URI를 확정할 수 있다.
