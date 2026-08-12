# =========================
# CONFIG
# =========================

$outputFolder = "C:\lwf\sbx-data-vis\data\input\params\cohorts\surgery"
New-Item -ItemType Directory -Force -Path $outputFolder | Out-Null

$encounterFile = Join-Path $outputFolder "surgery_alt.csv"
$surgeonFile   = Join-Path $outputFolder "surgery_ts.csv"

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
# ROOM COHORTS
# =========================

$roomCohorts = @(

    @{
        Name        = "cardio_or"
        Room        = "Cardiovascular OR"
        Department  = "Operating Room ECHI"
        Description = "Cardiovascular Operating Room"
    }

    @{
        Name        = "main_or"
        Room        = "Main OR"
        Department  = "Operating Room"
        Description = "Main Operating Room"
    }

    @{
        Name        = "ld_or"
        Room        = "Obstetrics, Labor, Delivery OR"
        Department  = "Labor and Delivery"
        Description = "Labor and delivery Operating Room"
    }
)

# =========================
# PROCESS
# =========================

$encounterRows = @()
$surgeonRows   = @()

foreach ($h in $hospitals) {

    $loc = $h.Name
    $prefix = $h.File

    foreach ($cohort in $roomCohorts) {

        # Encounter Dataset
        $encounterRows += [PSCustomObject]@{
            name        = "$prefix.$($cohort.Name)"
            param       = "filter"
            value       = "facility_name == `"$loc`" and department_desc == `"$($cohort.Department)`""
            description = "$loc - $($cohort.Description)"
            cohort_file = "ecu.surgery.combined.singlefile.rollup.cohorts.ps1"
        }

        # Surgeon Dataset
        $surgeonRows += [PSCustomObject]@{
            name        = "$prefix.$($cohort.Name)"
            param       = "filter"
            value       = "facility_name == `"$loc`" and or_type == `"$($cohort.Room)`""
            description = "$loc - $($cohort.Description)"
            cohort_file = "ecu.surgery.combined.singlefile.rollup.cohorts.ps1"
        }
    }
}

# =========================
# EXPORT
# =========================

$encounterRows |
    Export-Csv -NoTypeInformation -Path $encounterFile -Encoding UTF8

$surgeonRows |
    Export-Csv -NoTypeInformation -Path $surgeonFile -Encoding UTF8

Write-Host "Created -> surgery_alt.csv"
Write-Host "Created -> surgery_ts.csv"