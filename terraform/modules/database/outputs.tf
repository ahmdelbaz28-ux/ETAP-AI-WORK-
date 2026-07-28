output "fqdn" {
  value = azurerm_postgresql_flexible_server.this.fqdn
}

output "server_id" {
  value = azurerm_postgresql_flexible_server.this.id
}

output "database_name" {
  value = azurerm_postgresql_flexible_server_database.this.name
}

output "admin_login" {
  value = var.admin_login
}

output "admin_password" {
  value     = azurerm_postgresql_flexible_server.this.administrator_password
  sensitive = true
}

output "connection_string" {
  value = format(
    "postgresql://%s:%s@%s:5432/%s?sslmode=require",
    var.admin_login,
    azurerm_postgresql_flexible_server.this.administrator_password,
    azurerm_postgresql_flexible_server.this.fqdn,
    var.database_name
  )
  sensitive = true
}
