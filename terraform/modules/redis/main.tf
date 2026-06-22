# =============================================================================
# Redis Module — Azure Cache for Redis (Premium)
# =============================================================================

# ---------------------------------------------------------------------------
# Redis Cache
# ---------------------------------------------------------------------------
resource "azurerm_redis_cache" "this" {
  name                = var.cache_name
  location            = var.location
  resource_group_name = var.resource_group_name
  sku_name            = var.sku_name
  family              = var.family
  capacity            = var.capacity
  redis_version       = var.redis_version

  enable_non_ssl_port           = var.enable_non_ssl_port
  minimum_tls_version           = "1.2"
  public_network_access_enabled = false
  shard_count                   = var.shard_count

  redis_configuration {
    aof_backup_enabled              = var.sku_name == "Premium" ? true : false
    aof_storage_connection_string_0 = var.sku_name == "Premium" ? null : null
    enable_authentication           = true
  }

  tags = var.tags
}

# ---------------------------------------------------------------------------
# Private Endpoint for Redis
# ---------------------------------------------------------------------------
resource "azurerm_private_endpoint" "redis" {
  name                = "pe-${var.cache_name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.subnet_id

  private_service_connection {
    name                           = "psc-redis"
    private_connection_resource_id = azurerm_redis_cache.this.id
    subresource_names              = ["redisCache"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "redis-dns-zone-group"
    private_dns_zone_ids = [var.private_dns_zone_id]
  }

  tags = var.tags
}

# ---------------------------------------------------------------------------
# Private DNS A Record for Redis
# ---------------------------------------------------------------------------
resource "azurerm_private_dns_a_record" "redis" {
  name                = var.cache_name
  zone_name           = split("/", var.private_dns_zone_id)[length(split("/", var.private_dns_zone_id)) - 1]
  resource_group_name = var.resource_group_name
  ttl                 = 300
  records             = [azurerm_private_endpoint.redis.private_service_connection[0].private_ip_address]

  depends_on = [azurerm_private_endpoint.redis]
}
