# AhmedETAP — Production Backend Configuration
resource_group_name  = "rg-ahmedetap-tfstate"
storage_account_name = "stahmedetapstateprod"
container_name       = "terraform-state"
key                  = "ahmedetap/prod/terraform.tfstate"
use_azuread_auth     = true
