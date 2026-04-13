terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  name_prefix = "redactldr-${var.environment}"
}

resource "aws_s3_bucket" "originals" {
  bucket = "${local.name_prefix}-originals"
}

resource "aws_s3_bucket" "downloads" {
  bucket = "${local.name_prefix}-downloads"
}

resource "aws_ecr_repository" "api" {
  name                 = "${local.name_prefix}-api"
  image_tag_mutability = "MUTABLE"
}

resource "aws_ecr_repository" "worker" {
  name                 = "${local.name_prefix}-worker"
  image_tag_mutability = "MUTABLE"
}

resource "aws_ecr_repository" "web" {
  name                 = "${local.name_prefix}-web"
  image_tag_mutability = "MUTABLE"
}

resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"
}
