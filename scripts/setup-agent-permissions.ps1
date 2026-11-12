<#
.SYNOPSIS
    Gives the Agentforce agent user its least-privilege permission set.

.DESCRIPTION
    Permission set assignments are data, not metadata, so they are not deployed from Git.
    Run this once per org after deploying force-app (Delta_Agent_Access must exist in the org).

    1. Assigns Delta_Agent_Access to the agent user (skipped if it is already assigned).
    2. Removes Delta_Data_Access (the human/admin permission set) from that user only. It looks up
       the PermissionSetAssignment and deletes it only if exactly one record matches.
    3. Prints the agent user's final permission set assignments.

    Safe to run more than once.

.EXAMPLE
    .\scripts\setup-agent-permissions.ps1 -AgentUsername "delta_service_agent@<org-id>.ext" -TargetOrg delta-dev
#>
param(
    [Parameter(Mandatory = $true)][string]$AgentUsername,
    [Parameter(Mandatory = $true)][string]$TargetOrg
)

$ErrorActionPreference = 'Stop'

# The username goes into SOQL, so only accept characters a Salesforce username can contain.
if ($AgentUsername -notmatch '^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+$') {
    throw "AgentUsername '$AgentUsername' does not look like a Salesforce username."
}

function Invoke-Soql([string]$Soql) {
    $raw = sf data query --query $Soql --target-org $TargetOrg --json
    $res = ($raw | Out-String) | ConvertFrom-Json
    if ($res.status -ne 0) { throw "Query failed: $($res.message)`nSOQL: $Soql" }
    return $res.result
}

# 0. The agent user must exist exactly once.
$users = Invoke-Soql "SELECT Id, Username FROM User WHERE Username = '$AgentUsername'"
if ($users.totalSize -ne 1) { throw "Expected exactly 1 user '$AgentUsername' in $TargetOrg, found $($users.totalSize)." }
$userId = $users.records[0].Id
Write-Host "Agent user: $AgentUsername ($userId)"

# 1. Assign Delta_Agent_Access (skip if already assigned).
$agentPsa = Invoke-Soql "SELECT Id FROM PermissionSetAssignment WHERE AssigneeId = '$userId' AND PermissionSet.Name = 'Delta_Agent_Access'"
if ($agentPsa.totalSize -ge 1) {
    Write-Host "Delta_Agent_Access: already assigned, nothing to do."
} else {
    sf org assign permset --name Delta_Agent_Access --on-behalf-of $AgentUsername --target-org $TargetOrg
    if ($LASTEXITCODE -ne 0) { throw "Assigning Delta_Agent_Access failed. Is the permission set deployed?" }
}

# 2. Remove Delta_Data_Access from this user only: delete only if exactly one assignment matches.
$dataPsa = Invoke-Soql "SELECT Id FROM PermissionSetAssignment WHERE AssigneeId = '$userId' AND PermissionSet.Name = 'Delta_Data_Access'"
switch ($dataPsa.totalSize) {
    0 { Write-Host "Delta_Data_Access: not assigned to the agent user, nothing to remove." }
    1 {
        $psaId = $dataPsa.records[0].Id
        sf data delete record --sobject PermissionSetAssignment --record-id $psaId --target-org $TargetOrg
        if ($LASTEXITCODE -ne 0) { throw "Removing Delta_Data_Access ($psaId) failed." }
        Write-Host "Delta_Data_Access: removed from the agent user (assignment $psaId)."
    }
    default { throw "Expected 0 or 1 Delta_Data_Access assignment, found $($dataPsa.totalSize). Nothing deleted." }
}

# 3. Final state. No ORDER BY PermissionSet.Name: with it, the query returned fewer rows (Step 6a).
$final = Invoke-Soql "SELECT PermissionSet.Name FROM PermissionSetAssignment WHERE AssigneeId = '$userId'"
Write-Host "`nPermission set assignments of $AgentUsername ($($final.totalSize)):"
$final.records | ForEach-Object { Write-Host "  $($_.PermissionSet.Name)" }
