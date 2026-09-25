import pandas as pd
import numpy as np

# ------------------------------------------------------------------
# FILES
# ------------------------------------------------------------------

MAIN_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf_booking_housing_classification_chronic_detox.csv"

HOUSING_DETAIL_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf_20260824\HOUSING_HISTORY.CSV"

OUTPUT_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf_booking_housing_classification_chronic_detox_bh_acute.csv"

# ------------------------------------------------------------------
# BH ACUTE DEFINITIONS
# ------------------------------------------------------------------

BH_ACUTE_CELLS = {
    "G219A",
    "G219B",
    "G220A",
    "G220B",
    "G221A",
    "G221B",
    "G222A",
    "G222B",
    "G247",
    "G248",
    "G249",
    "G250"
}

# ------------------------------------------------------------------
# LOAD FILES
# ------------------------------------------------------------------

main = pd.read_csv(MAIN_FILE, low_memory=False)

detail = pd.read_csv(
    HOUSING_DETAIL_FILE,
    low_memory=False
)

# ------------------------------------------------------------------
# DATE CONVERSIONS
# ------------------------------------------------------------------

main["WindowStartDate"] = pd.to_datetime(
    main["WindowStartDate"],
    errors="coerce"
)

main["WindowEndDate"] = pd.to_datetime(
    main["WindowEndDate"],
    errors="coerce"
)

detail["ADATE"] = pd.to_datetime(
    detail["ADATE"],
    errors="coerce"
)

detail = detail.dropna(
    subset=["ADATE"]
)
# ------------------------------------------------------------------
# NORMALIZE BOOKING NUMBER
# ------------------------------------------------------------------

main["BookNumber"] = (
    pd.to_numeric(main["BookNumber"], errors="coerce")
    .astype("Int64")
)

detail["BOOK#"] = (
    pd.to_numeric(detail["BOOK#"], errors="coerce")
    .astype("Int64")
)


detail = detail.sort_values(
    ["BOOK#", "ADATE"]
)

detail["WindowStartDate"] = detail["ADATE"]

detail["WindowEndDate"] = (
    detail.groupby("BOOK#")["ADATE"]
    .shift(-1)
)

# optional buffer for final housing record
detail["WindowEndDate"] = (
    detail["WindowEndDate"]
    .fillna(pd.Timestamp("2099-12-31"))
)
# ------------------------------------------------------------------
# CREATE BH ACUTE WINDOWS
# ------------------------------------------------------------------

detail["POD"] = (
    detail["POD"]
    .fillna("")
    .astype(str)
    .str.upper()
    .str.strip()
)

detail["CELL"] = (
    detail["CELL"]
    .fillna("")
    .astype(str)
    .str.upper()
    .str.strip()
)

bh_acute_mask = (
    (detail["POD"] == "S3")
    |
    (
        (detail["POD"] == "G2")
        &
        (detail["CELL"].isin(BH_ACUTE_CELLS))
    )
)

bh_acute = detail.loc[bh_acute_mask].copy()

bh_acute = bh_acute[
    [
        "BOOK#",
        "WindowStartDate",
        "WindowEndDate"
    ]
].dropna(
    subset=[
        "BOOK#",
        "WindowStartDate",
        "WindowEndDate"
    ]
)

bh_groups = {
    k: g.copy()
    for k, g in bh_acute.groupby("BOOK#")
}

# ------------------------------------------------------------------
# SPLIT WINDOWS
# ------------------------------------------------------------------

output_rows = []

for _, row in main.iterrows():

    start = row["WindowStartDate"]
    end = row["WindowEndDate"]

    if pd.isna(start) or pd.isna(end):
        continue

    book_number = row["BookNumber"]

    if book_number not in bh_groups:

        new_row = row.copy()

        output_rows.append(new_row)
        continue

    overlaps = []

    bh_windows = bh_groups[book_number]

    for _, bh in bh_windows.iterrows():

        overlap_start = max(
            start,
            bh["WindowStartDate"]
        )

        overlap_end = min(
            end,
            bh["WindowEndDate"]
        )

        if overlap_start < overlap_end:
            overlaps.append(
                (
                    overlap_start,
                    overlap_end
                )
            )

    if not overlaps:

        new_row = row.copy()

        output_rows.append(new_row)
        continue

    overlaps.sort()

    merged = []

    for s, e in overlaps:

        if not merged:
            merged.append([s, e])
        else:

            last_s, last_e = merged[-1]

            if s <= last_e:
                merged[-1][1] = max(last_e, e)
            else:
                merged.append([s, e])

    cursor = start

    for bh_start, bh_end in merged:

        if cursor < bh_start:

            normal_row = row.copy()
            normal_row["WindowStartDate"] = cursor
            normal_row["WindowEndDate"] = bh_start

            output_rows.append(normal_row)

        bh_row = row.copy()

        bh_row["WindowStartDate"] = bh_start
        bh_row["WindowEndDate"] = bh_end

        current_housing = str(
            bh_row.get("housing", "")
        ).strip()

        if (
            current_housing == ""
            or current_housing.upper() == "NAN"
        ):
            bh_row["housing"] = "BH_Acute"
        else:
            bh_row["housing"] = (
                current_housing + "-BH_Acute"
            )        

        output_rows.append(bh_row)

        cursor = max(cursor, bh_end)

    if cursor < end:

        normal_row = row.copy()

        normal_row["WindowStartDate"] = cursor
        normal_row["WindowEndDate"] = end

        output_rows.append(normal_row)

# ------------------------------------------------------------------
# SAVE
# ------------------------------------------------------------------

result = pd.DataFrame(output_rows)

result = result.sort_values(
    [
        "BookNumber",
        "WindowStartDate"
    ]
)

date_cols = [
    "WindowStartDate",
    "WindowStartDateCpy",
    "WindowEndDate"
]

for col in date_cols:

    if col in result.columns:

        result[col] = pd.to_datetime(
            result[col],
            errors="coerce"
        ).dt.strftime("%-m/%-d/%Y")

result.to_csv(
    OUTPUT_FILE,
    index=False
)

print(f"Saved: {OUTPUT_FILE}")
print(f"Rows: {len(result):,}")

matched_bh = bh_acute["BOOK#"].isin(
    main["BookNumber"]
).sum()

print("\nQA SUMMARY")
print("-" * 40)
print(f"Bookings: {main['BookNumber'].nunique():,}")
print(f"Main Rows Input: {len(main):,}")
print(f"BH Acute Records: {len(bh_acute):,}")
print(f"Matched BH Acute Records: {matched_bh:,}")
print(f"Output Rows: {len(result):,}")

unmatched = bh_acute[
    ~bh_acute["BOOK#"].isin(main["BookNumber"])
]

unmatched.to_csv(
    r"C:\lwf\sbx-data-vis\data\input\bh_acute_unmatched.csv",
    index=False
)

print(f"Unmatched BH Acute Records: {len(unmatched):,}")