variable "aws_region" {
  description = "AWS region. Textract, Comprehend, and Bedrock must match the buckets."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Name prefix segment. Live dev buckets are not this state."
  type        = string
}

variable "s3_browser_allowed_origins" {
  description = "Browser origins for presigned S3 PUT/GET."
  type        = list(string)
  default     = ["http://localhost:3000"]
}

variable "domain_name" {
  description = "Apex domain. Empty skips Route 53 and ACM."
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "Existing public hosted zone. Empty skips DNS records."
  type        = string
  default     = ""
}

variable "image_tag" {
  description = "ECR tag the ECS services start from. Deploy overwrites this with the git SHA."
  type        = string
  default     = "latest"
}

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "worker_min_count" {
  type    = number
  default = 1
}

variable "worker_max_count" {
  type    = number
  default = 4
}

variable "bedrock_model_id" {
  description = "Bedrock model or inference profile the worker calls."
  type        = string
  default     = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "create_github_oidc_provider" {
  description = "Create the account-wide GitHub OIDC provider. Only one environment in an account should set this."
  type        = bool
  default     = true
}

variable "github_repository" {
  description = "GitHub repo allowed to assume the deploy role, owner/name."
  type        = string
  default     = "omer1203/redacTLDR"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}
