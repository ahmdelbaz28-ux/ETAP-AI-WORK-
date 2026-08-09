output "id" {
  value = azurerm_redis_cache.this.id
}

output "hostname" {
  value = azurerm_redis_cache.this.hostname
}

output "ssl_port" {
  value = azurerm_redis_cache.this.ssl_port
}

output "primary_access_key" {
  value     = azurerm_redis_cache.this.primary_access_key
  sensitive = true
}

output "private_endpoint_ip" {
  value = azurerm_private_endpoint.redis.private_service_connection[0].private_ip_address
}

output "connection_string" {
  value     = format("%s:6380,password=%s,ssl=True,abortConnect=False", azurerm_redis_cache.this.hostname, azurerm_redis_cache.this.primary_access_key)
  sensitive = true
}
