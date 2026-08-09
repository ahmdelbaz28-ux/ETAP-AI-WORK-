# AhmedETAP — Terraform Infrastructure

> Infrastructure-as-Code for deploying the AhmedETAP engineering platform on **Microsoft Azure**.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   Azure Resource Group                       │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │   AKS        │  │  PostgreSQL  │  │  Redis Cache        │  │
│  │  (K8s)       │  │  Flexible    │  │  (Premium/Std)      │  │
│  │  + Helm      │  │  Server v16  │  │  + Private Endpoint │  │
│  └──────┬───────┘  └──────┬───────┘  └─────────┬──────────┘  │
│         │                 │                    │              │
│  ┌──────┴──────────────────┴────────────────────┴──────────┐  │
│  │               Virtual Network (10.x.0.0/16)              │  │
│  │  ┌──────┐ ┌──────┐ ┌──────────┐ ┌──────┐ ┌──────────┐  │  │
│  │  │ AKS  │ │ AKS  │ │PostgreSQL│ │Redis │ │ Private  │  │  │
│  │  │System│ │ User │ │ Subnet   │ │Subnet│ │ Endpoints │  │  │
│  │  └──────┘ └──────┘ └──────────┘ └──────┘ └──────────┘  │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  Key Vault   │  │    ACR       │  │  Log Analytics     │  │
│  │  (Secrets)   │  │  (Images)    │  │  (Monitoring)      │  │
│  └──────────────┘  └──────────────┘  └────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
terraform/
├── main.tf                  # Root module — orchestrates all components
├── variables.tf             # All input variables with defaults
├── outputs.tf               # All output values
├── versions.tf              # Provider and Terraform version constraints
├── backend.tf               # Remote state backend config (Azure Storage)
├── helm-values.yaml         # Helm values template (rendered by Terraform)
├── README.md                # This file
│
├── modules/
│   ├── networking/          # VNet, subnets, NSGs, private DNS zones
│   ├── aks/                 # AKS cluster with node pools, monitoring
│   ├── database/            # PostgreSQL Flexible Server
│   ├── redis/               # Azure Cache for Redis (with private endpoint)
│   ├── security/            # Key Vault, ACR, managed identities
│   └── monitoring/          # Log Analytics, diagnostic settings, alerts
│
└── environments/
    ├── dev/                 # Minimal footprint for development
    ├── staging/             # Pre-production validation
    └── prod/                # Full enterprise-grade deployment
```

## Prerequisites

1. **Azure Subscription** — with Contributor + User Access Administrator permissions
2. **Azure CLI** — `az login` and authenticated
3. **Terraform** — v1.6.0 or later
4. **Storage Account** (for remote state) — see [Backend Setup](#backend-setup)

## Quick Start

### 1. Azure Login

```bash
az login
az account set --subscription "<subscription-id>"
```

### 2. Backend Setup (one-time)

```bash
# Create a resource group for Terraform state
az group create --name rg-ahmedetap-tfstate --location eastus2

# Create storage account
az storage account create \
  --name stahmedetaptfstate \
  --resource-group rg-ahmedetap-tfstate \
  --sku Standard_LRS \
  --allow-blob-public-access false

# Create container
az storage container create \
  --name terraform-state \
  --account-name stahmedetaptfstate
```

### 3. Initialize

```bash
cd terraform

# Dev
terraform init \
  -backend-config="resource_group_name=rg-ahmedetap-tfstate" \
  -backend-config="storage_account_name=stahmedetaptfstate" \
  -backend-config="container_name=terraform-state" \
  -backend-config="key=ahmedetap/dev/terraform.tfstate"

# Staging/Prod — use respective keys
```

### 4. Plan & Apply

```bash
# Dev
terraform plan -var-file="environments/dev/terraform.tfvars" -out=plan.tfplan
terraform apply plan.tfplan

# Staging
terraform plan -var-file="environments/staging/terraform.tfvars" -out=plan.tfplan
terraform apply plan.tfplan

# Prod
terraform plan -var-file="environments/prod/terraform.tfvars" -out=plan.tfplan
terraform apply plan.tfplan
```

## Environment Sizing Comparison

| Resource         | Dev              | Staging           | Prod                   |
|------------------|------------------|-------------------|------------------------|
| **AKS Tier**     | Free             | Standard          | Standard               |
| **AKS Nodes**    | 1-3 (D4s_v5)     | 2-4 (D4s_v5)      | 3-6 (D8s_v5) + compute |
| **PostgreSQL**   | B2s, 32GB        | D2ds_v5, 64GB     | D4ds_v5, 256GB, HA     |
| **Redis**        | C1 Standard      | C2 Standard       | P2 Premium + cluster   |
| **Backup**       | 7 days           | 14 days           | 30 days, geo-redundant |
| **ACR**          | Single region    | Single region     | Geo-replicated (3 reg) |
| **Monitoring**   | 14 days          | 30 days           | 90 days + alerts       |
| **Alerts**       | None             | Email             | Email + on-call        |
| **TLS**          | No               | Yes               | Yes                    |
| **Estimated/mo** | ~$200-400        | ~$600-1,000       | ~$2,500-5,000          |

## CI/CD Integration

The Terraform code supports GitHub Actions OIDC federated identity for secure, keyless authentication:

1. Enable `github_actions_oidc_enabled = true` in your environment tfvars
2. Set `github_repository` to your GitHub repo (e.g., `my-org/my-repo`)
3. GitHub Actions authenticates to Azure via OIDC — no service principal secrets needed

## Secrets Management

Sensitive values (database passwords, API keys, Redis keys) are stored in **Azure Key Vault**. The Terraform deployment creates the vault and stores initial secrets.

For production:
1. Set `postgresql_admin_password` via environment variable or CI/CD secret
2. Use `terraform.tfvars` with placeholders for non-sensitive values only
3. Import existing secrets into Key Vault post-deployment

## Connecting to AKS

```bash
# After terraform apply
az aks get-credentials --resource-group rg-ahmedetap-prod --name aks-ahmedetap-prod

# Verify
kubectl get nodes
kubectl get pods -n ahmedetap
```

## Destroying

```bash
# Helm chart first (to avoid dangling resources)
terraform destroy -var-file="environments/dev/terraform.tfvars" -target=helm_release.etap_ai

# Then infrastructure
terraform destroy -var-file="environments/dev/terraform.tfvars"
```

**Warning:** `prevent_destroy` is set on the PostgreSQL server. Remove it manually if you intend to destroy the database.

## Contributing

1. Make changes in a feature branch
2. Run `terraform fmt -recursive` before committing
3. Run `terraform validate` to check syntax
4. Update environment tfvars as needed
5. Open a PR with infrastructure changes
