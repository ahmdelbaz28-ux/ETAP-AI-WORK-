# =============================================================================
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
  }
}
