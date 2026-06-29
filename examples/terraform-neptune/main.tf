locals {
  tags = merge(
    {
      Project   = "dbt-graph-bridge"
      Example   = "terraform-neptune"
      ManagedBy = "terraform"
    },
    var.tags,
  )
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.tags, {
    Name = "${var.name_prefix}-vpc"
  })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = merge(local.tags, {
    Name = "${var.name_prefix}-igw"
  })
}

resource "aws_subnet" "public" {
  count = length(var.public_subnet_cidrs)

  vpc_id                  = aws_vpc.this.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = merge(local.tags, {
    Name = "${var.name_prefix}-public-${count.index + 1}"
  })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = merge(local.tags, {
    Name = "${var.name_prefix}-public"
  })
}

resource "aws_route_table_association" "public" {
  count = length(aws_subnet.public)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "client" {
  name        = "${var.name_prefix}-client"
  description = "Client host egress for Neptune tests"
  vpc_id      = aws_vpc.this.id

  egress {
    description = "Allow outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, {
    Name = "${var.name_prefix}-client"
  })
}

resource "aws_security_group" "neptune" {
  name        = "${var.name_prefix}-neptune"
  description = "Neptune openCypher access from the client host"
  vpc_id      = aws_vpc.this.id

  ingress {
    description     = "openCypher from client"
    from_port       = 8182
    to_port         = 8182
    protocol        = "tcp"
    security_groups = [aws_security_group.client.id]
  }

  egress {
    description = "Allow outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, {
    Name = "${var.name_prefix}-neptune"
  })
}

resource "aws_neptune_subnet_group" "this" {
  name       = var.name_prefix
  subnet_ids = aws_subnet.public[*].id

  tags = merge(local.tags, {
    Name = var.name_prefix
  })
}

resource "aws_neptune_cluster" "this" {
  cluster_identifier                  = var.name_prefix
  engine                              = "neptune"
  port                                = 8182
  neptune_subnet_group_name           = aws_neptune_subnet_group.this.name
  vpc_security_group_ids              = [aws_security_group.neptune.id]
  iam_database_authentication_enabled = false
  storage_encrypted                   = true
  backup_retention_period             = 1
  skip_final_snapshot                 = true
  deletion_protection                 = false
  apply_immediately                   = true

  tags = merge(local.tags, {
    Name = var.name_prefix
  })
}

resource "aws_neptune_cluster_instance" "this" {
  identifier         = "${var.name_prefix}-1"
  cluster_identifier = aws_neptune_cluster.this.id
  engine             = "neptune"
  instance_class     = var.neptune_instance_class
  apply_immediately  = true

  tags = merge(local.tags, {
    Name = "${var.name_prefix}-1"
  })
}

resource "aws_iam_role" "client" {
  name = "${var.name_prefix}-client"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.client.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "client" {
  name = "${var.name_prefix}-client"
  role = aws_iam_role.client.name
}

resource "aws_instance" "client" {
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = var.client_instance_type
  subnet_id                   = aws_subnet.public[0].id
  vpc_security_group_ids      = [aws_security_group.client.id]
  iam_instance_profile        = aws_iam_instance_profile.client.name
  associate_public_ip_address = true

  user_data = <<-USER_DATA
    #!/bin/bash
    set -euxo pipefail
    dnf install -y amazon-ssm-agent git jq python3 python3-pip
    systemctl enable --now amazon-ssm-agent
    python3 -m pip install --upgrade pip
    python3 -m pip install uv
  USER_DATA

  user_data_replace_on_change = true

  root_block_device {
    volume_size           = var.client_root_volume_size
    volume_type           = "gp3"
    delete_on_termination = true
    encrypted             = true
  }

  depends_on = [
    aws_iam_role_policy_attachment.ssm,
  ]

  tags = merge(local.tags, {
    Name = "${var.name_prefix}-client"
  })
}

resource "aws_iam_role" "notebook" {
  count = var.create_neptune_notebook ? 1 : 0

  name = "${var.name_prefix}-notebook"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "sagemaker.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "notebook_sagemaker" {
  count = var.create_neptune_notebook ? 1 : 0

  role       = aws_iam_role.notebook[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

resource "aws_sagemaker_notebook_instance_lifecycle_configuration" "neptune" {
  count = var.create_neptune_notebook ? 1 : 0

  name = "${var.name_prefix}-neptune-notebook"

  on_start = base64encode(templatefile("${path.module}/notebook-on-start.sh.tftpl", {
    neptune_endpoint = aws_neptune_cluster.this.endpoint
    neptune_port     = aws_neptune_cluster.this.port
    aws_region       = var.aws_region
  }))
}

resource "aws_sagemaker_notebook_instance" "neptune" {
  count = var.create_neptune_notebook ? 1 : 0

  name                   = "${var.name_prefix}-notebook"
  role_arn               = aws_iam_role.notebook[0].arn
  instance_type          = var.notebook_instance_type
  subnet_id              = aws_subnet.public[0].id
  security_groups        = [aws_security_group.client.id]
  lifecycle_config_name  = aws_sagemaker_notebook_instance_lifecycle_configuration.neptune[0].name
  direct_internet_access = "Enabled"
  root_access            = "Enabled"
  volume_size            = var.notebook_volume_size

  depends_on = [
    aws_iam_role_policy_attachment.notebook_sagemaker,
    aws_neptune_cluster_instance.this,
  ]

  tags = merge(local.tags, {
    Name = "${var.name_prefix}-notebook"
  })
}
