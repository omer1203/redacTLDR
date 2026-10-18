variable "name_prefix" { type = string }
variable "alb_arn_suffix" { type = string }
variable "target_group_arn_suffix" { type = string }
variable "aws_region" { type = string }

resource "aws_cloudwatch_log_group" "api" {
  name              = "/redactldr/${var.name_prefix}/api"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/redactldr/${var.name_prefix}/worker"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_metric_filter" "job_failures" {
  name           = "${var.name_prefix}-job-failures"
  log_group_name = aws_cloudwatch_log_group.worker.name
  pattern        = "{ $.message = \"*failed*\" }"
  metric_transformation {
    name      = "JobFailures"
    namespace = "RedacTLDR"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${var.name_prefix}-api-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"
  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = var.target_group_arn_suffix
  }
}

resource "aws_cloudwatch_metric_alarm" "queue_depth" {
  alarm_name          = "${var.name_prefix}-queue-depth"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "QueueDepth"
  namespace           = "RedacTLDR"
  period              = 60
  statistic           = "Average"
  threshold           = 50
  treat_missing_data  = "notBreaching"
  dimensions          = { QueueName = "default" }
}

resource "aws_cloudwatch_metric_alarm" "job_failures" {
  alarm_name          = "${var.name_prefix}-job-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "JobFailures"
  namespace           = "RedacTLDR"
  period              = 300
  statistic           = "Sum"
  threshold           = 3
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = var.name_prefix
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          title  = "API 5xx"
          region = var.aws_region
          metrics = [
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", var.alb_arn_suffix],
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title   = "Queue depth"
          region  = var.aws_region
          metrics = [["RedacTLDR", "QueueDepth", "QueueName", "default"]]
        }
      },
      {
        type = "metric"
        properties = {
          title   = "Job failures"
          region  = var.aws_region
          metrics = [["RedacTLDR", "JobFailures"]]
        }
      },
      {
        type = "metric"
        properties = {
          title   = "Stage seconds"
          region  = var.aws_region
          metrics = [["RedacTLDR", "StageSeconds", "Stage", "ocr"], [".", ".", ".", "detect"], [".", ".", ".", "export"], [".", ".", ".", "summary"]]
        }
      },
    ]
  })
}

output "api_log_group" { value = aws_cloudwatch_log_group.api.name }
output "worker_log_group" { value = aws_cloudwatch_log_group.worker.name }
