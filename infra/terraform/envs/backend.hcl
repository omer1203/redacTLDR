bucket         = "redactldr-terraform-state"
key            = "redactldr/dev/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "redactldr-terraform-lock"
encrypt        = true
