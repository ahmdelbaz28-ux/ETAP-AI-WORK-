# =============================================================================
# Database Module — Azure PostgreSQL Flexible Server
# =============================================================================

# ---------------------------------------------------------------------------
# Random password (fallback if admin_password not provided)
# ---------------------------------------------------------------------------
resource "random_password" "postgresql" {
  length           = 32
  special          = false
  override_special = ""
}

# ---------------------------------------------------------------------------
# PostgreSQL Flexible Server
# ---------------------------------------------------------------------------
resource "azurerm_postgresql_flexible_server" "this" {
  name                          = var.server_name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  sku_name                      = var.sku_name
  version                       = "16"
  storage_mb                    = var.storage_mb
  backup_retention_days         = var.backup_retention_days
  geo_redundant_backup_enabled  = var.geo_redundant_backup
  administrator_login           = var.admin_login
  administrator_password        = var.admin_password != "" ? var.admin_password : random_password.postgresql.result
  delegated_subnet_id           = var.delegated_subnet_id
  private_dns_zone_id           = var.private_dns_zone_id
  public_network_access_enabled = false

  dynamic "high_availability" {
    for_each = var.zone_high_availability ? [1] : []
    content {
      mode = "ZoneRedundant"
    }
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = var.tags
}

# ---------------------------------------------------------------------------
# PostgreSQL Database
# ---------------------------------------------------------------------------
resource "azurerm_postgresql_flexible_server_database" "this" {
  name      = var.database_name
  server_id = azurerm_postgresql_flexible_server.this.id
  collation = "en_US.utf8"
  charset   = "UTF8"

  depends_on = [azurerm_postgresql_flexible_server.this]
}

# ---------------------------------------------------------------------------
# PostgreSQL Configuration
# ---------------------------------------------------------------------------
resource "azurerm_postgresql_flexible_server_configuration" "timezone" {
  name      = "timezone"
  server_id = azurerm_postgresql_flexible_server.this.id
  value     = "UTC"
}

resource "azurerm_postgresql_flexible_server_configuration" "pgbouncer" {
  name      = "pgbouncer.enabled"
  server_id = azurerm_postgresql_flexible_server.this.id
  value     = "true"
}

resource "azurerm_postgresql_flexible_server_configuration" "max_connections" {
  name      = "max_connections"
  server_id = azurerm_postgresql_flexible_server.this.id
  value     = "100"
}
