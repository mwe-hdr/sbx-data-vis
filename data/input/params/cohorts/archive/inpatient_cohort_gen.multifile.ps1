# =========================
# CONFIG
# =========================

$outputFolder = "C:\lwf\sbx-data-vis\data\input\params\cohorts"

New-Item -ItemType Directory -Force -Path $outputFolder | Out-Null

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

foreach ($h in $hospitals) {

    $loc = $h.Name

    $rows = @(

        # all service lines excluding neonate + OB
        [PSCustomObject]@{
            name        = "$($h.File).all.service.lines.excl.neonate.and.ob"
            param       = "filter"
            value       = "hospital_name == `"$loc`" and service_line not in [$excludeStr]"
            description = "$loc - All service lines excluding Neonate and OB"
        }

        # neonate services only
        [PSCustomObject]@{
            name        = "$($h.File).neonate.services.only"
            param       = "filter"
            value       = "hospital_name == `"$loc`" and service_line in [$neonateStr]"
            description = "$loc - Neonatal and pediatric-related services"
        }

        # psychiatry only
        [PSCustomObject]@{
            name        = "$($h.File).psychiatry.only"
            param       = "filter"
            value       = "hospital_name == `"$loc`" and service_line in [`"Psychiatry`"]"
            description = "$loc - Psychiatry services"
        }
    )

    $outputPath = Join-Path $outputFolder "$($h.File).csv"

    $rows | Export-Csv -NoTypeInformation -Path $outputPath

    Write-Host "Created inpatient file -> $($h.File).csv"
}