# System Architecture Mermaid

## 2026-08-16 16:41 KST

- User: hnuu785
- User message: 시스템 아키텍쳐를 짜는 과정에서는 mermaid chart 형태로 시각화 가능한 코드를 줘
- Response summary: Assumed a generic web service and provided reusable Mermaid templates for the system component architecture and a request sequence flow, with guidance on what to customize.
- Files changed: `chat-log/2026-08-16-1641-system-architecture-mermaid.md`
- Verification: Checked Mermaid syntax structure manually; templates use standard flowchart and sequenceDiagram constructs.
- Remaining issues: Replace generic component names and relationships with project-specific services, infrastructure, and data flows.

## 2026-08-16 16:45 KST

- User: hnuu785
- User message: 이 내용 토대로 이미지 파일로 시스템 아키텍처 그려
- Response summary: Generated a polished Korean system architecture diagram from the prior Mermaid architecture, using grouped layers, directional request/data arrows, and dotted observability flows. Saved the resulting PNG in the project workspace.
- Files changed: `docs/system-architecture.png`, `chat-log/2026-08-16-1641-system-architecture-mermaid.md`
- Verification: Visually inspected the generated diagram and verified the saved file as a valid 1536×1024 RGB PNG; SHA-256 `cf69b75abf35b5f3d9657ba592f34bb6674cfc90e3281872bd76cc88b19e8276`.
- Remaining issues: The diagram represents a generic web-service architecture; project-specific service names and infrastructure can be substituted in a later revision.

## 2026-08-16 16:48 KST

- User: hnuu785
- User message: 우리 시스템이랑 안 맞지 않아?
- Response summary: Confirmed that the generated image is a generic web-service diagram and does not match Storylog's actual architecture. Identified the production path as Next.js on Amplify, FastAPI on ECS Express/ECR, private RDS PostgreSQL with pgvector, private S3 uploads, Google OAuth/Calendar, OpenAI API, and CloudWatch; noted that payment, email, mobile, a queue worker, and production Redis are absent.
- Files changed: `chat-log/2026-08-16-1641-system-architecture-mermaid.md`
- Verification: Cross-checked `README.md`, `docker-compose.yml`, `infra/README.md`, `infra/service.yml`, `infra/platform.yml`, and backend integration code.
- Remaining issues: `docs/system-architecture.png` is still the incorrect generic diagram and should be replaced only after the user requests regeneration.

## 2026-08-16 16:54 KST

- User: hnuu785
- User message: 우리 시스템 아키텍처에 유저 플로우까지 들어간 도식화 이미지로 뽑아
- Response summary: Generated a new Storylog-specific architecture and user-flow infographic. The architecture shows Amplify/Next.js, ECS Express/FastAPI, RDS PostgreSQL with pgvector, private S3 direct uploads, OpenAI, Google OAuth/Calendar, and CloudWatch. The six-phase user journey includes mandatory user approvals for StoryCard selection and final package review. Iterated once to correct external-service connections so they originate from FastAPI rather than RDS.
- Files changed: `docs/storylog-system-architecture-user-flow.png`, `chat-log/2026-08-16-1641-system-architecture-mermaid.md`
- Verification: Visually checked topology and labels after the correction; verified the saved output as a valid 1536×1024 RGB PNG with SHA-256 `8771076a63b2993dfdca8eb5abe1d2e3edb50ff572daefea4e1d57aaf04aee37`.
- Remaining issues: The earlier generic `docs/system-architecture.png` remains unchanged for safe, non-destructive handling and should not be used as the current architecture.
