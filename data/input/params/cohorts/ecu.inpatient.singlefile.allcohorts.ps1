# =========================
# CONFIG
# =========================

$outputFolder = "C:\lwf\sbx-data-vis\data\input\params\cohorts\inpatient"

New-Item -ItemType Directory -Force -Path $outputFolder | Out-Null

$encounterFile = Join-Path $outputFolder "inpatient.csv"

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
)

# =========================
# COHORT DEFINITIONS
# =========================

$cohorts = @(

    @{
        Name = "emergency"
        Description = "Emergency Department"
        Departments = @(
            "Emergency Department",
            "BFT Emergency Department"
        )
    }

    @{
        Name = "pediatric_emergency"
        Description = "Pediatric Emergency Department"
        Departments = @(
            "Childrens ED"
        )
    }

    @{
        Name = "ob_emergency"
        Description = "Obstetric Emergency Department"
        Departments = @(
            "OB Emergency Department"
        )
    }

    @{
        Name = "mother_baby"
        Description = "Mother Baby Unit"
        Departments = @(
            "1 West Mother Baby",
            "OB-GYN",
            "BFT OB-GYN"
        )
    }

    @{
        Name = "labor_delivery"
        Description = "Labor and Delivery"
        Departments = @(
            "Labor and Delivery",
            "Labor and Delivery Triage"
        )
    }

    @{
        Name = "newborn_nursery"
        Description = "Newborn Nursery"
        Departments = @(
            "Neo I-NBN",
            "BFT Neo I-NBN"
        )
    }

    @{
        Name = "nicu"
        Description = "Neonatal Intensive Care Unit"
        Departments = @(
            "Neo IV-NICU"
        )
    }

    @{
        Name = "neo_intermediate"
        Description = "Neonatal Intermediate Care"
        Departments = @(
            "Neo III-Neo Intermediate"
        )
    }

    @{
        Name = "pediatrics"
        Description = "Pediatric Acute Care"
        Departments = @(
            "Pediatrics"
        )
    }

    @{
        Name = "picu"
        Description = "Pediatric Intensive Care Unit"
        Departments = @(
            "Pediatric ICU"
        )
    }

    @{
        Name = "behavioral_health"
        Description = "Behavioral Health"
        Departments = @(
            "Behavioral Health Services",
            "Adult Psych"
        )
    }

    @{
        Name = "icu"
        Description = "Intensive Care Unit"
        Departments = @(
            "ICU-CCU",
            "BFT ICU-CCU"
        )
    }

    @{
        Name = "micu"
        Description = "Medical Intensive Care Unit"
        Departments = @(
            "MICU"
        )
    }

    @{
        Name = "sicu"
        Description = "Surgical Intensive Care Unit"
        Departments = @(
            "SICU"
        )
    }

    @{
        Name = "cicu"
        Description = "Cardiac Intensive Care Unit"
        Departments = @(
            "CICU"
        )
    }

    @{
        Name = "cvicu"
        Description = "Cardiovascular Intensive Care Unit"
        Departments = @(
            "CVICU"
        )
    }

    @{
        Name = "neuro_icu"
        Description = "Neuro Intensive Care Unit"
        Departments = @(
            "Neurosciences ICU"
        )
    }

    @{
        Name = "trauma_surgical_icu"
        Description = "Trauma Surgical Intensive Care Unit"
        Departments = @(
            "TSIU"
        )
    }

    @{
        Name = "step_down"
        Description = "Step Down Unit"
        Departments = @(
            "Medical Step Down Unit"
        )
    }

    @{
        Name = "progressive_care"
        Description = "Progressive Care Unit"
        Departments = @(
            "2 North Progressive Care"
        )
    }

    @{
        Name = "clinical_intermediate"
        Description = "Clinical Intermediate Unit"
        Departments = @(
            "CIU"
        )
    }

    @{
        Name = "cardiovascular_intermediate"
        Description = "Cardiovascular Intermediate Unit"
        Departments = @(
            "CVIU"
        )
    }

    @{
        Name = "neuro_intermediate"
        Description = "Neuroscience Intermediate Unit"
        Departments = @(
            "Neurosciences IU-Gen"
        )
    }

    @{
        Name = "medical_surgical"
        Description = "Medical Surgical Unit"
        Departments = @(
            "Medical-Surgical",
            "Medical/Surgical",
            "2 South B",
            "3 East"
        )
    }

    @{
        Name = "medical_unit"
        Description = "Medical Unit"
        Departments = @(
            "Medical Unit",
            "BFT Medical Unit"
        )
    }

    @{
        Name = "medical_intermediate"
        Description = "Medical Intermediate Unit"
        Departments = @(
            "MIU"
        )
    }

    @{
        Name = "surgical_unit"
        Description = "Surgical Unit"
        Departments = @(
            "Surgical Unit",
            "BFT Surgical Unit"
        )
    }

    @{
        Name = "orthopedics"
        Description = "Orthopedic Unit"
        Departments = @(
            "Orthopedics"
        )
    }

    @{
        Name = "complex_care"
        Description = "Complex Care Unit"
        Departments = @(
            "Hybrid Complex Medical Unit"
        )
    }

    @{
        Name = "rehabilitation"
        Description = "Rehabilitation Unit"
        Departments = @(
            "Rehab Medicine Nursing",
            "Rehab Comprehensive Care"
        )
    }

    @{
        Name = "neuro_rehabilitation"
        Description = "Neurological Rehabilitation Unit"
        Departments = @(
            "Rehab Neurosciences Nursing"
        )
    }

    @{
        Name = "medical_oncology"
        Description = "Medical Oncology"
        Departments = @(
            "Cancer Ctr Medical Oncology"
        )
    }

    @{
        Name = "surgical_oncology"
        Description = "Surgical Oncology"
        Departments = @(
            "Cancer Ctr Surgical Oncology",
            "Surgery Oncology Clinic"
        )
    }

    @{
        Name = "family_medicine"
        Description = "Family Medicine"
        Departments = @(
            "Family Medicine"
        )
    }

    @{
        Name = "palliative_care"
        Description = "Palliative Care Unit"
        Departments = @(
            "Palliative Care Unit"
        )
    }

    @{
        Name = "cardiology_outpatient"
        Description = "Cardiology Outpatient Unit"
        Departments = @(
            "Cardiology Outpatient Unit"
        )
    }

    @{
        Name = "observation"
        Description = "Observation Unit"
        Departments = @(
            "Observation Unit"
        )
    }
)

# =========================
# PROCESS
# =========================

$rows = @()

foreach ($hospital in $hospitals) {

    foreach ($cohort in $cohorts) {

        $departmentList = (
            $cohort.Departments |
            ForEach-Object { "`"$_`"" }
        ) -join ", "

        $rows += [PSCustomObject]@{
            name        = "$($hospital.File).$($cohort.Name)"
            param       = "filter"
            value       = "facility_name == `"$($hospital.Name)`" and department_desc in [$departmentList]"
            description = "$($hospital.Name) - $($cohort.Description)"
            cohort_file = "ecu.inpatient.singlefile.allcohorts.ps1"
        }
    }
}

# =========================
# EXPORT
# =========================

$rows |
    Export-Csv `
        -NoTypeInformation `
        -Encoding UTF8 `
        -Path $encounterFile

Write-Host "Created -> inpatient.csv"
Write-Host "Cohorts: $($rows.Count)"