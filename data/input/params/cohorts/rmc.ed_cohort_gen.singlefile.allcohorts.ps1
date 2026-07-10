# =========================
# CONFIG
# =========================

$outputFolder = "C:\lwf\sbx-data-vis\data\input\params\cohorts\ed"
New-Item -ItemType Directory -Force -Path $outputFolder | Out-Null

$outputFile = Join-Path $outputFolder "ed.csv"

# =========================
# COHORTS
# =========================

$rows = @(

    [PSCustomObject]@{
        name        = "ed.psych"
        param       = "filter"
        value       = 'psych_patient_flag == "Yes"'
        description = "Psych ED encounters"
        cohort_file = "ed_cohort_gen.singlefile.psych.nonpsych.ps1"
    }

    [PSCustomObject]@{
        name        = "ed.non_psych"
        param       = "filter"
        value       = 'psych_patient_flag == "No"'
        description = "Non-Psych ED encounters"
        cohort_file = "ed_cohort_gen.singlefile.psych.nonpsych.ps1"
    }
)

# =========================
# OUTPUT
# =========================

$rows | Export-Csv -NoTypeInformation -Path $outputFile -Encoding UTF8

Write-Host "Created psych/non-psych cohort file -> ed_psych.csv"