# =========================
# CONFIG
# =========================

$outputFolder = "C:\lwf\sbx-data-vis\data\input\params\cohorts\ed"
New-Item -ItemType Directory -Force -Path $outputFolder | Out-Null

$outputFile = Join-Path $outputFolder "ed.csv"

# =========================
# HOSPITALS
# =========================

$hospitals = @(
    @{ Name = "RL ECUH MEDICAL CENTER HOSPITAL"; File = "med_center" }
    @{ Name = "RL ECUH CHOWAN HOSPITAL"; File = "chowan" }
    @{ Name = "RL OUTER BANKS HEALTH"; File = "outer_banks" }
    @{ Name = "RL ECUH EDGECOMBE HOSPITAL"; File = "edgecombe" }
    @{ Name = "RL ECUH DUPLIN HOSPITAL"; File = "duplin" }
    @{ Name = "RL ECUH BEAUFORT HOSPITAL"; File = "beaufort" }
    @{ Name = "RL ECUH NORTH HOSPITAL"; File = "north" }
    @{ Name = "RL ECUH ROANOKE CHOWAN HOSPITAL"; File = "roanoke_chowan" }
    @{ Name = "RL ECUH BERTIE HOSPITAL"; File = "bertie" }
    @{ Name = "RL SURGICENTER"; File = "surgicenter" }
)

# =========================
# PROCESS
# =========================

$allRows = @()

foreach ($h in $hospitals) {

    $loc = $h.Name
    $prefix = $h.File

    $rows = @(
        [PSCustomObject]@{
            name        = "$prefix.all.emergency"
            param       = "filter"
            value       = "facility_name == `"$loc`""
            description = "All emergency encounters at $loc"
            cohort_file = "ed_cohort_gen.singlefile.models.ps1"
        }
    )

    # ✅ accumulate instead of per-hospital output
    $allRows += $rows
}

# ✅ single consolidated CSV
$allRows | Export-Csv -NoTypeInformation -Path $outputFile -Encoding UTF8

Write-Host "Created consolidated emergency file -> ed.csv"