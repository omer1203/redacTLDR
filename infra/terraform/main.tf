# Baseline infrastructure scaffold for AWS deployment direction.
terraform {
  # Pin Terraform and provider versions for reproducible plans.
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  # Region selected via input variable (see variables.tf).
  region = var.aws_region
}

locals {
  # Shared naming prefix for environment-specific resource separation.
  name_prefix = "redactldr-${var.environment}"
}

resource "aws_s3_bucket" "originals" {
  # Stores uploaded source/original documents.
  bucket = "${local.name_prefix}-originals"
}

resource "aws_s3_bucket" "downloads" {
  # Stores generated export artifacts for client download.
  bucket = "${local.name_prefix}-downloads"
}

resource "aws_s3_bucket_public_access_block" "originals" {
  bucket = aws_s3_bucket.originals.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "downloads" {
  bucket = aws_s3_bucket.downloads.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "originals" {
  bucket = aws_s3_bucket.originals.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "downloads" {
  bucket = aws_s3_bucket.downloads.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_cors_configuration" "originals" {
  bucket = aws_s3_bucket.originals.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "GET", "HEAD"]
    allowed_origins = var.s3_browser_allowed_origins
    expose_headers  = ["ETag"]
    max_age_seconds = 3600
  }
}

resource "aws_s3_bucket_cors_configuration" "downloads" {
  bucket = aws_s3_bucket.downloads.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = var.s3_browser_allowed_origins
    expose_headers  = ["ETag"]
    max_age_seconds = 3600
  }
}

resource "aws_ecr_repository" "api" {
  # Container image repository for API service.
  name                 = "${local.name_prefix}-api"
  image_tag_mutability = "MUTABLE"
}

resource "aws_ecr_repository" "worker" {
  # Container image repository for worker service.
  name                 = "${local.name_prefix}-worker"
  image_tag_mutability = "MUTABLE"
}

resource "aws_ecr_repository" "web" {
  # Container image repository for web frontend.
  name                 = "${local.name_prefix}-web"
  image_tag_mutability = "MUTABLE"
}

resource "aws_ecs_cluster" "main" {
  # Compute cluster placeholder for running services via ECS.
  name = "${local.name_prefix}-cluster"
}
