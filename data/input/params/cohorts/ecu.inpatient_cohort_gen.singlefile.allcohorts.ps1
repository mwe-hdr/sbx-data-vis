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
    @{ Name = "RL SURGICENTER"; File = "surgicenter" }
)

# =========================
# SERVICE LINE GROUPS
# =========================

$neonate = @(
    "Pediatrics",
    "Neonatology",
    "NEWBORN"
)

$ob = @(
    "Obstetrics/Gyn",
    "Obstetrics",
    "Gynecology",
    "Maternal-Fetal Med"
)

# format arrays into CSV-style string for filter
$neonateStr = ($neonate | ForEach-Object { "`"$_`"" }) -join ", "
$obStr      = ($ob | ForEach-Object { "`"$_`"" }) -join ", "

# combined exclusion list
$excludeStr = ($neonate + $ob | ForEach-Object { "`"$_`"" }) -join ", "

# =========================
# PROCESS
# =========================

$allRows = @()

foreach ($h in $hospitals) {

    $loc = $h.Name
    $prefix = $h.File

    $rows = @(

        # ✅ all hospital encounters
        [PSCustomObject]@{
            name        = "$prefix.all.inpatient"
            param       = "filter"
            value       = "hospital_name == `"$loc`""
            description = "$loc - All inpatient encounters"
            cohort_file = "inpatient_cohort_gen.singlefile.allcohorts.ps1"
        }

        # ✅ all service lines excluding neonate + OB
        [PSCustomObject]@{
            name        = "$prefix.all.service.lines.excl.neonate.and.ob"
            param       = "filter"
            value       = "hospital_name == `"$loc`" and service_line not in [$excludeStr]"
            description = "$loc - All service lines excluding Neonate and OB"
            cohort_file = "inpatient_cohort_gen.singlefile.allcohorts.ps1"
        }

        # ✅ neonate services only
        [PSCustomObject]@{
            name        = "$prefix.neonate.services"
            param       = "filter"
            value       = "hospital_name == `"$loc`" and service_line in [$neonateStr]"
            description = "$loc - Neonatal and pediatric-related services"
            cohort_file = "inpatient_cohort_gen.singlefile.allcohorts.ps1"
        }

        # ✅ psychiatry only
        [PSCustomObject]@{
            name        = "$prefix.psychiatry"
            param       = "filter"
            value       = "hospital_name == `"$loc`" and service_line in [`"Psychiatry`"]"
            description = "$loc - Psychiatry services"
            cohort_file = "inpatient_cohort_gen.singlefile.allcohorts.ps1"
        }
    )

    # ✅ accumulate instead of writing per hospital
    $allRows += $rows
}

# ✅ single consolidated CSV
$allRows | Export-Csv -NoTypeInformation -Path $outputFile -Encoding UTF8

Write-Host "Created consolidated inpatient file -> inpatient.csv"