# Terraform (AWS ECS/Fargate Primary Path)

This module scaffolds the primary deployment path:

- ECR repositories (`api`, `worker`, `web`)
- ECS cluster
- Fargate services for API and worker
- S3 buckets for originals/downloads
- IAM task roles

## Usage

1. Copy `terraform.tfvars.example` to `terraform.tfvars`.
2. Fill required variables.
3. Run:
   - `terraform init`
   - `terraform plan`
   - `terraform apply`

This scaffold is intentionally concise and should be extended with:

- VPC/subnet/security group details
- Secrets Manager integration
- ALB + TLS cert
- autoscaling and alarms
