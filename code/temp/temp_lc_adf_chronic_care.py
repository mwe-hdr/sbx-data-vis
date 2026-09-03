import re
import pandas as pd

SOURCE_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf_20260824\CHRONIC_CARE.csv"
OUTPUT_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf_chronic_care.csv"

UNKNOWN_SEVERITY = "UNKNOWN"

SEVERITY_ORDER = {
    "HIGH": 1,
    "MODERATE": 2,
    "LOW": 3,
    "UNKNOWN": 99
}

SEVERITY_CROSSWALK = {

    # =========================================================================
    # CARDIOVASCULAR
    # =========================================================================

    "401.0": "MODERATE",   # Malignant Hypertension
    "401.9": "LOW",        # Hypertension NOS

    "402": "MODERATE",     # Hypertensive Heart Disease
    "402.9": "MODERATE",

    "410.8": "HIGH",       # Acute MI (STEMI)
    "410.9": "HIGH",

    "413.9": "MODERATE",   # Angina
    "414.05": "HIGH",      # CAD w/ Bypass

    "416.9": "HIGH",       # Chronic Pulmonary Heart Disease

    "424.0": "MODERATE",   # Mitral Valve Disorder
    "424.1": "MODERATE",   # Aortic Valve Disorder

    "427": "MODERATE",     # Dysrhythmias
    "427.31": "HIGH",      # Atrial Fibrillation
    "427.89": "MODERATE",
    "427.9": "MODERATE",

    "428.0": "HIGH",       # CHF
    "428.9": "HIGH",

    "429.2": "HIGH",       # ASCVD
    "429.9": "MODERATE",

    "440.9": "HIGH",       # Atherosclerosis
    "442.9": "HIGH",       # Aneurysm
    "447.9": "HIGH",       # Arterial Disease

    "453.4": "HIGH",       # DVT
    "458.9": "LOW",        # Hypotension

    "785.2": "LOW",        # Cardiac Murmur

    # =========================================================================
    # ENDOCRINE / METABOLIC
    # =========================================================================

    "242.9": "MODERATE",   # Thyrotoxicosis

    "244": "LOW",
    "244.1": "LOW",
    "244.8": "LOW",
    "244.9": "LOW",

    "250": "MODERATE",
    "250.01": "MODERATE",
    "250.02": "MODERATE",

    "250.41": "HIGH",
    "250.62": "HIGH",
    "250.9": "HIGH",
    "250.91": "HIGH",

    "272.0": "LOW",
    "272.4": "LOW",

    "274": "LOW",
    "274.9": "LOW",

    # =========================================================================
    # RENAL
    # =========================================================================

    "403": "HIGH",

    "584": "HIGH",
    "585": "HIGH",
    "585.6": "HIGH",
    "585.9": "HIGH",
    "586": "HIGH",

    "753.12": "MODERATE",

    # =========================================================================
    # RESPIRATORY
    # =========================================================================

    "000.7": "UNKNOWN",    

    "415.19": "HIGH",

    "493.02": "MODERATE",
    "493.2": "HIGH",
    "493.9": "MODERATE",

    "496": "HIGH",

    # =========================================================================
    # INFECTIOUS DISEASE
    # =========================================================================

    "010": "HIGH",

    "011.9": "HIGH",
    "011.90": "HIGH",

    "042": "HIGH",

    "054.10": "LOW",

    "070.3": "MODERATE",
    "070.51": "MODERATE",
    "070.54": "HIGH",
    "070.70": "MODERATE",
    "070.71": "HIGH",

    "099.9": "LOW",

    "795.5": "LOW",

    # =========================================================================
    # HEMATOLOGIC / IMMUNOLOGIC
    # =========================================================================

    "279.3": "HIGH",

    "280": "LOW",
    "280.9": "LOW",

    "281.9": "LOW",

    "282.6": "HIGH",

    "285.9": "LOW",

    "286": "MODERATE",
    "286.9": "MODERATE",

    "287": "MODERATE",
    "287.5": "MODERATE",

    "289.9": "MODERATE",

    # =========================================================================
    # GI / HEPATIC
    # =========================================================================

    "456.21": "HIGH",

    "530.81": "LOW",

    "531.7": "MODERATE",

    "532.4": "HIGH",
    "532.7": "MODERATE",

    "533.4": "HIGH",
    "533.7": "MODERATE",

    "550.9": "LOW",

    "553.1": "LOW",
    "553.9": "LOW",

    "556.9": "MODERATE",

    "562.11": "LOW",

    "564.1": "LOW",

    "571.40": "MODERATE",
    "571.5": "HIGH",

    "573.9": "MODERATE",

    "575.0": "MODERATE",

    "787.0": "LOW",
    "789.0": "LOW",

    # =========================================================================
    # ONCOLOGY
    # =========================================================================

    "149.0": "HIGH",
    "153": "HIGH",
    "156": "HIGH",
    "159": "HIGH",

    "162.9": "HIGH",

    "174": "HIGH",

    "180.9": "HIGH",

    "186": "HIGH",

    "188.9": "HIGH",

    "191.9": "HIGH",

    "199": "HIGH",
    "199.1": "HIGH",

    "201.9": "HIGH",

    "239.9": "MODERATE",

    # =========================================================================
    # NEUROLOGIC / SENSORY
    # =========================================================================

    "237.70": "MODERATE",

    "338.21": "MODERATE",
    "338.28": "MODERATE",
    "338.29": "MODERATE",

    "340": "HIGH",

    "343.9": "HIGH",

    "345.9": "HIGH",

    "346": "LOW",
    "346.0": "LOW",
    "346.1": "LOW",
    "346.2": "LOW",
    "346.9": "LOW",

    "349.9": "MODERATE",

    "365.9": "MODERATE",

    "369": "HIGH",
    "369.3": "HIGH",

    "389.9": "LOW",

    "434.9": "HIGH",
    "438.9": "HIGH",

    "780.39": "MODERATE",
    "780.51": "MODERATE",
    "780.97": "HIGH",

    "784.0": "LOW",
    "784.5": "MODERATE",

    # =========================================================================
    # MUSCULOSKELETAL
    # =========================================================================

    "710.4": "HIGH",

    "713": "MODERATE",
    "714": "MODERATE",

    "715": "LOW",
    "715.08": "LOW",
    "715.09": "LOW",
    "715.9": "LOW",

    "716.9": "LOW",

    "719": "LOW",

    "722.6": "MODERATE",

    "724.5": "LOW",

    "733.0": "MODERATE",
    "733.00": "MODERATE",

    # =========================================================================
    # DERMATOLOGY
    # =========================================================================

    "682.8": "MODERATE",

    "691.8": "LOW",

    "696": "MODERATE",
    "696.1": "MODERATE",

    # =========================================================================
    # REPRODUCTIVE
    # =========================================================================

    "256.9": "LOW",
    "257.9": "LOW",

    "629.9": "LOW",

    "644.10": "MODERATE",

    # =========================================================================
    # DENTAL
    # =========================================================================

    "525.4": "LOW",
    "525.5": "LOW",

    # =========================================================================
    # INJURY / TRAUMA
    # =========================================================================

    "839": "LOW",

    "879.8": "LOW",

    "905.8": "LOW",

    "919": "LOW",

    "959.01": "MODERATE",

    # =========================================================================
    # OTHER
    # =========================================================================
    "700": "LOW",
    "782.1": "LOW",
}

NON_CHRONIC_CODES = {

    # Symptoms

    "782.1",    # Rash
    "787.0",    # Nausea / Vomiting
    "789.0",    # Abdominal Pain

    # Injuries

    "839",
    "879.8",
    "905.8",
    "919",
    "959.01"
}

# =============================================================================
# HELPERS
# =============================================================================

def is_condition_header(value):

    value = str(value).strip()

    return bool(
        re.match(
            r"^\d+(\.\d+)?",
            value
        )
    )


def parse_condition_header(header_text):

    header_text = str(header_text).strip()

    header_text = re.sub(
        r"\s*-\s*Patients:\s*\d+\s*$",
        "",
        header_text,
        flags=re.IGNORECASE
    )

    match = re.match(
        r"^(\d+(?:\.\d+)?)\s+(.*)$",
        header_text
    )

    if match:
        return (
            match.group(1).strip(),
            match.group(2).strip()
        )

    return "", header_text


# =============================================================================
# LOAD SOURCE FILE
# =============================================================================

df = pd.read_csv(
    SOURCE_FILE,
    header=None,
    dtype=str,
    keep_default_na=False
)

records = []

current_condition_code = None
current_condition = None


# =============================================================================
# PARSE FILE
# =============================================================================

for _, row in df.iterrows():

    patient_name = str(
        row.iloc[0]
    ).strip()

    if not patient_name:
        continue

    if is_condition_header(
        patient_name
    ):

        (
            current_condition_code,
            current_condition
        ) = parse_condition_header(
            patient_name
        )

        print(
            f"Condition: "
            f"{current_condition_code} | "
            f"{current_condition}"
        )

        continue

    if current_condition is None:
        continue

    severity = SEVERITY_CROSSWALK.get(
        current_condition_code,
        UNKNOWN_SEVERITY
    )

    chronic_flag = (
        current_condition_code
        not in NON_CHRONIC_CODES
    )

    records.append(
        {
            "condition_code": current_condition_code,
            "condition": current_condition,
            "severity": severity,
            "chronic_flag": chronic_flag,

            "Patient Name": row.iloc[0],

            "Age": row.iloc[3],

            "Patient Number": row.iloc[5],
            "Booking Number": row.iloc[6],
            "Housing": row.iloc[7],

            "Custody Date": row.iloc[8],
            "Release Date": row.iloc[9],
            "Observed Date": row.iloc[10],

            "Status": row.iloc[11],

            "Initial Visit Scheduled": row.iloc[12],
            "Initial Visit Attended": row.iloc[13],

            "Last F/U Attended": row.iloc[16],
            "Next F/U Scheduled": row.iloc[17]
        }
    )

# =============================================================================
# OUTPUT
# =============================================================================

output_df = pd.DataFrame(records)

output_df["severity_rank"] = (
    output_df["severity"]
    .map(SEVERITY_ORDER)
    .fillna(99)
    .astype(int)
)

output_df = output_df.sort_values(
    [
        "severity_rank",
        "condition_code",
        "Patient Name"
    ]
)

print()
print("Severity Counts:")

print(
    output_df["severity"]
    .value_counts(dropna=False)
)

unmapped = (
    output_df.loc[
        output_df["severity"] == UNKNOWN_SEVERITY,
        [
            "condition_code",
            "condition"
        ]
    ]
    .drop_duplicates()
    .sort_values(
        "condition_code"
    )
)

print()
print(
    f"Unmapped condition count: "
    f"{len(unmapped)}"
)

print(unmapped)

print()
print(
    "Chronic vs Non-Chronic:"
)

print(
    output_df["chronic_flag"]
    .value_counts()
)

output_df.to_csv(
    OUTPUT_FILE,
    index=False
)

print()

print(
    f"Exported {len(output_df):,} records"
)

print(
    f"Saved: {OUTPUT_FILE}"
)