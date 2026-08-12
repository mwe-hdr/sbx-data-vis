# =========================
# CONFIG
# =========================

$outputFolder = "C:\lwf\sbx-data-vis\data\input\params\cohorts\surgery"
New-Item -ItemType Directory -Force -Path $outputFolder | Out-Null

$encounterFile = Join-Path $outputFolder "surgery_encounter.csv"
$surgeonFile   = Join-Path $outputFolder "surgery_surgeon.csv"

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
# COHORTS
# =========================

$cohorts = @(

    @{
        Name = "cardiac_thoracic"
        Room = "Cardiovascular OR"
        Specialty = "Cardiac & Thoracic Surgery"
        Values = @(
            "Cardiac Surgery",
            "Cardiothoracic Surgery",
            "Thoracic Surgery",
            "Thoracic Diseases",
            "Cardiology",
            "Clinical Cardiac Electrophysiology",
            "Cardiovascular Disease"
        )
    }

    @{
        Name = "vascular"
        Room = "Cardiovascular OR"
        Specialty = "Vascular Surgery"
        Values = @(
            "Vascular Surgery"
        )
    }

    @{
        Name = "orthopedic"
        Room = "Main OR"
        Specialty = "Orthopedic Surgery"
        Values = @(
            "Orthopaedic Surgery"
        )
    }

    @{
        Name = "general_surgery"
        Room = "Main OR"
        Specialty = "General Surgery"
        Values = @(
            "General Surgery",
            "Surgery",
            "Surgical Oncology",
            "Trauma Surgery",
            "Colon & Rectal Surgery"
        )
    }

    @{
        Name = "neurosurgery"
        Room = "Main OR"
        Specialty = "Neurosurgery"
        Values = @(
            "Neurological Surgery"
        )
    }

    @{
        Name = "obgyn"
        Room = "Obstetrics, Labor, Delivery OR"
        Specialty = "Obstetrics-Gynecology"
        Values = @(
            "Obstetrics/Gynecology"
        )
    }

    @{
        Name = "maternal_fetal"
        Room = "Obstetrics, Labor, Delivery OR"
        Specialty = "Maternal & Fetal Medicine"
        Values = @(
            "Maternal & Fetal Medicine"
        )
    }

    @{
        Name = "gyn_oncology"
        Room = "Main OR"
        Specialty = "Gynecologic Oncology"
        Values = @(
            "Gynecolgic Oncology"
        )
    }

    @{
        Name = "urology"
        Room = "Main OR"
        Specialty = "Urologic Surgery"
        Values = @(
            "Urology"
        )
    }

    @{
        Name = "plastic"
        Room = "Main OR"
        Specialty = "Plastic Surgery"
        Values = @(
            "Plastic Surgery"
        )
    }

    @{
        Name = "ent"
        Room = "Main OR"
        Specialty = "ENT Surgery"
        Values = @(
            "Ent-Otolaryngology",
            "Otolaryngology"
        )
    }

    @{
        Name = "podiatry"
        Room = "Main OR"
        Specialty = "Podiatric Surgery"
        Values = @(
            "Podiatry"
        )
    }

    @{
        Name = "pediatric_surgery"
        Room = "Main OR"
        Specialty = "Pediatric Surgery"
        Values = @(
            "Pediatric Surgery"
        )
    }

    @{
        Name = "transplant"
        Room = "Main OR"
        Specialty = "Transplant Surgery"
        Values = @(
            "Transplant",
            "Transplant Surgery"
        )
    }

    @{
        Name = "critical_care"
        Room = "Main OR"
        Specialty = "Surgical Critical Care"
        Values = @(
            "Surgical Critical Care"
        )
    }

    @{
        Name = "ophthalmology"
        Room = "Main OR"
        Specialty = "Ophthalmic Surgery"
        Values = @(
            "Ophthalmology"
        )
    }

    @{
        Name = "oral_dental"
        Room = "Main OR"
        Specialty = "Oral & Dental Surgery"
        Values = @(
            "Oral Surgery",
            "Dental Surgery",
            "Dental General Practice",
            "Dentistry, Pedodontics"
        )
    }

    @{
        Name = "pediatric_medicine"
        Room = "Main OR"
        Specialty = "Pediatric Medicine & Surgery"
        Values = @(
            "Pediatrics",
            "Pediatric Gastroenterolgy",
            "Pediatric Hematology/Oncology",
            "Pediatric Nephrology",
            "Pediatrics, Pulmonary"
        )
    }

    @{
        Name = "perioperative"
        Room = "Main OR"
        Specialty = "Critical Care & Perioperative"
        Values = @(
            "Critical Care Medicine",
            "Pain Medicine",
            "Anesthesiology"
        )
    }

    @{
        Name = "medical_specialties"
        Room = "Main OR"
        Specialty = "Medical Procedural Specialties"
        Values = @(
            "Internal Medicine",
            "Family Medicine",
            "Pulmonary Medicine"
        )
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

    foreach ($cohort in $cohorts) {

        $specialtyList = ($cohort.Values | ForEach-Object { "`"$_`"" }) -join ", "

        $department = switch ($cohort.Room) {
            "Cardiovascular OR" { "Operating Room ECHI" }
            "Obstetrics, Labor, Delivery OR" { "Labor and Delivery" }
            default { "Operating Room" }
        }

        # Encounter Dataset (facility + department + encounter specialty)

        $encounterRows += [PSCustomObject]@{
            name        = "$prefix.$($cohort.Name)"
            param       = "filter"
            value       = "facility_name == `"$loc`" and department_desc == `"$department`" and encounter_primary_surgeon_specialty in [$specialtyList]"
            description = "$loc - $($cohort.Specialty)"
            cohort_file = "surgery_cohort_gen.singlefile.models.ps1"
        }

        # Surgeon Dataset (facility + or_type + surgeon specialty)

        $surgeonRows += [PSCustomObject]@{
            name        = "$prefix.$($cohort.Name)"
            param       = "filter"
            value       = "facility_name == `"$loc`" and or_type == `"$($cohort.Room)`" and surgeon_specialty in [$specialtyList]"
            description = "$loc - $($cohort.Specialty)"
            cohort_file = "surgery_cohort_gen.singlefile.models.ps1"
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

Write-Host "Created -> surgery_encounter.csv"
Write-Host "Created -> surgery_surgeon.csv"