output "originals_bucket" { value = aws_s3_bucket.originals.bucket }
output "downloads_bucket" { value = aws_s3_bucket.downloads.bucket }
output "originals_arn" { value = aws_s3_bucket.originals.arn }
output "downloads_arn" { value = aws_s3_bucket.downloads.arn }
output "kms_key_arn" { value = aws_kms_key.documents.arn }
