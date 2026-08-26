import pandas as pd
import numpy as np
from pathlib import Path

# ============================================================================
# CONFIGURATION
# ============================================================================

INPUT_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf_housing_classification_combo.csv"

ANALYSIS_START = pd.Timestamp("2025-07-01")
ANALYSIS_END = pd.Timestamp("2026-06-30")

OUTPUT_COHORT_CAPACITY = r"C:\lwf\sbx-data-vis\data\input\lc_adf_estimated_cohort_capacity.csv"
OUTPUT_HOUSING_UTILIZATION = r"C:\lwf\sbx-data-vis\data\input\lc_adf_housing_utilization_by_cohort.csv"

# ============================================================================
# KNOWN CAPACITY MODEL FROM SCREENSHOT
# ============================================================================

HOUSING_CAPACITY = {
    "A1": 24,
    "A2": 24,
    "B1": 24,
    "B2": 24,
    "C1": 24,
    "C2": 24,
    "D1": 24,
    "D2": 24,
    "E1": 24,
    "E2": 24,
    "F1": 24,
    "F2": 24,
    "G1": 22,
    "G2": 36,
    "I": 64,
    "J": 64,
    "K": 64,
    "L": 64,
    "N": 64,
    "R": 64,
    "S1": 24,
    "S2": 20,
    "S3": 12
}

# ============================================================================
# DIRECT / HIGH-CONFIDENCE CAPACITY ASSIGNMENTS
# ============================================================================

KNOWN_DIRECT_COHORT_CAPACITY = {
    "classified.minimum.housing.male": (
        HOUSING_CAPACITY["A1"]
        + HOUSING_CAPACITY["A2"]
        + HOUSING_CAPACITY["B1"]
        + HOUSING_CAPACITY["B2"]
        + HOUSING_CAPACITY["D1"]
        + HOUSING_CAPACITY["D2"]
        + HOUSING_CAPACITY["E1"]
        + HOUSING_CAPACITY["E2"]
        + HOUSING_CAPACITY["F1"]
    ),

    "classified.minimum.housing.female": (
        HOUSING_CAPACITY["C1"]
        + HOUSING_CAPACITY["C2"]
    ),

    "classified.maximum.housing.male": HOUSING_CAPACITY["N"],

    "classified.close.housing.male": HOUSING_CAPACITY["L"],

    "classified.medium.housing.male": HOUSING_CAPACITY["K"],

    "classified.administrative_segregation.housing.male": (
        HOUSING_CAPACITY["S1"]
        + HOUSING_CAPACITY["S3"]
    ),

    "classified.protective_classified.housing.male": HOUSING_CAPACITY["S1"],

    "classified.controlled_segregation.housing.male": (
        HOUSING_CAPACITY["G2"]
        + HOUSING_CAPACITY["S3"]
    ),

    "classified.special_needs.housing.male": HOUSING_CAPACITY["G2"],

    "classified.keep_separate.housing.male": HOUSING_CAPACITY["S3"]
}

# ============================================================================
# CUSTODY CLASS NORMALIZATION
# ============================================================================

def normalize_class(value):
    if pd.isna(value):
        return None

    v = str(value).upper().strip()

    if "MAX" in v:
        return "maximum"

    if "MIN" in v:
        return "minimum"

    if "MED" in v:
        return "medium"

    if "CLHI" in v:
        return "close_hi"

    if "CLLO" in v:
        return "close_low"

    if v in {"CLOS", "CLO"}:
        return "close"

    if "AS" in v and "KS" not in v:
        return "administrative_segregation"

    if "CS" in v or "CONTROL" in v:
        return "controlled_segregation"

    if "PC" in v:
        return "protective_classified"

    if "KS" in v:
        return "keep_separate"

    if "SN" in v:
        return "special_needs"

    return None


# ============================================================================
# HOUSING NORMALIZATION
# ============================================================================

ON_CAMPUS_HOUSING = set(HOUSING_CAPACITY.keys())

SEX_MAP = {
    "M": "male",
    "F": "female"
}

# ============================================================================
# LOAD
# ============================================================================

print("Loading file...")

df = pd.read_csv(
    INPUT_FILE,
    low_memory=False
)

df.columns = [c.strip() for c in df.columns]

# ============================================================================
# DATES
# ============================================================================

for col in [
    "WindowStartDate",
    "WindowEndDate",
    "HousingStart",
    "HousingEnd",
    "ClassStart",
    "ClassEnd"
]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

# ============================================================================
# FILTER ANALYSIS WINDOW
# ============================================================================

df = df[
    (df["WindowEndDate"] >= ANALYSIS_START)
    &
    (df["WindowStartDate"] <= ANALYSIS_END)
].copy()

# Trim overlap exactly to analysis period

df["AdjStart"] = df["WindowStartDate"].clip(lower=ANALYSIS_START)
df["AdjEnd"] = df["WindowEndDate"].clip(upper=ANALYSIS_END)

df["OverlapDays"] = (
    (df["AdjEnd"] - df["AdjStart"]).dt.days + 1
)

df = df[df["OverlapDays"] > 0]

# ============================================================================
# STANDARDIZE
# ============================================================================

df["housing"] = (
    df["housing"]
    .astype(str)
    .str.upper()
    .str.strip()
)

df["sex"] = (
    df["sex"]
    .astype(str)
    .str.upper()
    .str.strip()
)

df["sex_group"] = df["sex"].map(SEX_MAP)

df["class_group"] = df["custody_class"].apply(normalize_class)

df = df[df["housing"].isin(ON_CAMPUS_HOUSING)]

# ============================================================================
# RESIDENT-DAY UTILIZATION BY HOUSING / SEX / CLASSIFICATION
# ============================================================================

util = (
    df.groupby(
        ["housing", "sex_group", "class_group"],
        dropna=False
    )["OverlapDays"]
    .sum()
    .reset_index(name="resident_days")
)

housing_totals = (
    util.groupby("housing")["resident_days"]
    .sum()
    .reset_index(name="housing_days")
)

util = util.merge(housing_totals, on="housing")

util["allocation_pct"] = (
    util["resident_days"]
    / util["housing_days"]
)

util["housing_capacity"] = util["housing"].map(HOUSING_CAPACITY)

util["estimated_capacity"] = (
    util["allocation_pct"]
    * util["housing_capacity"]
)

# ============================================================================
# COHORT CROSSWALK
# ============================================================================

def cohort_name(class_group, sex_group):

    if pd.isna(class_group) or pd.isna(sex_group):
        return None

    return f"classified.{class_group}.housing.{sex_group}"


util["cohort"] = util.apply(
    lambda r: cohort_name(r["class_group"], r["sex_group"]),
    axis=1
)

util = util[util["cohort"].notna()].copy()

# ============================================================================
# ESTIMATED CAPACITY BY COHORT
# ============================================================================

estimated_capacity = (
    util.groupby("cohort")["estimated_capacity"]
    .sum()
    .reset_index()
)

# ============================================================================
# ADD HIGH-CONFIDENCE KNOWN VALUES
# ============================================================================

known_df = pd.DataFrame({
    "cohort": list(KNOWN_DIRECT_COHORT_CAPACITY.keys()),
    "known_capacity": list(KNOWN_DIRECT_COHORT_CAPACITY.values())
})

estimated_capacity = estimated_capacity.merge(
    known_df,
    on="cohort",
    how="outer"
)

estimated_capacity["final_capacity"] = np.where(
    estimated_capacity["known_capacity"].notna(),
    estimated_capacity["known_capacity"],
    estimated_capacity["estimated_capacity"]
)

# ============================================================================
# CREATE AGGREGATE COHORTS
# ============================================================================

agg_rows = []

def aggregate(prefix):

    mask = estimated_capacity["cohort"].str.startswith(prefix + ".")
    value = estimated_capacity.loc[
        mask,
        "final_capacity"
    ].sum()

    agg_rows.append({
        "cohort": prefix,
        "final_capacity": value
    })


aggregate("classified.minimum.housing")
aggregate("classified.medium.housing")
aggregate("classified.maximum.housing")
aggregate("classified.close.housing")
aggregate("classified.close_hi.housing")
aggregate("classified.close_low.housing")
aggregate("classified.administrative_segregation.housing")
aggregate("classified.controlled_segregation.housing")
aggregate("classified.keep_separate.housing")
aggregate("classified.protective_classified.housing")
aggregate("classified.special_needs.housing")

agg_df = pd.DataFrame(agg_rows)

final_capacity = pd.concat([
    estimated_capacity[["cohort", "final_capacity"]],
    agg_df
], ignore_index=True)

# ============================================================================
# ALL CLASSIFIED
# ============================================================================

sex_totals = (
    final_capacity[
        final_capacity["cohort"].str.endswith(".male")
        |
        final_capacity["cohort"].str.endswith(".female")
    ]
    .copy()
)

male_total = (
    sex_totals.loc[
        sex_totals["cohort"].str.endswith(".male"),
        "final_capacity"
    ].sum()
)

female_total = (
    sex_totals.loc[
        sex_totals["cohort"].str.endswith(".female"),
        "final_capacity"
    ].sum()
)

final_capacity = pd.concat([
    final_capacity,
    pd.DataFrame([
        {
            "cohort": "classified.all_classified.housing.male",
            "final_capacity": male_total
        },
        {
            "cohort": "classified.all_classified.housing.female",
            "final_capacity": female_total
        },
        {
            "cohort": "classified.all_classified.housing",
            "final_capacity": male_total + female_total
        }
    ])
], ignore_index=True)

# ============================================================================
# ALL SPECIAL MANAGEMENT
# ============================================================================

special_management_prefixes = [
    "classified.administrative_segregation.housing",
    "classified.controlled_segregation.housing",
    "classified.keep_separate.housing",
    "classified.protective_classified.housing",
    "classified.special_needs.housing"
]

for sex in ["male", "female"]:

    total = 0.0

    for prefix in special_management_prefixes:
        cohort = prefix + "." + sex

        match = final_capacity[
            final_capacity["cohort"] == cohort
        ]

        if len(match):
            total += match["final_capacity"].iloc[0]

    final_capacity = pd.concat([
        final_capacity,
        pd.DataFrame([
            {
                "cohort": f"classified.all_special_management.housing.{sex}",
                "final_capacity": total
            }
        ])
    ], ignore_index=True)

special_total = (
    final_capacity.loc[
        final_capacity["cohort"].str.startswith(
            "classified.all_special_management.housing."
        ),
        "final_capacity"
    ].sum()
)

final_capacity = pd.concat([
    final_capacity,
    pd.DataFrame([
        {
            "cohort": "classified.all_special_management.housing",
            "final_capacity": special_total
        }
    ])
], ignore_index=True)

# ============================================================================
# SORT / SAVE
# ============================================================================

final_capacity = (
    final_capacity
    .groupby("cohort", as_index=False)
    .agg(final_capacity=("final_capacity", "max"))
    .sort_values("cohort")
)

util.sort_values(
    ["housing", "sex_group", "class_group"]
).to_csv(
    OUTPUT_HOUSING_UTILIZATION,
    index=False
)

final_capacity.to_csv(
    OUTPUT_COHORT_CAPACITY,
    index=False
)

print()
print("Completed.")
print(f"Cohort capacity file : {OUTPUT_COHORT_CAPACITY}")
print(f"Housing utilization  : {OUTPUT_HOUSING_UTILIZATION}")