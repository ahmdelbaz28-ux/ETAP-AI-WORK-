variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "workspace_name" {
  type = string
}

variable "workspace_id" {
  description = "ID of an existing Log Analytics workspace (created in root module)"
  type        = string
}

variable "retention_in_days" {
  type = number
}

variable "alert_emails" {
  type    = list(string)
  default = []
}

variable "aks_cluster_id" {
  type    = string
  default = null
}

variable "tags" {
  type    = map(string)
  default = {}
}
