output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "s3_originals_bucket" {
  value = aws_s3_bucket.originals.bucket
}

output "s3_downloads_bucket" {
  value = aws_s3_bucket.downloads.bucket
}
