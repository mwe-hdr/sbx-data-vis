import pandas as pd

BASE_COHORTS = [
    {"name": "all", "filter": "True", "description": "All Detainees"},
    {"name": "male", "filter": "(sex == 'M')", "description": "Male Detainees"},
    {"name": "female", "filter": "(sex == 'F')", "description": "Female Detainees"},
    {
        "name": "admitted_classified",
        "filter": "(custody_class.notna() & (custody_class.str.strip() != ''))",
        "description": "Admitted Classified"
    },
    {
        "name": "admitted_not_classified",
        "filter": "(custody_class.isna() | (custody_class.str.strip() == ''))",
        "description": "Admitted Not Classified"
    },
    {
        "name": "minimum",
        "filter": "(custody_class.isin(['MIN', 'MINIMUM', 'MIIN']))",
        "description": "Minimum Custody"
    },
    {
        "name": "medium",
        "filter": "(custody_class.isin(['MED']))",
        "description": "Medium Custody"
    },
    {
        "name": "maximum",
        "filter": "(custody_class.isin(['MAX']))",
        "description": "Maximum Custody"
    },
    {
        "name": "close",
        "filter": "(custody_class.isin(['CLOS', 'CLO']))",
        "description": "Close Custody"
    },
    {
        "name": "special_needs",
        "filter": (
            "(custody_class.str.contains('SN', na=False) | "
            "custody_class.isin(['SN- HOUSE IN SUB', 'SN (IPOD SUBDAY)', 'SN J-POD']))"
        ),
        "description": "Special Needs"
    },
    {
        "name": "as",
        "filter": (
            "((custody_class.str.contains('AS', na=False)) | "
            "custody_class.isin(['AS/KS', 'S3 AS/KS', 'S3- AS/KS'])) & "
            "(housing != 'S2')"
        ),
        "description": "Administrative Segregation"
    },
    {
        "name": "ks",
        "filter": (
            "custody_class.isin(['AS/KS', 'SN/KS', 'SN/ KS', "
            "'PC/KS', 'AK/KS', 'SK/KS', 'G2 SN/KS', "
            "'S3 AS/KS', 'S3- AS/KS'])"
        ),
        "description": "Keep Separate"
    },
    {
        "name": "cs",
        "filter": (
            "(custody_class.str.contains('CS', na=False) | "
            "custody_class.isin(['S3-CS', 'S3 (CS)', 'S3 - CS', "
            "'S3-CONTROL SEG', 'S3-CONTROL SEGRE', "
            "'S3 CONT. SEG.', 'CONTROL SEGREGAT', "
            "'G2-CS', 'I POD SUBDAY CS']))"
        ),
        "description": "Control Segregation"
    },
    {
        "name": "pc",
        "filter": (
            "(custody_class.str.contains('PC', na=False) | "
            "custody_class.isin(['PEND PC']))"
        ),
        "description": "Protective Custody"
    },
    {
        "name": "work_release",
        "filter": "((sex == 'M') & (housing == 'A1'))",
        "description": "Work Release"
    },
    {
        "name": "medical_on_campus",
        "filter": "(housing.isin(['INFM']))",
        "description": "Medical Care On Campus"
    },
    {
        "name": "medical_off_campus",
        "filter": "(housing.isin(['BRE','BRW','BSDC','CTRP','NHI','STE']))",
        "description": "Medical Care Off Campus"
    },
    {
        "name": "medical_all",
        "filter": "(housing.isin(['INFM','BRE','BRW','BSDC','CTRP','NHI','STE']))",
        "description": "Medical Care All"
    },
    {
        "name": "disciplinary",
        "filter": (
            "(housing == 'S2') & "
            "~(custody_class.str.contains('AS', na=False) | "
            "custody_class.isin(['AS/KS','S3 AS/KS','S3- AS/KS']))"
        ),
        "description": "Disciplinary"
    },
    {
        "name": "detox",
        "filter": "(housing == 'DET')",
        "description": "Detox"
    }
]

AGE_BREAKOUTS = [
    ("u55", "adult under 55", "Under 55"),
    ("55plus", "adult 55+", "55+")
]

CHRONIC_BREAKOUTS = [
    ("chronic_high", "HIGH", "High Chronic"),
    ("chronic_moderate", "MODERATE", "Moderate Chronic"),
    ("chronic_low", "LOW", "Low Chronic"),
    ("no_chronic", "NO CHRONIC CONDITION", "No Chronic Condition")
]

SEX_BREAKOUTS = [
    ("male", "M", "Male"),
    ("female", "F", "Female")
]

rows = []


def add_cohort(name, filt, description):
    rows.append(
        {
            "name": name,
            "param": "filter",
            "value": filt,
            "description": description,
            "cohort_file": name
        }
    )


for cohort in BASE_COHORTS:

    base_name = cohort["name"]
    base_filter = cohort["filter"]
    base_desc = cohort["description"]

    # Base cohort
    add_cohort(
        base_name,
        base_filter,
        base_desc
    )

    # Age breakouts
    for age_suffix, age_val, age_desc in AGE_BREAKOUTS:
        add_cohort(
            f"{base_name}.{age_suffix}",
            f"({base_filter}) & (age_bracket == '{age_val}')",
            f"{base_desc} {age_desc}"
        )

    # Chronic breakouts
    for chronic_suffix, chronic_val, chronic_desc in CHRONIC_BREAKOUTS:
        add_cohort(
            f"{base_name}.{chronic_suffix}",
            f"({base_filter}) & (chronic_status == '{chronic_val}')",
            f"{base_desc} {chronic_desc}"
        )

    # Gender breakouts
    for sex_suffix, sex_val, sex_desc in SEX_BREAKOUTS:

        sex_filter = (
            f"({base_filter}) & "
            f"(sex == '{sex_val}')"
        )

        add_cohort(
            f"{base_name}.{sex_suffix}",
            sex_filter,
            f"{base_desc} {sex_desc}"
        )

        # Gender + Age
        for age_suffix, age_val, age_desc in AGE_BREAKOUTS:

            add_cohort(
                f"{base_name}.{sex_suffix}.{age_suffix}",
                f"({sex_filter}) & (age_bracket == '{age_val}')",
                f"{base_desc} {sex_desc} {age_desc}"
            )

        # Gender + Chronic
        for chronic_suffix, chronic_val, chronic_desc in CHRONIC_BREAKOUTS:

            add_cohort(
                f"{base_name}.{sex_suffix}.{chronic_suffix}",
                f"({sex_filter}) & (chronic_status == '{chronic_val}')",
                f"{base_desc} {sex_desc} {chronic_desc}"
            )

result = pd.DataFrame(rows)

result = result.drop_duplicates(
    subset=["name"],
    keep="first"
)

result = result.sort_values(
    by="name"
).reset_index(drop=True)

output_file = (
    r"C:\lwf\sbx-data-vis\data\input\params\cohorts\adf\adf_breakouts.csv"
)

result.to_csv(
    output_file,
    index=False
)

print(f"Generated {len(result):,} cohorts")
print(f"Saved to: {output_file}")