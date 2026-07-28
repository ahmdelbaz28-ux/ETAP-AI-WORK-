# =============================================================================
# AhmedETAP — Staging Environment
# =============================================================================
# Pre-production environment with HA-like configuration but smaller scale.
# Mimics prod for validation before production release.
# =============================================================================

environment         = "staging"
location            = "eastus2"
resource_group_name = "rg-ahmedetap-staging"

tags = {
  managed_by  = "terraform"
  project     = "ahmedetap"
  environment = "staging"
}

# --- Networking ---
vnet_name          = "vnet-ahmedetap-staging"
vnet_address_space = ["10.1.0.0/16"]

# --- AKS ---
aks_cluster_name   = "aks-ahmedetap-staging"
kubernetes_version = "1.30"
aks_sku_tier       = "Standard"

aks_system_node_pool = {
  name                = "system"
  vm_size             = "Standard_D4s_v5"
  min_count           = 2
  max_count           = 4
  enable_auto_scaling = true
  availability_zones  = ["1", "2"]
  os_disk_size_gb     = 128
  max_pods            = 50
}

aks_user_node_pools = {
  services = {
    vm_size             = "Standard_D8s_v5"
    min_count           = 1
    max_count           = 5
    enable_auto_scaling = true
    availability_zones  = ["1", "2"]
    os_disk_size_gb     = 128
    max_pods            = 50
    node_labels         = { "nodepool-type" = "services" }
  }
}

# --- PostgreSQL ---
postgresql_server_name            = "psql-ahmedetap-staging"
postgresql_database_name          = "ahmedetap"
postgresql_admin_login            = "etap_admin"
postgresql_admin_password         = "" # set in CI/CD
postgresql_sku_name               = "Standard_D2ds_v5"
postgresql_storage_mb             = 65536
postgresql_backup_retention_days  = 14
postgresql_geo_redundant_backup   = false
postgresql_zone_high_availability = false

# --- Redis ---
redis_cache_name  = "redis-ahmedetap-staging"
redis_sku_name    = "Standard"
redis_family      = "C"
redis_capacity    = 2
redis_shard_count = 0

# --- Security ---
key_vault_name = "kv-ahmedetap-staging"
acr_name       = "acrahmedetapstaging"

# --- Monitoring ---
log_analytics_workspace_name = "law-ahmedetap-staging"
log_analytics_retention_days = 30
alert_emails                 = ["ops@example.com"]

# --- Helm ---
deploy_helm_chart = true
helm_release_name = "ahmedetap"
helm_namespace    = "ahmedetap"
helm_image_tag    = "staging"

# --- Ingress ---
ingress_domain      = "staging.ahmedetap.example.com"
ingress_tls_enabled = true

# --- CI/CD ---
github_actions_oidc_enabled = true
