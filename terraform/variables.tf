# =============================================================================
# AhmedETAP — Terraform Variables
# =============================================================================

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "eastus2"
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
  default     = "rg-ahmedetap"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    managed_by = "terraform"
    project    = "ahmedetap"
  }
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------
variable "vnet_name" {
  description = "Name of the virtual network"
  type        = string
  default     = "vnet-ahmedetap"
}

variable "vnet_address_space" {
  description = "Address space for the virtual network"
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

variable "subnet_configs" {
  description = "Subnet configurations"
  type = map(object({
    address_prefixes     = list(string)
    service_endpoints    = optional(list(string))
    private_link_service = optional(bool, false)
    delegation = optional(object({
      name = string
      service_delegation = object({
        name    = string
        actions = optional(list(string))
      })
    }))
  }))
  default = {
    aks-system = {
      address_prefixes  = ["10.0.0.0/19"]
      service_endpoints = ["Microsoft.Storage", "Microsoft.ContainerRegistry"]
    }
    aks-user = {
      address_prefixes  = ["10.0.32.0/19"]
      service_endpoints = ["Microsoft.Storage", "Microsoft.ContainerRegistry"]
    }
    postgresql = {
      address_prefixes  = ["10.0.64.0/27"]
      service_endpoints = []
      delegation = {
        name = "postgresql-delegation"
        service_delegation = {
          name    = "Microsoft.DBforPostgreSQL/flexibleServers"
          actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
        }
      }
    }
    redis = {
      address_prefixes  = ["10.0.64.32/27"]
      service_endpoints = []
    }
    private-endpoints = {
      address_prefixes  = ["10.0.64.64/27"]
      service_endpoints = []
    }
    app-gateway = {
      address_prefixes  = ["10.0.64.96/27"]
      service_endpoints = []
    }
  }
}

variable "private_dns_zones" {
  description = "Private DNS zones to create"
  type = map(object({
    name                 = string
    registration_enabled = optional(bool, false)
    virtual_network_id   = optional(string)
  }))
  default = {
    postgresql = {
      name = "privatelink.postgres.database.azure.com"
    }
    redis = {
      name = "privatelink.redis.cache.windows.net"
    }
  }
}

# ---------------------------------------------------------------------------
# AKS
# ---------------------------------------------------------------------------
variable "aks_cluster_name" {
  description = "Name of the AKS cluster"
  type        = string
  default     = "aks-ahmedetap"
}

variable "kubernetes_version" {
  description = "Kubernetes version for the AKS cluster"
  type        = string
  default     = "1.30"
}

variable "aks_sku_tier" {
  description = "SKU tier for the AKS cluster (Free or Standard)"
  type        = string
  default     = "Standard"
}

variable "aks_system_node_pool" {
  description = "System node pool configuration"
  type = object({
    name                = string
    vm_size             = string
    min_count           = number
    max_count           = number
    enable_auto_scaling = bool
    availability_zones  = optional(list(string))
    os_disk_size_gb     = optional(number)
    max_pods            = optional(number)
  })
  default = {
    name                = "system"
    vm_size             = "Standard_D4s_v5"
    min_count           = 2
    max_count           = 5
    enable_auto_scaling = true
    availability_zones  = ["1", "2", "3"]
    os_disk_size_gb     = 128
    max_pods            = 50
  }
}

variable "aks_user_node_pools" {
  description = "User node pool configurations"
  type = map(object({
    vm_size             = string
    min_count           = number
    max_count           = number
    enable_auto_scaling = bool
    availability_zones  = optional(list(string))
    os_disk_size_gb     = optional(number)
    node_taints         = optional(list(string))
    max_pods            = optional(number)
    node_labels         = optional(map(string))
  }))
  default = {
    services = {
      vm_size             = "Standard_D8s_v5"
      min_count           = 2
      max_count           = 10
      enable_auto_scaling = true
      availability_zones  = ["1", "2", "3"]
      os_disk_size_gb     = 256
      max_pods            = 50
      node_labels = {
        "nodepool-type" = "services"
      }
    }
    compute = {
      vm_size             = "Standard_F8s_v2"
      min_count           = 1
      max_count           = 5
      enable_auto_scaling = true
      availability_zones  = ["1", "2", "3"]
      os_disk_size_gb     = 128
      max_pods            = 30
      node_labels = {
        "nodepool-type" = "compute"
      }
    }
  }
}

variable "aks_network_profile" {
  description = "AKS network profile configuration"
  type = object({
    network_plugin     = string
    network_policy     = string
    network_data_plane = optional(string)
    service_cidr       = optional(string)
    dns_service_ip     = optional(string)
    outbound_type      = optional(string)
    load_balancer_sku  = string
  })
  default = {
    network_plugin     = "azure"
    network_policy     = "calico"
    network_data_plane = "azure"
    service_cidr       = "172.16.0.0/16"
    dns_service_ip     = "172.16.0.10"
    outbound_type      = "loadBalancer"
    load_balancer_sku  = "standard"
  }
}

# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------
variable "postgresql_server_name" {
  description = "Name of the PostgreSQL flexible server"
  type        = string
  default     = "psql-ahmedetap"
}

variable "postgresql_database_name" {
  description = "Name of the PostgreSQL database"
  type        = string
  default     = "ahmedetap"
}

variable "postgresql_admin_login" {
  description = "Admin login for PostgreSQL server"
  type        = string
  default     = "etap_admin"
}

variable "postgresql_admin_password" {
  description = "Admin password for PostgreSQL server"
  type        = string
  sensitive   = true
}

variable "postgresql_sku_name" {
  description = "SKU name for PostgreSQL flexible server"
  type        = string
  default     = "Standard_D2ds_v5"
}

variable "postgresql_storage_mb" {
  description = "Storage size in MB for PostgreSQL"
  type        = number
  default     = 32768
}

variable "postgresql_backup_retention_days" {
  description = "Backup retention days for PostgreSQL"
  type        = number
  default     = 7
}

variable "postgresql_geo_redundant_backup" {
  description = "Enable geo-redundant backup for PostgreSQL"
  type        = bool
  default     = false
}

variable "postgresql_zone_high_availability" {
  description = "Enable zone-redundant high availability for PostgreSQL"
  type        = bool
  default     = false
}

# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------
variable "redis_cache_name" {
  description = "Name of the Azure Cache for Redis"
  type        = string
  default     = "redis-ahmedetap"
}

variable "redis_sku_name" {
  description = "SKU name for Redis cache"
  type        = string
  default     = "Premium"
}

variable "redis_family" {
  description = "Family for Redis cache (P = Premium)"
  type        = string
  default     = "P"
}

variable "redis_capacity" {
  description = "Capacity for Redis cache (1-3 for Premium)"
  type        = number
  default     = 1
}

variable "redis_enable_non_ssl_port" {
  description = "Enable non-SSL port for Redis"
  type        = bool
  default     = false
}

variable "redis_shard_count" {
  description = "Shard count for Redis cluster"
  type        = number
  default     = 0
}

variable "redis_version" {
  description = "Redis version"
  type        = string
  default     = "7"
}

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
variable "key_vault_name" {
  description = "Name of the Key Vault"
  type        = string
  default     = "kv-ahmedetap"
}

variable "acr_name" {
  description = "Name of the Azure Container Registry"
  type        = string
  default     = "acrahmedetap"
}

# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------
variable "log_analytics_workspace_name" {
  description = "Name of the Log Analytics workspace"
  type        = string
  default     = "law-ahmedetap"
}

variable "log_analytics_retention_days" {
  description = "Retention days for Log Analytics workspace"
  type        = number
  default     = 30
}

variable "alert_emails" {
  description = "Email addresses for alert notifications"
  type        = list(string)
  default     = []
}

# ---------------------------------------------------------------------------
# Helm Chart Deployment
# ---------------------------------------------------------------------------
variable "deploy_helm_chart" {
  description = "Deploy the AhmedETAP Helm chart onto AKS"
  type        = bool
  default     = false
}

variable "helm_release_name" {
  description = "Name of the Helm release"
  type        = string
  default     = "ahmedetap"
}

variable "helm_chart_repository" {
  description = "Helm chart repository URL"
  type        = string
  default     = "https://ahmdelbaz28-ux.github.io/ETAP-AI-WORK-/charts"
}

variable "helm_chart_name" {
  description = "Name of the Helm chart"
  type        = string
  default     = "etap-ai"
}

variable "helm_chart_version" {
  description = "Version of the Helm chart to deploy"
  type        = string
  default     = "1.0.0"
}

variable "helm_namespace" {
  description = "Kubernetes namespace for the Helm release"
  type        = string
  default     = "ahmedetap"
}

variable "helm_image_tag" {
  description = "Docker image tag for the Helm chart"
  type        = string
  default     = "latest"
}

# ---------------------------------------------------------------------------
# Ingress
# ---------------------------------------------------------------------------
variable "ingress_domain" {
  description = "Domain name for ingress"
  type        = string
  default     = ""
}

variable "ingress_tls_enabled" {
  description = "Enable TLS for ingress"
  type        = bool
  default     = false
}

# ---------------------------------------------------------------------------
# CI/CD Integration
# ---------------------------------------------------------------------------
variable "deployer_object_id" {
  description = "Azure AD object ID of the deploying user (for Key Vault access). Auto-detected if empty."
  type        = string
  default     = ""
}

variable "github_actions_oidc_enabled" {
  description = "Enable GitHub Actions OIDC federated identity"
  type        = bool
  default     = false
}

variable "github_repository" {
  description = "GitHub repository for OIDC federated identity"
  type        = string
  default     = "ahmdelbaz28-ux/ETAP-AI-WORK-"
}
