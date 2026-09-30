variable "aws_region" {
  description = "AWS region for deployment."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "staging"
}

variable "s3_browser_allowed_origins" {
  description = "Browser origins allowed for presigned S3 PUT/GET (bucket CORS). Include every frontend URL users upload or download from."
  type        = list(string)
  default = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
  ]
}
