terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # Bucket and lock table are created by infra/terraform/bootstrap (local state).
  # terraform init -backend-config=envs/backend.hcl
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region
}
