# =============================================================================
# AhmedETAP — Terraform Azure Provider Configuration
# =============================================================================
#
# Required for terraform plan/apply to function. Without this, you get:
#   Error: Insufficient features blocks
#
# When deploying to an actual AKS cluster, add providers for:
#   helm, kubernetes, and kubectl (see: terraform/README.md)
# =============================================================================

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy               = true
      recover_soft_deleted_key_vaults            = true
      purge_soft_deleted_keys_on_destroy         = true
      recover_soft_deleted_keys                  = true
      purge_soft_deleted_secrets_on_destroy      = true
      recover_soft_deleted_secrets               = true
      purge_soft_deleted_certificates_on_destroy = true
      recover_soft_deleted_certificates          = true
    }
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
    log_analytics_workspace {
      permanently_delete_on_destroy = true
    }
  }
}

provider "azuread" {
  # Uses Azure CLI or environment variables for authentication
}
