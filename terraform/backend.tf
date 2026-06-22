# =============================================================================
# AhmedETAP — Terraform Remote State Backend
# =============================================================================
# Uses Azure Storage Account for remote state storage with locking.
# Initialize with:
#   terraform init -backend-config="environments/<env>/backend.hcl"
#
# Or set backend config via environment variables:
#   export ARM_ACCESS_KEY=<storage-account-key>
# =============================================================================

terraform {
  backend "azurerm" {
    # These values are provided via -backend-config or environment variables
    # because they differ per environment.
    #
    # resource_group_name  = "rg-ahmedetap-tfstate"
    # storage_account_name = "stahmedetaptfstate"
    # container_name       = "terraform-state"
    # key                  = "ahmedetap/terraform.tfstate"
    use_azuread_auth = true
  }
}
