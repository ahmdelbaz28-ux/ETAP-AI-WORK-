variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "vnet_name" {
  type = string
}

variable "vnet_address_space" {
  type = list(string)
}

variable "subnet_configs" {
  type = map(object({
    address_prefixes     = list(string)
    service_endpoints    = optional(list(string))
    private_link_service = optional(bool, false)
    delegation = optional(object({
      name = string
      service_delegation = object({
        name    = string
        actions = optional(list(string))
      })
    }))
  }))
}

variable "private_dns_zones" {
  type = map(object({
    name                 = string
    registration_enabled = optional(bool, false)
    virtual_network_id   = optional(string)
  }))
}

variable "tags" {
  type    = map(string)
  default = {}
}
