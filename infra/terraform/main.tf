locals {
  name_prefix = "redactldr-${var.environment}"
  enable_dns  = var.domain_name != "" && var.route53_zone_id != ""
}

module "network" {
  source      = "./modules/network"
  name_prefix = local.name_prefix
  vpc_cidr    = var.vpc_cidr
}

module "storage" {
  source          = "./modules/storage"
  name_prefix     = local.name_prefix
  allowed_origins = var.s3_browser_allowed_origins
}

module "ecr" {
  source      = "./modules/ecr"
  name_prefix = local.name_prefix
}

module "secrets" {
  source      = "./modules/secrets"
  name_prefix = local.name_prefix
}

module "iam" {
  source                      = "./modules/iam"
  name_prefix                 = local.name_prefix
  originals_bucket_arn        = module.storage.originals_arn
  downloads_bucket_arn        = module.storage.downloads_arn
  kms_key_arn                 = module.storage.kms_key_arn
  secret_arns                 = module.secrets.arns
  github_repository           = var.github_repository
  create_github_oidc_provider = var.create_github_oidc_provider
}

module "elasticache" {
  source            = "./modules/elasticache"
  name_prefix       = local.name_prefix
  subnet_ids        = module.network.private_subnet_ids
  security_group_id = module.network.redis_security_group_id
}

module "alb" {
  source            = "./modules/alb"
  name_prefix       = local.name_prefix
  vpc_id            = module.network.vpc_id
  public_subnet_ids = module.network.public_subnet_ids
  security_group_id = module.network.alb_security_group_id
  domain_name       = var.domain_name
  route53_zone_id   = var.route53_zone_id
  enable_dns        = local.enable_dns
}

module "ecs" {
  source                   = "./modules/ecs"
  name_prefix              = local.name_prefix
  aws_region               = var.aws_region
  environment              = var.environment
  image_tag                = var.image_tag
  api_image                = module.ecr.api_url
  worker_image             = module.ecr.worker_url
  private_subnet_ids       = module.network.private_subnet_ids
  api_security_group_id    = module.network.api_security_group_id
  worker_security_group_id = module.network.worker_security_group_id
  target_group_arn         = module.alb.target_group_arn
  execution_role_arn       = module.iam.execution_role_arn
  api_task_role_arn        = module.iam.api_task_role_arn
  worker_task_role_arn     = module.iam.worker_task_role_arn
  secret_arns              = module.secrets.arns
  originals_bucket         = module.storage.originals_bucket
  downloads_bucket         = module.storage.downloads_bucket
  redis_url                = module.elasticache.redis_url
  api_desired_count        = var.api_desired_count
  worker_min_count         = var.worker_min_count
  worker_max_count         = var.worker_max_count
  log_group_api            = module.observability.api_log_group
  log_group_worker         = module.observability.worker_log_group
  cors_allowed_origins     = join(",", var.s3_browser_allowed_origins)
  bedrock_model_id         = var.bedrock_model_id
}

module "observability" {
  source                  = "./modules/observability"
  name_prefix             = local.name_prefix
  alb_arn_suffix          = module.alb.arn_suffix
  target_group_arn_suffix = module.alb.target_group_arn_suffix
  aws_region              = var.aws_region
}
