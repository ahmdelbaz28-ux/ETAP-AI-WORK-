# AhmedETAP — Dev Backend Configuration
resource_group_name  = "rg-ahmedetap-tfstate"
storage_account_name = "stahmedetaptfstatedev"
container_name       = "terraform-state"
key                  = "ahmedetap/dev/terraform.tfstate"
use_azuread_auth     = true
