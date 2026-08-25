import pandas as pd

# Input files
CLASS_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf_class_pod_history_flat_enriched.csv"
HOUSING_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf_housing_history_flat.csv"

# Output file
OUTPUT_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf_housing_classification_combo.csv"

# ------------------------------------------------------------------
# Read files
# ------------------------------------------------------------------
housing = pd.read_csv(HOUSING_FILE)
classification = pd.read_csv(CLASS_FILE)

# ------------------------------------------------------------------
# Standardize column names
# ------------------------------------------------------------------
housing = housing.rename(
    columns={
        "BOOK#": "BookNumber",
        "WindowStartDate": "HousingStart",
        "WindowEndDate": "HousingEnd",
        "housing": "Housing"
    }
)

classification = classification.rename(
    columns={
        "WindowStartDate": "ClassStart",
        "WindowEndDate": "ClassEnd",
        "Pod": "ClassificationPod"
    }
)

# Ensure merge keys have the same datatype
housing["BookNumber"] = housing["BookNumber"].astype(str).str.strip()
classification["BookNumber"] = classification["BookNumber"].astype(str).str.strip()

merged = housing.merge(
    classification,
    on="BookNumber",
    how="inner",
    suffixes=("_Housing", "_Class")
)

# ------------------------------------------------------------------
# Convert dates
# ------------------------------------------------------------------
housing["HousingStart"] = pd.to_datetime(housing["HousingStart"])
housing["HousingEnd"] = pd.to_datetime(housing["HousingEnd"])

classification["ClassStart"] = pd.to_datetime(classification["ClassStart"])
classification["ClassEnd"] = pd.to_datetime(classification["ClassEnd"])

# ------------------------------------------------------------------
# Merge by inmate
# ------------------------------------------------------------------
merged = housing.merge(
    classification,
    on="BookNumber",
    how="inner",
    suffixes=("_Housing", "_Class")
)

# ------------------------------------------------------------------
# Keep only overlapping windows
# ------------------------------------------------------------------
overlap_mask = (
    (merged["HousingStart"] <= merged["ClassEnd"]) &
    (merged["HousingEnd"] >= merged["ClassStart"])
)

merged = merged.loc[overlap_mask].copy()

# ------------------------------------------------------------------
# Calculate overlap period
# ------------------------------------------------------------------
merged["OverlapStart"] = merged[
    ["HousingStart", "ClassStart"]
].max(axis=1)

merged["OverlapEnd"] = merged[
    ["HousingEnd", "ClassEnd"]
].min(axis=1)

merged["OverlapDays"] = (
    merged["OverlapEnd"] - merged["OverlapStart"]
).dt.days + 1

# ------------------------------------------------------------------
# Select output columns
# ------------------------------------------------------------------
output_cols = [
    "BookNumber",
    "Housing",
    "HousingStart",
    "HousingEnd",
    "ClassificationPod",
    "ClassStart",
    "ClassEnd",
    "OverlapStart",
    "OverlapEnd",
    "OverlapDays"
]

result = merged[output_cols].sort_values(
    ["BookNumber", "OverlapStart"]
)

# ------------------------------------------------------------------
# Write output
# ------------------------------------------------------------------
result.to_csv(OUTPUT_FILE, index=False)

print(f"Output records: {len(result):,}")
print(f"Saved to: {OUTPUT_FILE}")