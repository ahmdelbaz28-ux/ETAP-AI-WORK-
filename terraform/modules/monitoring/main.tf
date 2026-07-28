# =============================================================================
# Monitoring Module — Log Analytics, Diagnostics, Alerts
# =============================================================================

# ---------------------------------------------------------------------------
# Diagnostic Settings for AKS
# ---------------------------------------------------------------------------
resource "azurerm_monitor_diagnostic_setting" "aks" {
  count = var.aks_cluster_id != null ? 1 : 0

  name                       = "aks-diagnostics"
  target_resource_id         = var.aks_cluster_id
  log_analytics_workspace_id = var.workspace_id

  enabled_log {
    category = "kube-apiserver"
  }
  enabled_log {
    category = "kube-controller-manager"
  }
  enabled_log {
    category = "kube-scheduler"
  }
  enabled_log {
    category = "kube-audit"
  }
  enabled_log {
    category = "cluster-autoscaler"
  }
  enabled_log {
    category = "guard"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}

# ---------------------------------------------------------------------------
# Metric Alerts
# ---------------------------------------------------------------------------
resource "azurerm_monitor_metric_alert" "cpu_high" {
  count = length(var.alert_emails) > 0 ? 1 : 0

  name                = "CPU-High-AKS"
  resource_group_name = var.resource_group_name
  scopes              = var.aks_cluster_id != null ? [var.aks_cluster_id] : []
  description         = "Alert when CPU usage is high on AKS nodes"
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.ContainerService/managedClusters"
    metric_name      = "cpuUsagePercentage"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = azurerm_monitor_action_group.this[0].id
  }
}

resource "azurerm_monitor_metric_alert" "memory_high" {
  count = length(var.alert_emails) > 0 ? 1 : 0

  name                = "Memory-High-AKS"
  resource_group_name = var.resource_group_name
  scopes              = var.aks_cluster_id != null ? [var.aks_cluster_id] : []
  description         = "Alert when memory usage is high on AKS nodes"
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.ContainerService/managedClusters"
    metric_name      = "memoryUsagePercentage"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = azurerm_monitor_action_group.this[0].id
  }
}

resource "azurerm_monitor_metric_alert" "disk_full" {
  count = length(var.alert_emails) > 0 ? 1 : 0

  name                = "Disk-Full-AKS"
  resource_group_name = var.resource_group_name
  scopes              = var.aks_cluster_id != null ? [var.aks_cluster_id] : []
  description         = "Alert when disk usage is high on AKS nodes"
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.ContainerService/managedClusters"
    metric_name      = "diskUsagePercentage"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 85
  }

  action {
    action_group_id = azurerm_monitor_action_group.this[0].id
  }
}

# ---------------------------------------------------------------------------
# Action Group (Email Notifications)
# ---------------------------------------------------------------------------
resource "azurerm_monitor_action_group" "this" {
  count = length(var.alert_emails) > 0 ? 1 : 0

  name                = "ag-ahmedetap-alerts"
  resource_group_name = var.resource_group_name
  short_name          = "AhmedETAP"

  dynamic "email_receiver" {
    for_each = var.alert_emails
    content {
      name          = "alert-${index(var.alert_emails, email_receiver.value)}"
      email_address = email_receiver.value
    }
  }
}

# ---------------------------------------------------------------------------
# Kubernetes Log Analytics Query (for quick reference)
# ---------------------------------------------------------------------------
resource "azurerm_log_analytics_saved_search" "error_logs" {
  name                       = "ErrorLogs"
  log_analytics_workspace_id = var.workspace_id
  category                   = "AhmedETAP"
  display_name               = "AhmedETAP - Error Logs (Last 24h)"
  query                      = <<-QUERY
    ContainerLog
    | where LogEntry has "ERROR" or LogEntry has "Exception"
    | where TimeGenerated > ago(24h)
    | project TimeGenerated, Computer, LogEntry
    | order by TimeGenerated desc
    | take 100
  QUERY
}
