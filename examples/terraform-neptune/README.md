# terraform-neptune

Disposable Amazon Neptune test environment for `dbt-graph-bridge`.

This Terraform example creates:

- A small VPC with two public subnets
- Security groups for Neptune and a client EC2 instance
- An Amazon Neptune cluster with IAM database authentication disabled
- One Neptune instance
- One Amazon Linux client EC2 instance reachable through SSM Session Manager
  with a 30 GiB encrypted gp3 root volume

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

To change the client EC2 root volume size:

```bash
terraform apply -var="client_root_volume_size=50"
```

After apply, connect to the client instance:

```bash
terraform output -raw neptune_opencypher_url

aws ssm start-session \
  --region "$(terraform output -raw aws_region)" \
  --target "$(terraform output -raw client_instance_id)"
```

Inside the session, test Neptune openCypher:

```bash
curl -X POST "https://<neptune-endpoint>:8182/openCypher" \
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
