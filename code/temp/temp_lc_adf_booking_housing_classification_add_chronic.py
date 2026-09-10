import pandas as pd
from pathlib import Path

# Input files
base_path = Path(r"C:\lwf\sbx-data-vis\data\input")

chronic_file = base_path / "lc_adf_chronic_care.csv"
housing_file = base_path / "lc_adf_booking_housing_classification.csv"
output_file = base_path / "lc_adf_booking_housing_classification_chronic.csv"

# ------------------------------------------------------------------
# Read chronic care data
# ------------------------------------------------------------------
chronic_df = pd.read_csv(chronic_file)

# Ensure severity_rank is numeric
chronic_df["severity_rank"] = pd.to_numeric(
    chronic_df["severity_rank"],
    errors="coerce"
)

# Keep only the chronic record with the lowest severity_rank
# for each Booking Number
chronic_one_row = (
    chronic_df
    .sort_values(["Booking Number", "severity_rank"], ascending=[True, True])
    .drop_duplicates(subset=["Booking Number"], keep="first")
    [["Booking Number", "severity"]]
    .rename(columns={"severity": "chronic_status"})
)

# ------------------------------------------------------------------
# Read housing classification data
# ------------------------------------------------------------------
housing_df = pd.read_csv(housing_file)

# ------------------------------------------------------------------
# Merge chronic status onto housing data
# ------------------------------------------------------------------
result_df = housing_df.merge(
    chronic_one_row,
    how="left",
    left_on="BookNumber",
    right_on="Booking Number"
)

# Remove merge key from chronic file
if "Booking Number" in result_df.columns:
    result_df = result_df.drop(columns=["Booking Number"])

# ------------------------------------------------------------------
# Write output
# ------------------------------------------------------------------
result_df.to_csv(output_file, index=False)

print(f"Output written to: {output_file}")
print(f"Rows written: {len(result_df):,}")