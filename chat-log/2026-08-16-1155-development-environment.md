# Development environment and AWS deployment

## Turn 37

### User (hnuu785) — 2026-08-16 17:26 KST

> 구글로그인 실패했어. 왜지?
>
> Attached: the deployed Amplify frontend showing `Failed to fetch` after selecting Google login.

### Codex response and decisions

- Diagnosed the immediate failure as a CORS rejection before the Google OAuth flow starts.
- Explained that the backend still permits only the local frontend origin and does not return `Access-Control-Allow-Origin` for the Amplify URL.
- Noted a second configuration gap: the ECS service does not currently receive production Google OAuth client settings or production callback/frontend URLs, so real Google login is not yet configured even after CORS is corrected.

### Files changed

- `chat-log/2026-08-16-1155-development-environment.md` (recreated because `chat-log/` was absent on the current `develop` branch)

### Verification

- Sent an OPTIONS preflight from origin `https://main.dt70s26a0ny4l.amplifyapp.com` to `/api/access/invite`; the backend returned HTTP 400 without `Access-Control-Allow-Origin`.
- A direct POST reached the backend, confirming the service and invite endpoint are running.
- CloudFormation stack `influence-service-prod` currently has `CorsOrigins=http://localhost:3001`.
- `infra/service.yml` does not inject `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `APP_PUBLIC_API_URL`, or `APP_FRONTEND_URL` into ECS.

### Remaining work

- Add GitHub repository variable `FRONTEND_ORIGIN=https://main.dt70s26a0ny4l.amplifyapp.com` and rerun `Deploy backend`.
- Add production Google OAuth client/secret storage and ECS injection, set the backend callback URL, and register that exact callback in Google Cloud before real Google login can work.
