output "cluster_name" {
  value = azurerm_kubernetes_cluster.this.name
}

output "cluster_id" {
  value = azurerm_kubernetes_cluster.this.id
}

output "kubeconfig" {
  value     = azurerm_kubernetes_cluster.this.kube_config_raw
  sensitive = true
}

output "host" {
  value = azurerm_kubernetes_cluster.this.kube_config[0].host
}

output "identity_principal_id" {
  value = azurerm_user_assigned_identity.aks.principal_id
}

output "identity_client_id" {
  value = azurerm_user_assigned_identity.aks.client_id
}

output "oidc_issuer_url" {
  value = azurerm_kubernetes_cluster.this.oidc_issuer_url
}

output "node_resource_group" {
  value = azurerm_kubernetes_cluster.this.node_resource_group
}
