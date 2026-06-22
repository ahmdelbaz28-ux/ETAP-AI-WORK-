# =============================================================================
# AKS Module — Cluster, Node Pools, Monitoring
# =============================================================================

# ---------------------------------------------------------------------------
# Managed Identity for AKS
# ---------------------------------------------------------------------------
resource "azurerm_user_assigned_identity" "aks" {
  name                = "id-${var.cluster_name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

# ---------------------------------------------------------------------------
# AKS Cluster
# ---------------------------------------------------------------------------
resource "azurerm_kubernetes_cluster" "this" {
  name                = var.cluster_name
  location            = var.location
  resource_group_name = var.resource_group_name
  dns_prefix          = var.cluster_name
  kubernetes_version  = var.kubernetes_version
  sku_tier            = var.sku_tier
  node_resource_group = "${var.resource_group_name}-nodes"
  tags                = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.aks.id]
  }

  default_node_pool {
    name                = var.system_node_pool.name
    vm_size             = var.system_node_pool.vm_size
    min_count           = var.system_node_pool.min_count
    max_count           = var.system_node_pool.max_count
    enable_auto_scaling = var.system_node_pool.enable_auto_scaling
    vnet_subnet_id      = var.subnet_id
    zones               = var.system_node_pool.availability_zones
    os_disk_size_gb     = var.system_node_pool.os_disk_size_gb
    max_pods            = var.system_node_pool.max_pods
    node_labels = {
      "nodepool-type" = "system"
    }
  }

  network_profile {
    network_plugin     = var.network_profile.network_plugin
    network_policy     = var.network_profile.network_policy
    network_data_plane = var.network_profile.network_data_plane
    service_cidr       = var.network_profile.service_cidr
    dns_service_ip     = var.network_profile.dns_service_ip
    outbound_type      = var.network_profile.outbound_type
    load_balancer_sku  = var.network_profile.load_balancer_sku
  }

  oms_agent {
    log_analytics_workspace_id = var.log_analytics_workspace_id
  }

  key_vault_secrets_provider {
    secret_rotation_enabled = true
  }

  azure_active_directory_role_based_access_control {
    managed                = true
    admin_group_object_ids = null
    azure_rbac_enabled     = true
  }

  storage_profile {
    blob_driver_enabled = true
    disk_driver_enabled = true
  }

  oidc_issuer_enabled = true
  oidc_issuer_url     = null

  lifecycle {
    ignore_changes = [
      default_node_pool[0].node_count,
      kubernetes_version,
    ]
  }
}

# ---------------------------------------------------------------------------
# User Node Pools
# ---------------------------------------------------------------------------
resource "azurerm_kubernetes_cluster_node_pool" "user" {
  for_each = var.user_node_pools

  name                  = each.key
  kubernetes_cluster_id = azurerm_kubernetes_cluster.this.id
  vm_size               = each.value.vm_size
  min_count             = each.value.min_count
  max_count             = each.value.max_count
  enable_auto_scaling   = each.value.enable_auto_scaling
  vnet_subnet_id        = var.subnet_id
  zones                 = each.value.availability_zones
  os_disk_size_gb       = each.value.os_disk_size_gb
  max_pods              = each.value.max_pods
  node_taints           = each.value.node_taints
  node_labels           = each.value.node_labels

  lifecycle {
    ignore_changes = [
      node_count,
    ]
  }
}

# ---------------------------------------------------------------------------
# ACR Integration (attach ACR to AKS)
# ---------------------------------------------------------------------------
resource "azurerm_role_assignment" "acr_pull" {
  count = var.acr_id != null ? 1 : 0

  principal_id         = azurerm_user_assigned_identity.aks.principal_id
  role_definition_name = "AcrPull"
  scope                = var.acr_id
}

# ---------------------------------------------------------------------------
# Workload Identity for Helm deployments
# ---------------------------------------------------------------------------
resource "azurerm_federated_identity_credential" "helm_deploy" {
  name                = "helm-deploy"
  resource_group_name = var.resource_group_name
  audience            = ["api://AzureADTokenExchange"]
  issuer              = azurerm_kubernetes_cluster.this.oidc_issuer_url
  parent_id           = azurerm_user_assigned_identity.aks.id
  subject             = "system:serviceaccount:ahmedetap:helm-deploy"
}
