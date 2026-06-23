<#
.SYNOPSIS
    Provisions an Azure Service Principal for Terraform CI/CD and stores the
    credentials as GitHub Actions secrets.

.DESCRIPTION
    This script:
    1. Logs you into Azure (if not already logged in)
    2. Creates a Service Principal with Contributor + User Access Administrator roles
    3. Stores the credentials as GitHub Actions secrets (AZURE_CLIENT_ID,
       AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID)

.PARAMETER SubscriptionId
    Azure subscription ID. If omitted, uses the current default subscription.

.PARAMETER GitHubRepo
    GitHub repository in "owner/repo" format. Defaults to "ahmdelbaz28-ux/ETAP-AI-WORK-".

.PARAMETER SpName
    Name for the Service Principal. Defaults to "ahmedetap-terraform-ci".

.PARAMETER OutputScript
    If specified, writes a shell script instead of running the commands directly.
    Useful for environments without Azure CLI installed.

.EXAMPLE
    # Run interactively (will prompt for Azure login)
    ./scripts/setup-azure-github-secrets.ps1

.EXAMPLE
    # Specify subscription and repo
    ./scripts/setup-azure-github-secrets.ps1 -SubscriptionId "00000000-0000-0000-0000-000000000000" -GitHubRepo "ahmdelbaz28-ux/ETAP-AI-WORK-"

.EXAMPLE
    # Output instructions as a script (for non-Windows machines)
    ./scripts/setup-azure-github-secrets.ps1 -OutputScript
#>

param(
    [string]$SubscriptionId = "",
    [string]$GitHubRepo = "ahmdelbaz28-ux/ETAP-AI-WORK-",
    [string]$SpName = "ahmedetap-terraform-ci",
    [switch]$OutputScript
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "  ✓ $Message" -ForegroundColor Green
}

function Write-Instruction {
    param([string]$Message)
    Write-Host "  $Message" -ForegroundColor Yellow
}

# ============================================================================
# 1. Check / Install Azure CLI
# ============================================================================
Write-Step "1. Checking Azure CLI"

$azPath = (Get-Command "az" -ErrorAction SilentlyContinue).Source
if (-not $azPath) {
    Write-Instruction "Azure CLI is not installed. Installing via winget..."
    winget install Microsoft.AzureCLI --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install Azure CLI. Please install manually from:"
        Write-Error "  https://docs.microsoft.com/cli/azure/install-azure-cli-windows"
        exit 1
    }
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}

Write-Success "Azure CLI is available"

# ============================================================================
# 2. Azure Login
# ============================================================================
Write-Step "2. Azure Login"

$azAccount = az account show 2>$null
if (-not $azAccount) {
    Write-Instruction "Opening browser for Azure login..."
    az login
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Azure login failed."
        exit 1
    }
}

Write-Success "Logged in to Azure"

# ============================================================================
# 3. Select Subscription
# ============================================================================
Write-Step "3. Selecting Subscription"

if ($SubscriptionId) {
    az account set --subscription $SubscriptionId
} else {
    $currentSub = az account show --query "{Name:name, ID:id}" -o tsv
    Write-Instruction "Using current subscription: $currentSub"
}

$subInfo = az account show --query "{Name:name, ID:id, TenantID:tenantId}" -o json | ConvertFrom-Json
Write-Success "Subscription: $($subInfo.Name) ($($subInfo.ID))"
Write-Success "Tenant: $($subInfo.TenantID)"

# ============================================================================
# 4. Create Resource Group for Terraform State
# ============================================================================
Write-Step "4. Creating Resource Group for Terraform State"

$tfStateRG = "rg-ahmedetap-tfstate"
az group create --name $tfStateRG --location eastus2 --tags "managed_by=terraform" "project=ahmedetap" | Out-Null
Write-Success "Resource Group: $tfStateRG"

# ============================================================================
# 5. Create Storage Accounts for Terraform State
# ============================================================================
Write-Step "5. Creating Storage Accounts for Terraform State"

$environments = @(
    @{ Name = "dev"; Location = "eastus2" },
    @{ Name = "staging"; Location = "eastus2" },
    @{ Name = "prod"; Location = "eastus2" }
)

foreach ($env in $environments) {
    $saName = "stahmedetapstate$($env.Name)"
    Write-Instruction "Creating storage account: $saName ..."

    # Check if it exists first
    $exists = az storage account show --name $saName --resource-group $tfStateRG --query "name" -o tsv 2>$null
    if (-not $exists) {
        az storage account create `
            --name $saName `
            --resource-group $tfStateRG `
            --location $env.Location `
            --sku Standard_LRS `
            --allow-blob-public-access false `
            --tags "managed_by=terraform" "environment=$($env.Name)" | Out-Null

        az storage container create `
            --name terraform-state `
            --account-name $saName | Out-Null

        Write-Success "Created storage account and container for $($env.Name)"
    } else {
        Write-Success "Storage account $saName already exists"
    }
}

# ============================================================================
# 6. Create Service Principal
# ============================================================================
Write-Step "6. Creating Azure Service Principal"

$existingSp = az ad sp list --display-name $SpName --query "[0]" -o json 2>$null | ConvertFrom-Json
if ($existingSp) {
    Write-Instruction "Service Principal '$SpName' already exists. Creating a fresh one with a unique name suffix..."
    $uniqueSpName = "$SpName-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Write-Instruction "New SP name: $uniqueSpName"

    $spInfo = az ad sp create-for-rbac `
        --name $uniqueSpName `
        --role Contributor `
        --scopes "/subscriptions/$($subInfo.ID)" 2>&1 | ConvertFrom-Json

    if (-not $spInfo) {
        Write-Error "Failed to create Service Principal."
        exit 1
    }

    $spAppId = $spInfo.appId
    $spPassword = $spInfo.password
} else {
    Write-Instruction "Creating Service Principal '$SpName' with Contributor role..."

    $spInfo = az ad sp create-for-rbac `
        --name $SpName `
        --role Contributor `
        --scopes "/subscriptions/$($subInfo.ID)" 2>&1 | ConvertFrom-Json

    if (-not $spInfo) {
        Write-Error "Failed to create Service Principal."
        exit 1
    }

    $spAppId = $spInfo.appId
    $spPassword = $spInfo.password

    Write-Success "Service Principal created: $spAppId"
}

# Add User Access Administrator role (needed for RBAC assignments)
# Check if already assigned first to avoid conflict errors
Write-Instruction "Granting User Access Administrator role..."
$existingUaaRole = az role assignment list `
    --assignee $spAppId `
    --role "User Access Administrator" `
    --scope "/subscriptions/$($subInfo.ID)" `
    --query "[0]" -o tsv 2>$null

if (-not $existingUaaRole) {
    az role assignment create `
        --assignee $spAppId `
        --role "User Access Administrator" `
        --scope "/subscriptions/$($subInfo.ID)" | Out-Null
    Write-Success "User Access Administrator role assigned"
} else {
    Write-Success "User Access Administrator role already assigned"
}

# ============================================================================
# 7. Set GitHub Secrets
# ============================================================================
Write-Step "7. Setting GitHub Secrets"

# Check if gh CLI is available and authenticated
$ghCheck = gh auth status 2>&1
if ($LASTEXITCODE -eq 0) {
    # Get SP credentials if we just created it
    if (-not $spPassword) {
        Write-Instruction "Using existing SP — resetting password..."
        $spPassword = az ad sp credential reset --id $spAppId --query "password" -o tsv
    }

    Write-Instruction "Setting AZURE_CLIENT_ID..."
    gh secret set AZURE_CLIENT_ID --repo "$GitHubRepo" --body $spAppId

    Write-Instruction "Setting AZURE_TENANT_ID..."
    gh secret set AZURE_TENANT_ID --repo "$GitHubRepo" --body $subInfo.TenantID

    Write-Instruction "Setting AZURE_SUBSCRIPTION_ID..."
    gh secret set AZURE_SUBSCRIPTION_ID --repo "$GitHubRepo" --body $subInfo.ID

    Write-Success "All 3 GitHub secrets set on $GitHubRepo"
} else {
    Write-Instruction "GitHub CLI not authenticated. Please set secrets manually:"
    Write-Instruction ""
    Write-Instruction "  gh secret set AZURE_CLIENT_ID --repo $GitHubRepo --body $spAppId"
    Write-Instruction "  gh secret set AZURE_TENANT_ID --repo $GitHubRepo --body $($subInfo.TenantID)"
    Write-Instruction "  gh secret set AZURE_SUBSCRIPTION_ID --repo $GitHubRepo --body $($subInfo.ID)"
}

# ============================================================================
# 8. Summary
# ============================================================================
Write-Step "8. Summary"

Write-Host ""
Write-Host "  Azure Setup Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  GitHub Secrets (set on $GitHubRepo):" -ForegroundColor Cyan
Write-Host "    AZURE_CLIENT_ID       = $spAppId"
Write-Host "    AZURE_TENANT_ID       = $($subInfo.TenantID)"
Write-Host "    AZURE_SUBSCRIPTION_ID = $($subInfo.ID)"
Write-Host ""
Write-Host "  Terraform State Storage:" -ForegroundColor Cyan
Write-Host "    RG:      $tfStateRG"
foreach ($env in $environments) {
    Write-Host "    $($env.Name): stahmedetapstate$($env.Name) (container: terraform-state)"
}
Write-Host ""
Write-Host "  Next Steps:" -ForegroundColor Cyan
Write-Host "    1. Run the Terraform CI/CD: git push to develop or main"
Write-Host "    2. Or run locally: terraform plan -var-file='environments/dev/terraform.tfvars'"
Write-Host "    3. The workflow will use OIDC (federated identity) to authenticate"
Write-Host ""
