aws_region  = "us-east-1"
environment = "prod"
# Fill these before apply. DNS stays off until both are set.
domain_name                = ""
route53_zone_id            = ""
s3_browser_allowed_origins = ["https://app.example.com"]
github_repository          = "omer1203/redacTLDR"
# The dev environment creates the account-wide GitHub OIDC provider.
create_github_oidc_provider = false
api_desired_count           = 2
worker_min_count            = 1
worker_max_count            = 4
