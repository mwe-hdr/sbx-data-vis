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
# PROCESS
# =========================

foreach ($h in $hospitals) {

    $loc = $h.Name

    $rows = @(
        [PSCustomObject]@{
            name        = "$($h.File).all.emergency"
            param       = "filter"
            value       = "hospital_name == `"$loc`""
            description = "All emergency encounters at $loc"
        }
    )

    $outputPath = Join-Path $outputFolder "$($h.File).csv"

    $rows | Export-Csv -NoTypeInformation -Path $outputPath

    Write-Host "Created emergency file -> $($h.File).csv"
}