import pandas as pd
from pathlib import Path

# Input file
input_file = Path(
    r"C:\lwf\sbx-data-vis\data\input\ecu_inpatient_days_and_discharges_export.csv"
)

# Output file
output_file = input_file.with_name(
    f"{input_file.stem}_flat{input_file.suffix}"
)

# Read CSV
df = pd.read_csv(input_file, low_memory=False)

# Convert service date to datetime
df["service_dt"] = pd.to_datetime(df["service_dt"], errors="coerce")

# Encounter key
encounter_col = "patient_encounter_record_number"

# Build aggregation:
#  - first non-null value for all columns
#  - min/max service_dt for the new fields
agg_dict = {
    col: (lambda x: x.dropna().iloc[0] if len(x.dropna()) > 0 else pd.NA)
    for col in df.columns
}

# Flatten to encounter level
flat_df = (
    df.groupby(encounter_col, dropna=False)
      .agg(agg_dict)
      .reset_index(drop=True)
)

# Add service span dates
svc_dates = (
    df.groupby(encounter_col)["service_dt"]
      .agg(svc_st_dt="min", svc_end_dt="max")
      .reset_index()
)

flat_df = flat_df.merge(
    svc_dates,
    on=encounter_col,
    how="left"
)

# Format dates
flat_df["svc_st_dt"] = flat_df["svc_st_dt"].dt.strftime("%Y-%m-%d")
flat_df["svc_end_dt"] = flat_df["svc_end_dt"].dt.strftime("%Y-%m-%d")

# Optional: preserve original service_dt column from first row,
# while adding the new encounter-level span columns.

# Write output
flat_df.to_csv(output_file, index=False)

print(f"Output written to: {output_file}")
print(f"Input rows:  {len(df):,}")
print(f"Output rows: {len(flat_df):,}")