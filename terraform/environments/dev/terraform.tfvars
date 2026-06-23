# =============================================================================
# AhmedETAP — Development Environment
# =============================================================================
# Minimal footprint for development and testing.
# Single-node AKS, basic PostgreSQL, no HA.
# =============================================================================

environment         = "dev"
location            = "eastus2"
resource_group_name = "rg-ahmedetap-dev"

tags = {
  managed_by  = "terraform"
  project     = "ahmedetap"
  environment = "dev"
}

# --- Networking ---
vnet_name          = "vnet-ahmedetap-dev"
vnet_address_space = ["10.0.0.0/16"]

# --- AKS ---
aks_cluster_name   = "aks-ahmedetap-dev"
kubernetes_version = "1.30"
aks_sku_tier       = "Free"

aks_system_node_pool = {
  name                = "system"
  vm_size             = "Standard_D4s_v5"
  min_count           = 1
  max_count           = 3
  enable_auto_scaling = true
  availability_zones  = []
  os_disk_size_gb     = 64
  max_pods            = 50
}

aks_user_node_pools = {
  services = {
    vm_size             = "Standard_D4s_v5"
    min_count           = 1
    max_count           = 3
    enable_auto_scaling = true
    availability_zones  = []
    os_disk_size_gb     = 64
    max_pods            = 50
    node_labels         = { "nodepool-type" = "services" }
  }
}

# --- PostgreSQL ---
postgresql_server_name            = "psql-ahmedetap-dev"
postgresql_database_name          = "ahmedetap"
postgresql_admin_login            = "etap_admin"
postgresql_admin_password         = "" # auto-generated
postgresql_sku_name               = "Standard_B2s"
postgresql_storage_mb             = 32768
postgresql_backup_retention_days  = 7
postgresql_geo_redundant_backup   = false
postgresql_zone_high_availability = false

# --- Redis ---
redis_cache_name  = "redis-ahmedetap-dev"
redis_sku_name    = "Standard"
redis_family      = "C"
redis_capacity    = 1
redis_shard_count = 0

# --- Security ---
key_vault_name = "kv-ahmedetap-dev"
acr_name       = "acrahmedetapdev"

# --- Monitoring ---
log_analytics_workspace_name = "law-ahmedetap-dev"
log_analytics_retention_days = 14
alert_emails                 = []

# --- Helm ---
deploy_helm_chart = true
helm_release_name = "ahmedetap"
helm_namespace    = "ahmedetap"
helm_image_tag    = "latest"

# --- Ingress ---
ingress_domain      = "dev.ahmedetap.example.com"
ingress_tls_enabled = false

# --- CI/CD ---
github_actions_oidc_enabled = false
