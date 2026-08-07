# =============================================================================
<<<<<<< HEAD
# AhmedETAP — Terraform Remote State Backend (Azure Blob Storage)
# =============================================================================
# CRITICAL FIX: Switched from local backend to azurerm backend.
# Local backend has no state locking — concurrent deployments corrupt state.
# Per CI/CD skill: "Set it up on day one." Remote state with locking prevents
# data loss and ensures consistent infrastructure deployments.
#
# Prerequisites:
#   1. Azure Storage Account created (via az cli or portal)
#   2. Container named "tfstate" exists in the storage account
#   3. Run: terraform init -backend-config="environments/<env>/backend.hcl"
#
# backend.hcl format (per environment):
#   resource_group_name  = "etap-ai-tfstate-rg"
#   storage_account_name = "etapaitfstate<env>"
#   container_name       = "tfstate"
#   key                  = "etap-ai-<env>.tfstate"
# =============================================================================
# NOTE: For initial bootstrap before the storage account exists, you can
# temporarily use the local backend. After creating the storage account,
# migrate state with: terraform init -migrate-state

terraform {
  backend "azurerm" {
    # These values are provided via -backend-config at init time
    # Do NOT hardcode them here — each environment has its own backend.hcl
    resource_group_name  = null # overridden by backend.hcl
    storage_account_name = null # overridden by backend.hcl
    container_name       = null # overridden by backend.hcl
    key                  = null # overridden by backend.hcl
    use_azuread_auth     = true # OIDC auth, no storage key needed
=======
# AhmedETAP — Terraform Local State Backend
# =============================================================================
# Uses local file-based state. No Azure subscription required.
#
# To switch back to Azure remote state, replace with:
#   backend "azurerm" {
#     use_azuread_auth = true
#   }
#   terraform init -backend-config="environments/<env>/backend.hcl"
# =============================================================================

terraform {
  backend "local" {
    path = "terraform.tfstate"
>>>>>>> origin/fix/scenario-tests-properly
  }
}
