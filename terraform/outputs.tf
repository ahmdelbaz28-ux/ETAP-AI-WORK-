# =============================================================================
# AhmedETAP — Terraform Outputs
# =============================================================================

output "resource_group_name" {
  description = "Name of the resource group"
  value       = azurerm_resource_group.this.name
}

output "resource_group_location" {
  description = "Location of the resource group"
  value       = azurerm_resource_group.this.location
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------
output "vnet_id" {
  description = "ID of the virtual network"
  value       = module.networking.vnet_id
}

output "vnet_name" {
  description = "Name of the virtual network"
  value       = module.networking.vnet_name
}

output "aks_subnet_id" {
  description = "Subnet ID for AKS"
  value       = module.networking.aks_subnet_id
}

output "postgresql_subnet_id" {
  description = "Subnet ID for PostgreSQL"
  value       = module.networking.postgresql_subnet_id
}

output "redis_subnet_id" {
  description = "Subnet ID for Redis"
  value       = module.networking.redis_subnet_id
}

# ---------------------------------------------------------------------------
# AKS
# ---------------------------------------------------------------------------
output "aks_cluster_name" {
  description = "Name of the AKS cluster"
  value       = module.aks.cluster_name
}

output "aks_cluster_id" {
  description = "ID of the AKS cluster"
  value       = module.aks.cluster_id
}

output "aks_kubeconfig" {
  description = "Kubeconfig for the AKS cluster"
  value       = module.aks.kubeconfig
  sensitive   = true
}

output "aks_host" {
  description = "AKS API server host"
  value       = module.aks.host
}

output "aks_identity_id" {
  description = "Principal ID of the AKS cluster identity"
  value       = module.aks.identity_principal_id
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
output "postgresql_fqdn" {
  description = "FQDN of the PostgreSQL server"
  value       = module.database.fqdn
}

output "postgresql_database_name" {
  description = "Name of the PostgreSQL database"
  value       = module.database.database_name
}

output "postgresql_connection_string" {
  description = "Connection string for PostgreSQL (sensitive)"
  value       = module.database.connection_string
  sensitive   = true
}

# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------
output "redis_hostname" {
  description = "Hostname of the Redis cache"
  value       = module.redis.hostname
}

output "redis_ssl_port" {
  description = "SSL port of the Redis cache"
  value       = module.redis.ssl_port
}

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
output "key_vault_id" {
  description = "ID of the Key Vault"
  value       = module.security.key_vault_id
}

output "key_vault_uri" {
  description = "URI of the Key Vault"
  value       = module.security.key_vault_uri
}

output "acr_login_server" {
  description = "ACR login server URL"
  value       = module.security.acr_login_server
}

output "acr_id" {
  description = "ID of the Azure Container Registry"
  value       = module.security.acr_id
}

# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------
output "log_analytics_workspace_id" {
  description = "ID of the Log Analytics workspace"
  value       = module.monitoring.log_analytics_workspace_id
}

output "log_analytics_workspace_name" {
  description = "Name of the Log Analytics workspace"
  value       = module.monitoring.log_analytics_workspace_name
}

# ---------------------------------------------------------------------------
# Helm
# ---------------------------------------------------------------------------
output "helm_release_name" {
  description = "Name of the Helm release"
  value       = var.deploy_helm_chart ? helm_release.etap_ai[0].name : null
}

output "helm_namespace" {
  description = "Kubernetes namespace of the Helm release"
  value       = var.deploy_helm_chart ? helm_release.etap_ai[0].namespace : null
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
output "deployment_summary" {
  description = "Summary of the deployment"
  value = {
    environment    = var.environment
    resource_group = azurerm_resource_group.this.name
    location       = azurerm_resource_group.this.location
    aks_cluster    = module.aks.cluster_name
    postgresql     = module.database.fqdn
    redis          = module.redis.hostname
    key_vault      = module.security.key_vault_uri
    acr            = module.security.acr_login_server
    log_analytics  = module.monitoring.log_analytics_workspace_name
    helm_namespace = var.deploy_helm_chart ? helm_release.etap_ai[0].namespace : "N/A (disabled)"
  }
}
