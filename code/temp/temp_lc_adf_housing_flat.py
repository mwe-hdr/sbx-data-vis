import pandas as pd
from datetime import timedelta

INPUT_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf\HOUSING_HISTORY.CSV"
OUTPUT_FILE = r"C:\lwf\sbx-data-vis\data\output\housing_history_flat.csv"

# Read file
df = pd.read_csv(INPUT_FILE)

# Parse dates
df["ADATE"] = pd.to_datetime(df["ADATE"])

# Sort chronologically within inmate
df = df.sort_values(["BOOK#", "ADATE"])

results = []

for book_no, grp in df.groupby("BOOK#", sort=False):

    grp = grp[["BOOK#", "POD", "ADATE"]].copy()

    # Remove consecutive duplicate housing assignments
    grp = grp.loc[
        (grp["POD"] != grp["POD"].shift()) |
        (grp["POD"].shift().isna())
    ].reset_index(drop=True)

    for i in range(len(grp)):

        housing = grp.loc[i, "POD"]
        start_date = grp.loc[i, "ADATE"]

        if i < len(grp) - 1:
            next_start = grp.loc[i + 1, "ADATE"]
            end_date = next_start - timedelta(days=1)
        else:
            end_date = pd.NaT

        results.append({
            "BOOK#": book_no,
            "HOUSING": housing,
            "HOUSING_START_DATE": start_date,
            "HOUSING_END_DATE": end_date
        })

out_df = pd.DataFrame(results)

out_df.to_csv(OUTPUT_FILE, index=False)

print(f"Wrote {len(out_df):,} rows to {OUTPUT_FILE}")