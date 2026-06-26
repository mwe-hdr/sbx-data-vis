# =========================
# CONFIG
# =========================

$outputFolder = "C:\lwf\sbx-data-vis\data\input\params\cohorts\surgery"

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
# PROCESS
# =========================

foreach ($h in $hospitals) {

    $loc = $h.Name

    $rows = @(

        # all ORs excluding Endoscopy + OB
        [PSCustomObject]@{
            name        = "all.operatingrooms.excl.endoscopy.and.ob"
            param       = "filter"
            value       = "location == `"$loc`" and or_room not in [`"Obstetrics, Labor, Delivery OR`", `"Endoscopy Lab`"]"
            description = "$loc - Operating rooms excluding Endoscopy and OB"
        }

        # Endoscopy only
        [PSCustomObject]@{
            name        = "endoscopy"
            param       = "filter"
            value       = "location == `"$loc`" and or_room in [`"Endoscopy Lab`"]"
            description = "$loc - Endoscopy procedures"
        }

        # OB only
        [PSCustomObject]@{
            name        = "ob"
            param       = "filter"
            value       = "location == `"$loc`" and or_room in [`"Obstetrics, Labor, Delivery OR`"]"
            description = "$loc - Obstetrics operating room procedures"
        }
    )

    $outputPath = Join-Path $outputFolder "$($h.File).csv"

    $rows | Export-Csv -NoTypeInformation -Path $outputPath

    Write-Host "Created surgery file -> $($h.File).csv"
}