variable "aws_region" {
  description = "AWS region for the test environment."
  type        = string
  default     = "ap-northeast-1"
}

variable "name_prefix" {
  description = "Prefix for created resource names."
  type        = string
  default     = "graphbridge-test"
}

variable "vpc_cidr" {
  description = "CIDR block for the test VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "Two subnet CIDRs used by Neptune and the client EC2 instance."
  type        = list(string)
  default     = ["10.42.1.0/24", "10.42.2.0/24"]

  validation {
    condition     = length(var.public_subnet_cidrs) >= 2
    error_message = "At least two subnet CIDRs are required for Neptune."
  }
}

variable "neptune_instance_class" {
  description = "Neptune instance class. Keep this small for disposable tests."
  type        = string
  default     = "db.t4g.medium"
}

variable "client_instance_type" {
  description = "EC2 instance type for the SSM client host."
  type        = string
  default     = "t3.micro"
}

variable "client_root_volume_size" {
  description = "Root EBS volume size in GiB for the SSM client host."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Additional tags for all resources."
  type        = map(string)
  default     = {}
}
