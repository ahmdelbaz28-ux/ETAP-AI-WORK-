# =============================================================================
# AhmedETAP — Main Terraform Configuration
# =============================================================================
# This is the root module that orchestrates all infrastructure modules for
# deploying the AhmedETAP engineering platform on Azure.
#
# Usage:
#   terraform init
#   terraform plan -var-file="environments/dev/terraform.tfvars"
#   terraform apply -var-file="environments/dev/terraform.tfvars"
# =============================================================================

# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------
data "azurerm_client_config" "current" {}

# ---------------------------------------------------------------------------
# Resource Group
# ---------------------------------------------------------------------------
resource "azurerm_resource_group" "this" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------
module "networking" {
  source = "./modules/networking"

  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  vnet_name           = var.vnet_name
  vnet_address_space  = var.vnet_address_space
  subnet_configs      = var.subnet_configs
  private_dns_zones   = var.private_dns_zones
  tags                = var.tags
}

# ---------------------------------------------------------------------------
# PostgreSQL Database
# ---------------------------------------------------------------------------
module "database" {
  source = "./modules/database"

  resource_group_name    = azurerm_resource_group.this.name
  location               = azurerm_resource_group.this.location
  server_name            = var.postgresql_server_name
  database_name          = var.postgresql_database_name
  admin_login            = var.postgresql_admin_login
  admin_password         = var.postgresql_admin_password
  sku_name               = var.postgresql_sku_name
  storage_mb             = var.postgresql_storage_mb
  backup_retention_days  = var.postgresql_backup_retention_days
  geo_redundant_backup   = var.postgresql_geo_redundant_backup
  zone_high_availability = var.postgresql_zone_high_availability
  delegated_subnet_id    = module.networking.postgresql_subnet_id
  private_dns_zone_id    = module.networking.postgresql_private_dns_zone_id
  tags                   = var.tags

  depends_on = [module.networking]
}

# ---------------------------------------------------------------------------
# Redis Cache
# ---------------------------------------------------------------------------
module "redis" {
  source = "./modules/redis"

  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  cache_name          = var.redis_cache_name
  sku_name            = var.redis_sku_name
  family              = var.redis_family
  capacity            = var.redis_capacity
  enable_non_ssl_port = var.redis_enable_non_ssl_port
  shard_count         = var.redis_shard_count
  redis_version       = var.redis_version
  subnet_id           = module.networking.redis_subnet_id
  private_dns_zone_id = module.networking.redis_private_dns_zone_id
  tags                = var.tags

  depends_on = [module.networking]
}

# ---------------------------------------------------------------------------
# Log Analytics Workspace (standalone — needed by both AKS and monitoring)
# ---------------------------------------------------------------------------
resource "azurerm_log_analytics_workspace" "this" {
  name                       = var.log_analytics_workspace_name
  location                   = azurerm_resource_group.this.location
  resource_group_name        = azurerm_resource_group.this.name
  sku                        = "PerGB2018"
  retention_in_days          = var.log_analytics_retention_days
  internet_ingestion_enabled = true
  internet_query_enabled     = true
  tags                       = var.tags

  depends_on = [azurerm_resource_group.this]
}

# ---------------------------------------------------------------------------
# Security (Key Vault, Managed Identities, ACR)
# ---------------------------------------------------------------------------
module "security" {
  source = "./modules/security"

  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  key_vault_name      = var.key_vault_name
  acr_name            = var.acr_name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  deployer_object_id  = var.deployer_object_id != "" ? var.deployer_object_id : data.azurerm_client_config.current.object_id
  tags                = var.tags

  depends_on = [module.networking]
}

# ---------------------------------------------------------------------------
# AKS Cluster
# ---------------------------------------------------------------------------
module "aks" {
  source = "./modules/aks"

  resource_group_name        = azurerm_resource_group.this.name
  location                   = azurerm_resource_group.this.location
  cluster_name               = var.aks_cluster_name
  kubernetes_version         = var.kubernetes_version
  sku_tier                   = var.aks_sku_tier
  system_node_pool           = var.aks_system_node_pool
  user_node_pools            = var.aks_user_node_pools
  subnet_id                  = module.networking.aks_subnet_id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
  acr_id                     = module.security.acr_id
  network_profile            = var.aks_network_profile
  tags                       = var.tags

  depends_on = [
    module.networking,
    module.security,
  ]
}

# ---------------------------------------------------------------------------
# Monitoring (Alerts, Diagnostics — depends on AKS being created)
# ---------------------------------------------------------------------------
module "monitoring" {
  source = "./modules/monitoring"

  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  workspace_name      = var.log_analytics_workspace_name
  workspace_id        = azurerm_log_analytics_workspace.this.id
  retention_in_days   = var.log_analytics_retention_days
  alert_emails        = var.alert_emails
  aks_cluster_id      = module.aks.cluster_id
  tags                = var.tags

  depends_on = [module.aks]
}

# ---------------------------------------------------------------------------
# Helm Release (Deploy the AhmedETAP Helm Chart onto AKS)
# ---------------------------------------------------------------------------
resource "helm_release" "etap_ai" {
  count = var.deploy_helm_chart ? 1 : 0

  name             = var.helm_release_name
  repository       = var.helm_chart_repository
  chart            = var.helm_chart_name
  version          = var.helm_chart_version
  namespace        = var.helm_namespace
  create_namespace = true
  timeout          = 600

  values = [
    templatefile("${path.module}/helm-values.yaml", {
      # Docker image settings
      image_registry = module.security.acr_login_server
      image_tag      = var.helm_image_tag

      # Database
      postgresql_host     = module.database.fqdn
      postgresql_port     = 5432
      postgresql_database = module.database.database_name
      postgresql_user     = module.database.admin_login
      postgresql_password = module.database.admin_password

      # Redis
      redis_host     = module.redis.hostname
      redis_port     = 6380
      redis_password = module.redis.primary_access_key

      # Ingress
      ingress_domain = var.ingress_domain
      ingress_tls    = var.ingress_tls_enabled

      # Resource limits
      environment = var.environment
    })
  ]

  depends_on = [
    module.aks,
    module.database,
    module.redis,
  ]
}

# ---------------------------------------------------------------------------
# GitHub Actions OIDC Federated Credential (optional)
# ---------------------------------------------------------------------------
resource "azurerm_federated_identity_credential" "github_actions" {
  count = var.github_actions_oidc_enabled ? 1 : 0

  name                = "${var.aks_cluster_name}-github-actions"
  resource_group_name = azurerm_resource_group.this.name
  audience            = ["api://AzureADTokenExchange"]
  issuer              = "https://token.actions.githubusercontent.com"
  parent_id           = module.security.aks_identity_id
  subject             = "repo:${var.github_repository}:environment:${var.environment}"
}
