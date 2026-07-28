variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "cluster_name" {
  type = string
}

variable "kubernetes_version" {
  type = string
}

variable "sku_tier" {
  type = string
}

variable "system_node_pool" {
  type = object({
    name                = string
    vm_size             = string
    min_count           = number
    max_count           = number
    enable_auto_scaling = bool
    availability_zones  = optional(list(string))
    os_disk_size_gb     = optional(number)
    max_pods            = optional(number)
  })
}

variable "user_node_pools" {
  type = map(object({
    vm_size             = string
    min_count           = number
    max_count           = number
    enable_auto_scaling = bool
    availability_zones  = optional(list(string))
    os_disk_size_gb     = optional(number)
    node_taints         = optional(list(string))
    max_pods            = optional(number)
    node_labels         = optional(map(string))
  }))
}

variable "subnet_id" {
  type = string
}

variable "log_analytics_workspace_id" {
  type = string
}

variable "acr_id" {
  type    = string
  default = null
}

variable "network_profile" {
  type = object({
    network_plugin     = string
    network_policy     = string
    network_data_plane = optional(string)
    service_cidr       = optional(string)
    dns_service_ip     = optional(string)
    outbound_type      = optional(string)
    load_balancer_sku  = string
  })
}

variable "tags" {
  type    = map(string)
  default = {}
}
