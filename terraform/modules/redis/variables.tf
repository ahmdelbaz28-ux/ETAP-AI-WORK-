variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "cache_name" {
  type = string
}

variable "sku_name" {
  type = string
}

variable "family" {
  type = string
}

variable "capacity" {
  type = number
}

variable "enable_non_ssl_port" {
  type = bool
}

variable "shard_count" {
  type = number
}

variable "redis_version" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "private_dns_zone_id" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
