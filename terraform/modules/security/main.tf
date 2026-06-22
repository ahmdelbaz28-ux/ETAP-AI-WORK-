# =============================================================================
# Security Module — Key Vault, ACR, Managed Identities
# =============================================================================

# ---------------------------------------------------------------------------
# Azure Container Registry
# ---------------------------------------------------------------------------
resource "azurerm_container_registry" "this" {
  name                = var.acr_name
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "Premium"
  admin_enabled       = false

  # Geo-replication for production
  dynamic "georeplications" {
    for_each = var.tags["environment"] == "prod" ? [
      { location = "westeurope", zone_redundancy_enabled = true },
      { location = "southeastasia", zone_redundancy_enabled = true },
    ] : []
    content {
      location                = georeplications.value.location
      zone_redundancy_enabled = georeplications.value.zone_redundancy_enabled
    }
  }

  # ACR network access is controlled via subnet service endpoints and RBAC.
  # AKS nodes authenticate using Managed Identity (AcrPull role).

  trust_policy {
    enabled = true
  }

  retention_policy {
    days    = 30
    enabled = true
  }

  tags = var.tags
}

# ---------------------------------------------------------------------------
# Key Vault
# ---------------------------------------------------------------------------
resource "azurerm_key_vault" "this" {
  name                = var.key_vault_name
  location            = var.location
  resource_group_name = var.resource_group_name
  tenant_id           = var.tenant_id
  sku_name            = "standard"

  enabled_for_deployment          = true
  enabled_for_disk_encryption     = true
  enabled_for_template_deployment = true
  purge_protection_enabled        = true
  soft_delete_retention_days      = 90

  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
  }

  tags = var.tags
}

# ---------------------------------------------------------------------------
# Key Vault Access Policy for current user
# ---------------------------------------------------------------------------
resource "azurerm_key_vault_access_policy" "deployer" {
  count = var.deployer_object_id != null ? 1 : 0

  key_vault_id = azurerm_key_vault.this.id
  tenant_id    = var.tenant_id
  object_id    = var.deployer_object_id

  key_permissions = [
    "Get", "List", "Create", "Decrypt", "Encrypt",
  ]

  secret_permissions = [
    "Get", "List", "Set", "Delete",
  ]

  certificate_permissions = [
    "Get", "List", "Create", "Delete",
  ]
}

# ---------------------------------------------------------------------------
# Store secrets from other modules
# ---------------------------------------------------------------------------
resource "azurerm_key_vault_secret" "placeholder" {
  name         = "PLACEHOLDER"
  value        = "Secrets are populated during deployment"
  key_vault_id = azurerm_key_vault.this.id

  tags = var.tags
}
