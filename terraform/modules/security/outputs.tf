output "key_vault_id" {
  value = azurerm_key_vault.this.id
}

output "key_vault_uri" {
  value = azurerm_key_vault.this.vault_uri
}

output "key_vault_name" {
  value = azurerm_key_vault.this.name
}

output "acr_id" {
  value = azurerm_container_registry.this.id
}

output "acr_login_server" {
  value = azurerm_container_registry.this.login_server
}

output "acr_name" {
  value = azurerm_container_registry.this.name
}

# SECURITY AUDIT R7-B1: This output was incorrectly returning azurerm_key_vault.this.id.
# The AKS user-assigned identity lives in the AKS module (modules/aks/main.tf).
# Consumers should use module.aks.identity_principal_id instead.
# This output is retained for backward compatibility but now marked as deprecated
# in the description field. NOTE: The `deprecated` attribute was introduced in
# Terraform 1.11+, but our CI uses 1.9.0, so we use description-only deprecation.
output "aks_identity_id" {
  value       = azurerm_key_vault.this.id # NOTE: This is the Key Vault ID, NOT the AKS identity.
  description = "DEPRECATED: Use module.aks.identity_principal_id for the AKS managed identity."
}
