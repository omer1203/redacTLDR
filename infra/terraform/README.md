# Terraform (AWS ECS/Fargate Primary Path)

This module scaffolds the primary deployment path:

- ECR repositories (`api`, `worker`, `web`)
- ECS cluster
- Fargate services for API and worker
- S3 buckets for originals/downloads (default encryption, block public access, browser CORS for presigned uploads)
- IAM task roles

## Usage

1. Copy `terraform.tfvars.example` to `terraform.tfvars`.
2. Fill required variables.
3. Run:
   - `terraform init`
   - `terraform plan`
   - `terraform apply`

From the repository root, for buckets created outside Terraform (for example `redactldr-originals-dev`):

`bash scripts/apply-s3-cors.sh`

Buckets managed here use `var.s3_browser_allowed_origins`; extend that list before production deploys.

This scaffold is intentionally concise and should be extended with:

- VPC/subnet/security group details
- Secrets Manager integration
- ALB + TLS cert
- autoscaling and alarms
