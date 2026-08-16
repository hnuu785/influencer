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

## Turn 42

### User (hnuu785) — 2026-08-16 22:26 KST

> 안전한 삭제 알려줘

### Codex response and decisions

- Scoped the safe removal to the Amplify `main` branch deployment, preserving the Amplify app, GitHub repository/branch, backend, database, and S3 data.
- Recommended recording the current app root and environment variables, disabling automatic builds, confirming no active job, and deleting only the Amplify branch.
- Warned against choosing `Delete app` and explained that backend infrastructure and its costs remain afterward.

### Files changed

- `chat-log/2026-08-16-1155-development-environment.md`

### Verification

- AWS documents a dedicated `DeleteBranch` operation for deleting a branch belonging to an Amplify app, separately from `DeleteApp`.
- Target app ID is `dt70s26a0ny4l` and target Amplify branch is `main`.

### Remaining work

- User must delete only the Amplify `main` branch in the console, then verify that its Amplify URL no longer serves the frontend.
- Backend and data removal require a separate, explicitly authorized teardown procedure.

## Turn 43

### User (hnuu785) — 2026-08-16 22:29 KST

> 브랜치 삭제가 안 보여
>
> Attached: Amplify branch settings with `main` selected and the Actions menu showing `브랜치 분리`.

### Codex response and decisions

- Identified `브랜치 분리` as the current console label for removing/disconnecting the Amplify branch deployment.
- Directed the user to keep `main` selected, choose `작업 → 브랜치 분리`, and confirm only the Amplify branch connection is being removed.
- Confirmed that automatic builds are already disabled in the screenshot.

### Files changed

- `chat-log/2026-08-16-1155-development-environment.md`

### Verification

- The screenshot shows the `main` row selected and its auto build status as disabled.
- AWS models disconnecting an Amplify branch separately from deleting the Amplify app or the source Git repository.

### Remaining work

- Confirm the branch disconnect dialog and verify the Amplify URL is no longer served after propagation.

## Turn 44

### User (hnuu785) — 2026-08-16 22:30 KST

> 여기서 Cancel workflow가 어딨어?
>
> Attached: GitHub Actions run list showing only completed runs with green checks.

### Codex response and decisions

- Explained that `Cancel workflow` is absent because no workflow is currently running or queued; all visible runs have completed.
- Directed the user to disable the `Deploy backend` workflow from its workflow page to prevent future backend deployments.
- Clarified that canceling or disabling GitHub Actions does not take an already deployed ECS backend offline.

### Files changed

- `chat-log/2026-08-16-1155-development-environment.md`

### Verification

- The latest visible CI and backend deployment runs in the screenshot all have green completion indicators and elapsed durations.

### Remaining work

- Disable `Deploy backend` if future `main` updates must not deploy.
- Use a separate AWS teardown procedure if the goal is to take the existing backend service offline and stop its costs.
