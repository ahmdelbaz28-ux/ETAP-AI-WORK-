output "log_analytics_workspace_id" {
  value = var.workspace_id
}

output "log_analytics_workspace_name" {
  value = var.workspace_name
}

output "action_group_id" {
  value = length(var.alert_emails) > 0 ? azurerm_monitor_action_group.this[0].id : null
}
