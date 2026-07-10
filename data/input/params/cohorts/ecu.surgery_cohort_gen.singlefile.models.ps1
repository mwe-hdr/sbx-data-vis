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

    $rows = @(

        # ✅ all ORs excluding Endoscopy + OB
        [PSCustomObject]@{
            name        = "$prefix.all.operatingrooms.excl.endoscopy.and.ob"
            param       = "filter"
            value       = "location == `"$loc`" and or_type not in [`"Obstetrics, Labor, Delivery OR`", `"Endoscopy Lab`"]"
            description = "$loc - Operating rooms excluding Endoscopy and OB"
            cohort_file = "surgery_cohort_gen.singlefile.models.ps1"
        }

        # ✅ Endoscopy only
        [PSCustomObject]@{
            name        = "$prefix.endoscopy"
            param       = "filter"
            value       = "location == `"$loc`" and or_type in [`"Endoscopy Lab`"]"
            description = "$loc - Endoscopy procedures"
            cohort_file = "surgery_cohort_gen.singlefile.models.ps1"
        }

        # ✅ OB only
        [PSCustomObject]@{
            name        = "$prefix.ob"
            param       = "filter"
            value       = "location == `"$loc`" and or_type in [`"Obstetrics, Labor, Delivery OR`"]"
            description = "$loc - Obstetrics operating room procedures"
            cohort_file = "surgery_cohort_gen.singlefile.models.ps1"
        }
    )

    # ✅ accumulate instead of per-hospital file
    $allRows += $rows
}

# ✅ single consolidated CSV
$allRows | Export-Csv -NoTypeInformation -Path $outputFile -Encoding UTF8

Write-Host "Created consolidated surgery file -> surgery.csv"