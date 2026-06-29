# terraform-neptune

Disposable Amazon Neptune test environment for `dbt-graph-bridge`.

This Terraform example creates:

- A small VPC with two public subnets
- Security groups for Neptune and a client EC2 instance
- An Amazon Neptune cluster with IAM database authentication disabled
- One Neptune instance
- One Amazon Linux client EC2 instance reachable through SSM Session Manager

The client EC2 instance is intended as the place to run dbt because Neptune
endpoints are VPC-private. This is a test-only setup and will create billable AWS
resources.

## Prerequisites

- Terraform
- AWS credentials configured for the target account
- Permission to create VPC, EC2, IAM, and Neptune resources
- Session Manager access for the generated EC2 instance

## Usage

```bash
cd examples/terraform-neptune
terraform init
terraform apply
```

After apply, connect to the client instance:

```bash
aws ssm start-session \
  --region "$(terraform output -raw aws_region)" \
  --target "$(terraform output -raw client_instance_id)"
```

Inside the session, test Neptune openCypher:

```bash
curl -X POST "$(terraform output -raw neptune_opencypher_url)" \
  -d "query=RETURN 1 AS ok"
```

For `dbt-graph-bridge`, use the output environment variables:

```bash
terraform output graphbridge_env
```

## Cleanup

```bash
terraform destroy
```

Destroy the environment when finished. Neptune and EC2 continue to incur cost
while running.
