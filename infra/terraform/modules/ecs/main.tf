variable "name_prefix" { type = string }
variable "aws_region" { type = string }
variable "environment" { type = string }
variable "image_tag" { type = string }
variable "api_image" { type = string }
variable "worker_image" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "api_security_group_id" { type = string }
variable "worker_security_group_id" { type = string }
variable "target_group_arn" { type = string }
variable "execution_role_arn" { type = string }
variable "api_task_role_arn" { type = string }
variable "worker_task_role_arn" { type = string }
variable "secret_arns" { type = map(string) }
variable "originals_bucket" { type = string }
variable "downloads_bucket" { type = string }
variable "redis_url" { type = string }
variable "api_desired_count" { type = number }
variable "worker_min_count" { type = number }
variable "worker_max_count" { type = number }
variable "log_group_api" { type = string }
variable "log_group_worker" { type = string }
variable "cors_allowed_origins" { type = string }
variable "bedrock_model_id" { type = string }

locals {
  adot_config = <<-YAML
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
    processors:
      batch:
    exporters:
      awsxray:
        region: ${var.aws_region}
    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [batch]
          exporters: [awsxray]
  YAML
  adot_image  = "public.ecr.aws/aws-observability/aws-otel-collector:v0.43.0"
}

resource "aws_ecs_cluster" "main" {
  name = "${var.name_prefix}-cluster"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

locals {
  api_secrets = [
    { name = "DATABASE_URL", valueFrom = var.secret_arns["database-url"] },
    { name = "CLERK_JWKS_URL", valueFrom = var.secret_arns["clerk-jwks-url"] },
    { name = "CLERK_ISSUER_URL", valueFrom = var.secret_arns["clerk-issuer-url"] },
  ]
  app_env = [
    { name = "ENVIRONMENT", value = var.environment },
    { name = "AWS_REGION", value = var.aws_region },
    { name = "S3_BUCKET_ORIGINALS", value = var.originals_bucket },
    { name = "S3_BUCKET_DOWNLOADS", value = var.downloads_bucket },
    { name = "CELERY_BROKER_URL", value = var.redis_url },
    { name = "CELERY_BACKEND_URL", value = "${replace(var.redis_url, "/0", "/1")}" },
    { name = "LOG_JSON", value = "true" },
    { name = "OTEL_EXPORTER_OTLP_ENDPOINT", value = "http://127.0.0.1:4317" },
    { name = "CLOUDWATCH_METRICS_NAMESPACE", value = "RedacTLDR" },
    { name = "BEDROCK_MODEL_ID", value = var.bedrock_model_id },
  ]
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name_prefix}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.api_task_role_arn
  container_definitions = jsonencode([
    {
      name         = "api"
      image        = "${var.api_image}:${var.image_tag}"
      essential    = true
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]
      environment = concat(local.app_env, [
        { name = "OTEL_SERVICE_NAME", value = "redactldr-api" },
        { name = "CLERK_AUDIENCE", value = "redactldr-api" },
        { name = "CORS_ALLOWED_ORIGINS", value = var.cors_allowed_origins },
      ])
      secrets = local.api_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = var.log_group_api
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "api"
        }
      }
      dependsOn = [{ containerName = "adot", condition = "START" }]
    },
    {
      name      = "adot"
      image     = local.adot_image
      essential = false
      command   = ["--config=env:AOT_CONFIG_CONTENT"]
      environment = [
        { name = "AOT_CONFIG_CONTENT", value = local.adot_config },
        { name = "AWS_REGION", value = var.aws_region },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = var.log_group_api
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "adot"
        }
      }
    },
  ])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.name_prefix}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.worker_task_role_arn
  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = "${var.worker_image}:${var.image_tag}"
      essential = true
      command   = ["celery", "-A", "services.worker.app.celery_app.celery", "worker", "-Q", "default,celery", "--loglevel=INFO", "--pool=solo", "--concurrency=1"]
      environment = concat(local.app_env, [
        { name = "OTEL_SERVICE_NAME", value = "redactldr-worker" },
      ])
      secrets = [
        { name = "DATABASE_URL", valueFrom = var.secret_arns["database-url"] },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = var.log_group_worker
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "worker"
        }
      }
      dependsOn = [{ containerName = "adot", condition = "START" }]
    },
    {
      name      = "adot"
      image     = local.adot_image
      essential = false
      command   = ["--config=env:AOT_CONFIG_CONTENT"]
      environment = [
        { name = "AOT_CONFIG_CONTENT", value = local.adot_config },
        { name = "AWS_REGION", value = var.aws_region },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = var.log_group_worker
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "adot"
        }
      }
    },
  ])
}

resource "aws_ecs_task_definition" "migrate" {
  family                   = "${var.name_prefix}-migrate"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.api_task_role_arn
  container_definitions = jsonencode([
    {
      name      = "migrate"
      image     = "${var.api_image}:${var.image_tag}"
      essential = true
      command   = ["alembic", "-c", "alembic.ini", "upgrade", "head"]
      environment = [
        { name = "ENVIRONMENT", value = var.environment },
      ]
      secrets = [
        { name = "MIGRATION_DATABASE_URL", valueFrom = var.secret_arns["migration-database-url"] },
        { name = "DATABASE_URL", valueFrom = var.secret_arns["database-url"] },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = var.log_group_api
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "migrate"
        }
      }
    },
  ])
}

resource "aws_ecs_service" "api" {
  name            = "${var.name_prefix}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"
  # A failed health check rolls back. The previous tasks keep serving.
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.api_security_group_id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = var.target_group_arn
    container_name   = "api"
    container_port   = 8000
  }
  lifecycle {
    ignore_changes = [task_definition, desired_count]
  }
}

resource "aws_ecs_service" "worker" {
  name                               = "${var.name_prefix}-worker"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.worker.arn
  desired_count                      = var.worker_min_count
  launch_type                        = "FARGATE"
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.worker_security_group_id]
    assign_public_ip = false
  }
  lifecycle {
    ignore_changes = [task_definition, desired_count]
  }
}

resource "aws_appautoscaling_target" "worker" {
  max_capacity       = var.worker_max_count
  min_capacity       = var.worker_min_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.worker.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "worker_queue" {
  name               = "${var.name_prefix}-queue-depth"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.worker.resource_id
  scalable_dimension = aws_appautoscaling_target.worker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker.service_namespace
  target_tracking_scaling_policy_configuration {
    target_value = 5
    customized_metric_specification {
      metric_name = "QueueDepth"
      namespace   = "RedacTLDR"
      statistic   = "Average"
      dimensions {
        name  = "QueueName"
        value = "default"
      }
    }
  }
}

resource "aws_ecs_task_definition" "beat" {
  family                   = "${var.name_prefix}-beat"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.worker_task_role_arn
  container_definitions = jsonencode([
    {
      name      = "beat"
      image     = "${var.worker_image}:${var.image_tag}"
      essential = true
      command   = ["celery", "-A", "services.worker.app.celery_app.celery", "beat", "--loglevel=INFO"]
      environment = concat(local.app_env, [
        { name = "OTEL_SERVICE_NAME", value = "redactldr-beat" },
      ])
      secrets = [
        { name = "DATABASE_URL", valueFrom = var.secret_arns["database-url"] },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = var.log_group_worker
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "beat"
        }
      }
    },
  ])
}

resource "aws_ecs_service" "beat" {
  name            = "${var.name_prefix}-beat"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.beat.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.worker_security_group_id]
    assign_public_ip = false
  }
  lifecycle {
    ignore_changes = [task_definition]
  }
}

output "cluster_name" { value = aws_ecs_cluster.main.name }
output "api_service_name" { value = aws_ecs_service.api.name }
output "worker_service_name" { value = aws_ecs_service.worker.name }
output "migrate_task_definition" { value = aws_ecs_task_definition.migrate.family }
output "beat_service_name" { value = aws_ecs_service.beat.name }
