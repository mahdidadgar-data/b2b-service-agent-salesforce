<#
.SYNOPSIS
    Deactivates products that are not part of Delta's catalog (no DIS- product code), such as the
    sample products a new Developer Edition org comes with (GenWatt generators, installation, SLAs).

.DESCRIPTION
    The product search action (flow Get_Product_Specs) searches all ACTIVE products. Sample products
    would make the agent offer products Delta doesn't sell, so only Delta's own catalog may be active.
    This is data, not metadata, so it is not deployed from Git: run it once per org.

    Default (dry run): lists the active products without a DIS- code and their usage on order lines,
    opportunity products and assets. Changes nothing.
    -Apply: deactivates them (sends only IsActive = false). Stops without changing anything if any of
    them is used. Afterwards verifies that no active product without a DIS- code is left.

    Safe to run more than once: when nothing is found, nothing is done.

.EXAMPLE
    .\scripts\deactivate-sample-products.ps1 -TargetOrg delta-dev            # dry run
    .\scripts\deactivate-sample-products.ps1 -TargetOrg delta-dev -Apply     # deactivate
#>
param(
    [Parameter(Mandatory = $true)][string]$TargetOrg,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'

function Invoke-Soql([string]$Soql) {
    $raw = sf data query --query $Soql --target-org $TargetOrg --json
    $res = ($raw | Out-String) | ConvertFrom-Json
    if ($res.status -ne 0) { throw "Query failed: $($res.message)`nSOQL: $Soql" }
    return $res.result
}

# Products outside Delta's catalog: active, and no DIS- code (an empty code counts as "not DIS-").
$selection = "IsActive = true AND (ProductCode = null OR (NOT ProductCode LIKE 'DIS-%'))"
$found = Invoke-Soql "SELECT Id, ProductCode, Name FROM Product2 WHERE $selection"
Write-Host "Active products without a DIS- code: $($found.totalSize)"
if ($found.totalSize -eq 0) {
    Write-Host "Nothing to do: only Delta's catalog is active."
    exit 0
}

# Usage: a product that is used on an order line, opportunity product or asset is never deactivated.
$idList = ($found.records | ForEach-Object { "'" + $_.Id + "'" }) -join ','
$usage = @{}
foreach ($obj in 'OrderItem', 'OpportunityLineItem', 'Asset') {
    $rows = Invoke-Soql "SELECT Product2Id FROM $obj WHERE Product2Id IN ($idList)"
    foreach ($r in $rows.records) { $usage[$r.Product2Id] = @($usage[$r.Product2Id]) + $obj }
    Write-Host ("  used on {0,-20} {1}" -f $obj, $rows.totalSize)
}
foreach ($p in $found.records) {
    $used = if ($usage.ContainsKey($p.Id)) { ($usage[$p.Id] | Where-Object { $_ } | Group-Object | ForEach-Object { "$($_.Name) x$($_.Count)" }) -join ', ' } else { 'not used' }
    Write-Host ("  {0,-10} {1,-36} {2}" -f $p.ProductCode, $p.Name, $used)
}

if (-not $Apply) {
    Write-Host "`nDry run: nothing changed. Add -Apply to deactivate."
    exit 0
}
if ($usage.Count -gt 0) {
    throw "$($usage.Count) of these products are in use (see above). Nothing changed. Review them by hand."
}

foreach ($p in $found.records) {
    sf data update record --sobject Product2 --record-id $p.Id --values "IsActive=false" --target-org $TargetOrg | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Deactivating $($p.ProductCode) ($($p.Id)) failed. Re-run the script to continue." }
}
$left = Invoke-Soql "SELECT Id FROM Product2 WHERE $selection"
Write-Host "`nDeactivated $($found.totalSize) product(s) (only IsActive sent). Active products without a DIS- code left: $($left.totalSize)."
if ($left.totalSize -ne 0) { exit 1 }
