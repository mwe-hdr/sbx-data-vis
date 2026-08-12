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
# MATERNAL SERVICE LINES
# =========================

$maternalServices = @(
    "Pediatrics",
    "Neonatology",
    "NEWBORN",
    "Obstetrics/Gyn",
    "Obstetrics",
    "Gynecology",
    "Maternal-Fetal Med"
)

$maternalServicesStr = (
    $maternalServices |
    ForEach-Object { "`"$_`"" }
) -join ", "

# =========================
# PROCESS
# =========================

$allRows = @()

foreach ($h in $hospitals) {

    $loc = $h.Name
    $prefix = $h.File

    $rows = @(

        # ✅ All Inpatient
        [PSCustomObject]@{
            name        = "$prefix.all.inpatient"
            param       = "filter"
            value       = "hospital_name == `"$loc`" and patient_class == `"Inpatient`""
            description = "$loc - All Inpatient"
            cohort_file = "inpatient_cohort_gen.singlefile.allcohorts.ps1"
        }

        # ✅ Maternal Services
        [PSCustomObject]@{
            name        = "$prefix.maternal.services"
            param       = "filter"
            value       = "hospital_name == `"$loc`" and patient_class == `"Inpatient`" and service_line in [$maternalServicesStr]"
            description = "$loc - Maternal Services"
            cohort_file = "inpatient_cohort_gen.singlefile.allcohorts.ps1"
        }

        # ✅ Inpatient Excluding Maternal Services
        [PSCustomObject]@{
            name        = "$prefix.inpatient.excl.maternal.services"
            param       = "filter"
            value       = "hospital_name == `"$loc`" and patient_class == `"Inpatient`" and service_line not in [$maternalServicesStr]"
            description = "$loc - Inpatient Excluding Maternal Services"
            cohort_file = "inpatient_cohort_gen.singlefile.allcohorts.ps1"
        }

        # ✅ Psychiatry Inpatient
        [PSCustomObject]@{
            name        = "$prefix.psychiatry.inpatient"
            param       = "filter"
            value       = "hospital_name == `"$loc`" and patient_class == `"Psych Inpatient`""
            description = "$loc - Psychiatry Inpatient"
            cohort_file = "inpatient_cohort_gen.singlefile.allcohorts.ps1"
        }

        # ✅ Rehab Inpatient
        [PSCustomObject]@{
            name        = "$prefix.rehab.inpatient"
            param       = "filter"
            value       = "hospital_name == `"$loc`" and patient_class == `"Rehab Inpatient`""
            description = "$loc - Rehab Inpatient"
            cohort_file = "inpatient_cohort_gen.singlefile.allcohorts.ps1"
        }

        # ✅ Observation
        [PSCustomObject]@{
            name        = "$prefix.observation"
            param       = "filter"
            value       = "hospital_name == `"$loc`" and patient_class == `"Observation`""
            description = "$loc - Observation"
            cohort_file = "inpatient_cohort_gen.singlefile.allcohorts.ps1"
        }
    )

    $allRows += $rows
}

# =========================
# EXPORT
# =========================

$allRows |
    Export-Csv -NoTypeInformation -Path $outputFile -Encoding UTF8

Write-Host "Created consolidated inpatient file -> inpatient.csv"