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

variable "acr_public_network_access_enabled" {
  description = "Whether public network access is allowed for the ACR. Defaults to false (private-endpoint only) to satisfy SonarCloud S6329. Set to true only for break-glass maintenance in non-prod."
  type        = bool
  default     = false
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
