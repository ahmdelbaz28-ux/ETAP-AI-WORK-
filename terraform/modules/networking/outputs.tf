output "vnet_id" {
  value = azurerm_virtual_network.this.id
}

output "vnet_name" {
  value = azurerm_virtual_network.this.name
}

output "subnet_ids" {
  value = { for k, v in azurerm_subnet.this : k => v.id }
}

output "aks_subnet_id" {
  value = azurerm_subnet.this["aks-system"].id
}

output "aks_user_subnet_id" {
  value = azurerm_subnet.this["aks-user"].id
}

output "postgresql_subnet_id" {
  value = azurerm_subnet.this["postgresql"].id
}

output "redis_subnet_id" {
  value = azurerm_subnet.this["redis"].id
}

output "private_endpoints_subnet_id" {
  value = azurerm_subnet.this["private-endpoints"].id
}

output "app_gateway_subnet_id" {
  value = azurerm_subnet.this["app-gateway"].id
}

output "postgresql_private_dns_zone_id" {
  value = azurerm_private_dns_zone.this["postgresql"].id
}

output "redis_private_dns_zone_id" {
  value = azurerm_private_dns_zone.this["redis"].id
}
