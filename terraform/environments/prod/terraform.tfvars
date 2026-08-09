# =============================================================================
# AhmedETAP — Production Environment
# =============================================================================
# Full enterprise-grade deployment with:
# - Zone-redundant AKS (3 zones)
# - HA PostgreSQL (zone-redundant)
# - Premium Redis with clustering
# - Geo-replicated ACR
# - 24/7 monitoring with alerting
# =============================================================================

environment         = "prod"
location            = "eastus2"
resource_group_name = "rg-ahmedetap-prod"

tags = {
  managed_by  = "terraform"
  project     = "ahmedetap"
  environment = "prod"
}

# --- Networking ---
vnet_name          = "vnet-ahmedetap-prod"
vnet_address_space = ["10.2.0.0/16"]

# --- AKS ---
aks_cluster_name   = "aks-ahmedetap-prod"
kubernetes_version = "1.30"
aks_sku_tier       = "Standard"

aks_system_node_pool = {
  name                = "system"
  vm_size             = "Standard_D8s_v5"
  min_count           = 3
  max_count           = 6
  enable_auto_scaling = true
  availability_zones  = ["1", "2", "3"]
  os_disk_size_gb     = 256
  max_pods            = 50
}

aks_user_node_pools = {
  services = {
    vm_size             = "Standard_D8s_v5"
    min_count           = 3
    max_count           = 15
    enable_auto_scaling = true
    availability_zones  = ["1", "2", "3"]
    os_disk_size_gb     = 256
    max_pods            = 50
    node_labels         = { "nodepool-type" = "services" }
  }
  compute = {
    vm_size             = "Standard_F16s_v2"
    min_count           = 2
    max_count           = 10
    enable_auto_scaling = true
    availability_zones  = ["1", "2", "3"]
    os_disk_size_gb     = 128
    max_pods            = 30
    node_taints         = ["compute=true:NoSchedule"]
    node_labels         = { "nodepool-type" = "compute" }
  }
}

# --- PostgreSQL ---
postgresql_server_name            = "psql-ahmedetap-prod"
postgresql_database_name          = "ahmedetap"
postgresql_admin_login            = "etap_admin"
postgresql_admin_password         = "" # must be set via CI/CD secrets
postgresql_sku_name               = "Standard_D4ds_v5"
postgresql_storage_mb             = 262144
postgresql_backup_retention_days  = 30
postgresql_geo_redundant_backup   = true
postgresql_zone_high_availability = true

# --- Redis ---
redis_cache_name  = "redis-ahmedetap-prod"
redis_sku_name    = "Premium"
redis_family      = "P"
redis_capacity    = 2
redis_shard_count = 3

# --- Security ---
key_vault_name = "kv-ahmedetap-prod"
acr_name       = "acrahmedetapprod"

# --- Monitoring ---
log_analytics_workspace_name = "law-ahmedetap-prod"
log_analytics_retention_days = 90
alert_emails                 = ["ops@example.com", "oncall@example.com"]

# --- Helm ---
deploy_helm_chart = true
helm_release_name = "ahmedetap"
helm_namespace    = "ahmedetap"
helm_image_tag    = "prod"

# --- Ingress ---
ingress_domain      = "app.ahmedetap.example.com"
ingress_tls_enabled = true

# --- CI/CD ---
github_actions_oidc_enabled = true
