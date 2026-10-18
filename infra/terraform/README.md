# Terraform

Infrastructure for running the API and worker on ECS Fargate in a new AWS environment. The web app is deployed on Vercel. This has not been applied yet, and the existing dev buckets `redactldr-originals-dev` and `redactldr-downloads-dev` are not part of this state.

| Path | What it creates |
|---|---|
| `bootstrap/` | State bucket and DynamoDB lock. Local state, applied once. |
| `modules/network` | VPC, two public subnets, two private subnets, one NAT. |
| `modules/storage` | Originals and downloads buckets, SSE-KMS, lifecycle, CORS. |
| `modules/ecr` | API and worker repositories. |
| `modules/elasticache` | One Valkey node with encryption at rest and in transit (`rediss://`). |
| `modules/secrets` | Secret names only. Values are added after apply. |
| `modules/iam` | Task roles, execution role, GitHub OIDC deploy role. |
| `modules/alb` | Load balancer, `/v1/health`, HTTPS when a domain and zone are set. |
| `modules/ecs` | API (2 tasks), worker (scales on queue depth), beat, migrate task. Circuit breaker rolls back a bad deploy. |
| `modules/observability` | Log groups, 5xx / queue / job-failure alarms, a dashboard. |
| `envs/dev.tfvars`, `envs/prod.tfvars` | Per environment. DNS is off until `domain_name` and `route53_zone_id` are set. |

## First-time setup

Run once from a machine with AWS credentials that can create the state bucket. Do not point it at the existing document buckets.

```bash
cd infra/terraform/bootstrap && terraform init && terraform apply
cd .. && terraform init -backend-config=envs/backend.hcl
terraform plan -var-file=envs/dev.tfvars
```

Leave `domain_name` and `route53_zone_id` empty until a hosted zone exists. With both set, Terraform requests an ACM certificate for `api.<domain>`, validates it in Route 53, serves HTTPS, and redirects HTTP to it. With them empty, the load balancer serves HTTP on port 80 so a plan does not need a domain.

After apply, set the secret values (console or `aws secretsmanager put-secret-value`). Terraform creates the names and never stores the values:

- `redactldr-<env>/database-url`: pooler URL the API and worker use
- `redactldr-<env>/migration-database-url`: direct URL Alembic uses
- `redactldr-<env>/clerk-jwks-url`
- `redactldr-<env>/clerk-issuer-url`

Copy these outputs into GitHub repository variables:

| Variable | Output |
|---|---|
| `AWS_ROLE_ARN` | `github_deploy_role_arn` |
| `AWS_REGION` | `us-east-1` |
| `ECR_API` | `api_repository_url` |
| `ECR_WORKER` | `worker_repository_url` |
| `ECS_CLUSTER` | `ecs_cluster_name` |
| `ECS_API_SERVICE` | `api_service_name` |
| `ECS_WORKER_SERVICE` | `worker_service_name` |
| `ECS_BEAT_SERVICE` | `beat_service_name` |
| `ECS_MIGRATE_TASK` | `migrate_task_definition` |
| `ECS_SUBNETS` | `private_subnet_ids` joined with commas |
| `ECS_SECURITY_GROUP` | `api_security_group_id` |
| `API_HEALTH_URL` | `http://<alb_dns_name>/v1/health`, or `https://api.<domain>/v1/health` once DNS exists |

The GitHub OIDC provider is one per AWS account. A second environment in the same account sets `create_github_oidc_provider = false`.

The task definitions use the `:latest` tag, so the services become healthy after the first deploy workflow pushes an image.

## What a push to main does

`.github/workflows/deploy.yml` runs after the CI workflow passes on a push to `main` (or by hand), and is skipped until the repository variable `AWS_ROLE_ARN` is set. When it runs:

1. Assume the deploy role with GitHub OIDC (no long-lived AWS keys).
2. Build the API and worker images, tag them with the git SHA and `latest`, push to ECR.
3. Write an SBOM and fail on a CRITICAL Trivy finding in the API image.
4. Run `alembic upgrade head` as a one-off ECS task (`redactldr-<env>-migrate`).
5. Force a new deployment of the API, worker, and beat services.
6. Wait until they are stable, then `curl` `/v1/health`.

ECS keeps 100% of the old tasks until the new ones pass the load balancer health check, and the circuit breaker rolls a failed deployment back. Migrations run before the new tasks start, so keep them backward compatible with the tasks still running.

## Web (Vercel)

Connect the repo in Vercel with `main` as the production branch. Set, for production and preview:

- `NEXT_PUBLIC_API_URL`: `https://api.<domain>` (or the load balancer URL until the domain exists)
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` from the Clerk production instance
- `CLERK_JWT_TEMPLATE`: `redactldr-api`
- `AWS_REGION`: `us-east-1` (the upload CSP allows that region's S3 host)

Add the Vercel origins to `s3_browser_allowed_origins` and to the API `CORS_ALLOWED_ORIGINS`. The Clerk production instance needs the JWT template `redactldr-api` with audience `redactldr-api`.

## Rollback

```bash
aws ecs update-service --cluster "$ECS_CLUSTER" --service "$ECS_API_SERVICE" \
  --task-definition redactldr-dev-api:<previous-revision>
aws ecs wait services-stable --cluster "$ECS_CLUSTER" --services "$ECS_API_SERVICE"
```

Do the same for the worker and beat. A migration that already ran is not reversed by this; write a down migration only when it is safe to undo, and run it as a one-off task.

## Rotate secrets

Put a new value on the secret, then force a new deployment of the API, worker, and beat so the tasks read it.

## Traces

The API adds a W3C `traceparent` to every Celery message and the worker span continues that trace. Botocore spans (S3, Textract, Comprehend, Bedrock) attach under it, and an ADOT sidecar exports them to X-Ray. With `LOG_JSON=true` (set in the task definitions) logs carry `trace_id`, `document_id`, and `job_id`.
