import pandas as pd
from pathlib import Path

# ============================================================
# Input / Output
# ============================================================

input_file = Path(
    r"C:\lwf\sbx-data-vis\data\input\ecu_surgery_and_gi_export.csv"
)

output_file = input_file.with_name(
    f"{input_file.stem}_flat{input_file.suffix}"
)

# ============================================================
# Read file
# ============================================================

df = pd.read_csv(input_file, low_memory=False)

encounter_col = "patient_encounter_record_number"

# Preserve original values while creating encounter span dates
df["service_dt"] = pd.to_datetime(df["service_dt"], errors="coerce")

# ============================================================
# Build encounter-level service date ranges
# ============================================================

svc_dates = (
    df.groupby(encounter_col, dropna=False)["service_dt"]
      .agg(
          svc_st_dt="min",
          svc_end_dt="max"
      )
      .reset_index()
)

# ============================================================
# Flatten all other columns
# Take the first non-null value encountered
# ============================================================

def first_non_null(series):
    non_null = series.dropna()
    return non_null.iloc[0] if len(non_null) else pd.NA

agg_dict = {
    col: first_non_null
    for col in df.columns
    if col != encounter_col
}

flat_df = (
    df.groupby(encounter_col, dropna=False)
      .agg(agg_dict)
      .reset_index()
)

# ============================================================
# Add service date span
# ============================================================

flat_df = flat_df.merge(
    svc_dates,
    on=encounter_col,
    how="left"
)

flat_df["svc_st_dt"] = flat_df["svc_st_dt"].dt.strftime("%Y-%m-%d")
flat_df["svc_end_dt"] = flat_df["svc_end_dt"].dt.strftime("%Y-%m-%d")

# ============================================================
# Write output
# ============================================================

flat_df.to_csv(output_file, index=False)

print(f"Input file : {input_file}")
print(f"Output file: {output_file}")
print(f"Input rows : {len(df):,}")
print(f"Output rows: {len(flat_df):,}")