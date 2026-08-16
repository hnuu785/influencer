# AWS production deployment

This directory contains the reproducible AWS deployment for the production MVP.
All commands below use `ap-northeast-2`.

## Architecture and cost boundary

- Amplify Hosting builds `influence-fe` from `main`.
- ECS Express Mode runs the FastAPI image from ECR.
- PostgreSQL runs in a private, Single-AZ RDS instance.
- The ECS tasks use public subnets so the public Express endpoint works without a
  NAT Gateway. The tasks accept inbound traffic only through security groups
  managed by Express Mode. RDS accepts PostgreSQL traffic only from the ECS task
  security group.
- The artifact S3 bucket is private and encrypted. It is not used by the current
  application yet.
- Redis, Runpod workers, a custom domain, and a staging environment are not
  created.

ECS, the Application Load Balancer, RDS, CloudWatch, and data transfer continue
to incur charges while they exist. RDS deletion protection is enabled.

## 1. Bootstrap GitHub OIDC

Use an AWS administrator session once. Do not create an IAM access key for
GitHub.

Check whether this AWS account already has the GitHub OIDC provider:

```bash
aws iam list-open-id-connect-providers --region ap-northeast-2
```

For an account without the provider:

```bash
aws cloudformation deploy \
  --region ap-northeast-2 \
  --stack-name influence-bootstrap \
  --template-file infra/bootstrap.yml \
  --capabilities CAPABILITY_NAMED_IAM
```

If `token.actions.githubusercontent.com` is already registered, reuse its ARN:

```bash
aws cloudformation deploy \
  --region ap-northeast-2 \
  --stack-name influence-bootstrap \
  --template-file infra/bootstrap.yml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    UseExistingGitHubOidcProvider=true \
    ExistingGitHubOidcProviderArn=arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com
```

Read the two role outputs:

```bash
aws cloudformation describe-stacks \
  --region ap-northeast-2 \
  --stack-name influence-bootstrap \
  --query 'Stacks[0].Outputs' \
  --output table
```

## 2. Configure GitHub

In repository **Settings → Secrets and variables → Actions → Variables**, add:

| Variable | Value |
| --- | --- |
| `AWS_REGION` | `ap-northeast-2` |
| `AWS_ACCOUNT_ID` | The 12-digit AWS account ID |
| `AWS_DEPLOY_ROLE_ARN` | Bootstrap output `GitHubDeployRoleArn` |
| `CFN_EXECUTION_ROLE_ARN` | Bootstrap output `CloudFormationExecutionRoleArn` |

Create a GitHub environment named `production` without required reviewers. The
workflow is intentionally automatic after tests pass. The OIDC trust policy still
restricts access to `hnuu785/influencer` on `main`.

Run **Deploy backend** once from the Actions page, or merge a backend/infra change
to `main`. The workflow creates the platform, pushes an image tagged with the Git
commit, deploys the digest through ECS Express Mode, and tests `/health` and
`/ready`.

Get the generated API URL from the workflow summary or stack output:

```bash
aws cloudformation describe-stacks \
  --region ap-northeast-2 \
  --stack-name influence-service-prod \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
  --output text
```

## 3. Connect Amplify

1. In Amplify Hosting, choose **Deploy an app → GitHub** and authorize only this
   repository.
2. Select branch `main`, enable **My app is a monorepo**, and enter
   `influence-fe` as the app root. Amplify sets `AMPLIFY_MONOREPO_APP_ROOT` and
   uses the root `amplify.yml` to build with Node.js 22.
3. Add `NEXT_PUBLIC_API_URL` with the ECS API URL, then deploy.
4. Copy the exact generated origin, such as
   `https://main.example.amplifyapp.com` (without a trailing slash).
5. Add that value as the GitHub repository variable `FRONTEND_ORIGIN` and rerun
   **Deploy backend**. This updates FastAPI CORS and the S3 CORS rule.

Until step 5, CORS uses `http://localhost:3001` so the backend can be bootstrapped
before Amplify has assigned a domain.

## Operations

- Backend logs: CloudWatch log group `/aws/ecs/influence-prod/backend`, retained
  for 14 days.
- Liveness: `GET <ApiUrl>/health`.
- Dependency readiness: `GET <ApiUrl>/ready`.
- Images: ECR repository `influence-backend`; only the 20 newest images remain.
- Runpod secret: `influence/prod/runpod-api-key`. It has no value and is not
  available to ECS until a model and authenticated API are implemented.
- Database migrations are intentionally absent because the repository has no
  application schema or Alembic configuration.

To remove the environment, first disable RDS deletion protection, then delete the
service stack followed by the platform stack. The final RDS snapshot and Runpod
secret are retained and must be removed explicitly if no longer needed.
