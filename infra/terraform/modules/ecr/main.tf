variable "name_prefix" { type = string }

resource "aws_ecr_repository" "api" {
  name                 = "${var.name_prefix}-api"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration { scan_on_push = true }
}

resource "aws_ecr_repository" "worker" {
  name                 = "${var.name_prefix}-worker"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration { scan_on_push = true }
}

output "api_url" { value = aws_ecr_repository.api.repository_url }
output "worker_url" { value = aws_ecr_repository.worker.repository_url }
output "api_arn" { value = aws_ecr_repository.api.arn }
output "worker_arn" { value = aws_ecr_repository.worker.arn }
