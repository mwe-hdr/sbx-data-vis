# =========================
# CONFIG
# =========================

$outputFolder = "C:\lwf\sbx-data-vis\data\input\params\cohorts\surgery"
New-Item -ItemType Directory -Force -Path $outputFolder | Out-Null

$outputFile = Join-Path $outputFolder "surgery.csv"

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

    $row = [PSCustomObject]@{
        name        = "$prefix.all.surgery"
        param       = "filter"
        value       = "location == `"$loc`""
        description = "$loc - All surgical encounters"
        cohort_file = "surgery_cohort_gen.singlefile.highlevel.ps1"
    }

    $allRows += $row
}

# =========================
# OUTPUT
# =========================

$allRows | Export-Csv -NoTypeInformation -Path $outputFile -Encoding UTF8

Write-Host "Created simplified surgery cohort file -> surgery.csv"