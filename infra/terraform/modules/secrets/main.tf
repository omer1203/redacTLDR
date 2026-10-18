variable "name_prefix" { type = string }

# Containers read the current version. Create that version after apply
# (see infra/terraform/README.md). Terraform does not store the URL or the keys.

locals {
  names = toset([
    "database-url",
    "migration-database-url",
    "clerk-jwks-url",
    "clerk-issuer-url",
  ])
}

resource "aws_secretsmanager_secret" "app" {
  for_each = local.names
  name     = "${var.name_prefix}/${each.key}"
}

output "arns" {
  value = { for key, secret in aws_secretsmanager_secret.app : key => secret.arn }
}
