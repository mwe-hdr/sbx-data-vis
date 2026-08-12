# =========================
# CONFIG
# =========================

$outputFolder = "C:\lwf\sbx-data-vis\data\input\params\cohorts\inpatient"
New-Item -ItemType Directory -Force -Path $outputFolder | Out-Null

$outputFile = Join-Path $outputFolder "inpatient.csv"

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
            name        = "$prefix.all.inpatient"
            param       = "filter"
            value       = "facility_name == `"$loc`""
            description = "All inpatient encounters at $loc"
            cohort_file = "ecu.inpatient.combinedsinglefile.rollup.cohorts.ps1"
        }
    )

    $allRows += $rows
}

# =========================
# EXPORT
# =========================

$allRows |
    Export-Csv `
        -NoTypeInformation `
        -Encoding UTF8 `
        -Path $outputFile

Write-Host "Created consolidated inpatient file -> inpatient_rollup.csv"
Write-Host "Hospitals: $($allRows.Count)"