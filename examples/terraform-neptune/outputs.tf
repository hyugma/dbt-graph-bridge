output "aws_region" {
  description = "AWS region where resources were created."
  value       = var.aws_region
}

output "client_instance_id" {
  description = "EC2 instance ID for SSM Session Manager."
  value       = aws_instance.client.id
}

output "ssm_start_session_command" {
  description = "Command to open a shell on the client EC2 instance."
  value       = "aws ssm start-session --region ${var.aws_region} --target ${aws_instance.client.id}"
}

output "neptune_endpoint" {
  description = "Neptune cluster endpoint."
  value       = aws_neptune_cluster.this.endpoint
}

output "neptune_port" {
  description = "Neptune port."
  value       = aws_neptune_cluster.this.port
}

output "neptune_opencypher_url" {
  description = "HTTPS openCypher endpoint URL."
  value       = "https://${aws_neptune_cluster.this.endpoint}:${aws_neptune_cluster.this.port}/openCypher"
}

output "graphbridge_env" {
  description = "Environment variables for dbt-graph-bridge graph_engine: neptune."
  value = {
    DBT_GRAPHBRIDGE_GRAPH_SCHEME   = "https"
    DBT_GRAPHBRIDGE_GRAPH_HOST     = aws_neptune_cluster.this.endpoint
    DBT_GRAPHBRIDGE_GRAPH_PORT     = tostring(aws_neptune_cluster.this.port)
    DBT_GRAPHBRIDGE_GRAPH_DATABASE = ""
    DBT_GRAPHBRIDGE_GRAPH_USER     = ""
    DBT_GRAPHBRIDGE_GRAPH_PASSWORD = ""
  }
}

output "notebook_instance_name" {
  description = "SageMaker notebook instance name for Neptune visualization, when enabled."
  value       = var.create_neptune_notebook ? aws_sagemaker_notebook_instance.neptune[0].name : null
}

output "notebook_open_hint" {
  description = "Where to open the Neptune visualization notebook, when enabled."
  value       = var.create_neptune_notebook ? "Open SageMaker > Notebook instances > ${aws_sagemaker_notebook_instance.neptune[0].name}, then open SageMaker/graphbridge-neptune.ipynb." : null
}
