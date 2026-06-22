# AhmedETAP — Staging Backend Configuration
resource_group_name  = "rg-ahmedetap-tfstate"
storage_account_name = "stahmedetapstatestaging"
container_name       = "terraform-state"
key                  = "ahmedetap/staging/terraform.tfstate"
use_azuread_auth     = true
