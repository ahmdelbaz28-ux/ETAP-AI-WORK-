variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "key_vault_name" {
  type = string
}

variable "acr_name" {
  type = string
}

variable "tenant_id" {
  type = string
}

variable "deployer_object_id" {
  description = "Azure AD object ID of the deploying user (for Key Vault access)"
  type        = string
  default     = null
}

variable "tags" {
  type    = map(string)
  default = {}
}
