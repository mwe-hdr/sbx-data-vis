import pandas as pd
import numpy as np
from datetime import timedelta

# ------------------------------------------------------------------
# FILES
# ------------------------------------------------------------------

HOUSING_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf_booking_housing_classification_chronic.csv"

BOOKING_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf_20260824\INMATES_BOOKED_with_demo.CSV"

DETOX_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf_20260824\DETOX_EVENTS.csv"

OUTPUT_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf_booking_housing_classification_chronic_detox.csv"

DETOX_START_COL = "Protocol Start Date"
DETOX_END_COL = "Protocol End Date"

# ------------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------------

def clean_name(value):
    if pd.isna(value):
        return ""
    return (
        str(value)
        .upper()
        .strip()
        .replace(",", "")
        .replace(".", "")
    )


def create_person_key(last_name, first_name, dob):
    dob_str = ""
    if pd.notna(dob):
        try:
            dob_str = pd.to_datetime(dob).strftime("%Y-%m-%d")
        except Exception:
            dob_str = str(dob)

    return f"{clean_name(last_name)}|{clean_name(first_name)}|{dob_str}"


# ------------------------------------------------------------------
# LOAD FILES
# ------------------------------------------------------------------

housing = pd.read_csv(HOUSING_FILE, low_memory=False)

booking = pd.read_csv(
    BOOKING_FILE,
    low_memory=False
)

detox = pd.read_csv(
    DETOX_FILE,
    low_memory=False
)

# ------------------------------------------------------------------
# DATE CONVERSIONS
# ------------------------------------------------------------------

housing["WindowStartDate"] = pd.to_datetime(
    housing["WindowStartDate"],
    errors="coerce"
)

housing["WindowEndDate"] = pd.to_datetime(
    housing["WindowEndDate"],
    errors="coerce"
)

booking["DOB"] = pd.to_datetime(
    booking["DOB"],
    errors="coerce"
)

# ------------------------------------------------------------------
# BUILD BOOKING LOOKUP
# ------------------------------------------------------------------

booking["person_key"] = booking.apply(
    lambda x: create_person_key(
        x["LNAM"],
        x["FNAM"],
        x["DOB"]
    ),
    axis=1
)

booking_lookup = booking[
    ["BOOKNUMBER", "person_key"]
].drop_duplicates()

housing = housing.merge(
    booking_lookup,
    left_on="BookNumber",
    right_on="BOOKNUMBER",
    how="left"
)

# ----------------------------------------------------------
# DETOX NORMALIZATION
# ----------------------------------------------------------

detox["Date of Birth"] = pd.to_datetime(
    detox["Date of Birth"],
    errors="coerce"
)

detox["Protocol Start Date"] = pd.to_datetime(
    detox["Protocol Start Date"],
    errors="coerce"
)

detox["Protocol End Date"] = pd.to_datetime(
    detox["Protocol End Date"],
    errors="coerce"
)

name_parts = (
    detox["Patient Name"]
    .fillna("")
    .astype(str)
    .str.upper()
    .str.split(",", n=1)
)

detox["LNAM"] = name_parts.str[0].str.strip()

detox["FNAM"] = (
    name_parts.str[1]
    .fillna("")
    .str.strip()
    .str.split()
    .str[0]
)

booking["FNAM_MATCH"] = (
    booking["FNAM"]
    .fillna("")
    .astype(str)
    .str.upper()
    .str.strip()
    .str.split()
    .str[0]
)

booking["person_key"] = (
    booking["LNAM"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    + "|"
    + booking["FNAM_MATCH"]
    + "|"
    + booking["DOB"].dt.strftime("%Y-%m-%d")
)

booking_lookup = (
    booking[["BOOKNUMBER", "person_key"]]
    .drop_duplicates()
)

housing = housing.drop(
    columns=["BOOKNUMBER", "person_key"],
    errors="ignore"
)

housing = housing.merge(
    booking_lookup,
    left_on="BookNumber",
    right_on="BOOKNUMBER",
    how="left"
)

detox["person_key"] = (
    detox["LNAM"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    + "|"
    + detox["FNAM"]
    + "|"
    + detox["Date of Birth"].dt.strftime("%Y-%m-%d")
)

# ------------------------------------------------------------------
# SPLIT WINDOWS
# ------------------------------------------------------------------

output_rows = []

detox_groups = {
    k: g.copy()
    for k, g in detox.groupby("person_key")
}

for _, row in housing.iterrows():

    start = row["WindowStartDate"]
    end = row["WindowEndDate"]

    if pd.isna(start) or pd.isna(end):
        continue

    person_key = row["person_key"]

    if person_key not in detox_groups:

        new_row = row.copy()
        new_row["housing_detox_status"] = "NORMAL"
        output_rows.append(new_row)

        continue

    overlaps = []

    person_detox = detox_groups[person_key]

    for _, d in person_detox.iterrows():

        overlap_start = max(
            start,
            d[DETOX_START_COL]
        )

        overlap_end = min(
            end,
            d[DETOX_END_COL]
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
        new_row["housing_detox_status"] = "NORMAL"
        output_rows.append(new_row)
        continue

    overlaps.sort()

    cursor = start

    for d_start, d_end in overlaps:

        if cursor < d_start:

            normal_row = row.copy()
            normal_row["WindowStartDate"] = cursor
            normal_row["WindowEndDate"] = d_start
            normal_row["housing_detox_status"] = "NORMAL"

            output_rows.append(normal_row)

        detox_row = row.copy()
        detox_row["WindowStartDate"] = d_start
        detox_row["WindowEndDate"] = d_end
        detox_row["housing_detox_status"] = "DETOX"

        output_rows.append(detox_row)

        cursor = max(cursor, d_end)

    if cursor < end:

        normal_row = row.copy()
        normal_row["WindowStartDate"] = cursor
        normal_row["WindowEndDate"] = end
        normal_row["housing_detox_status"] = "NORMAL"

        output_rows.append(normal_row)

# ------------------------------------------------------------------
# SAVE
# ------------------------------------------------------------------

result = pd.DataFrame(output_rows)

drop_cols = [
    col
    for col in ["BOOKNUMBER", "person_key"]
    if col in result.columns
]

result = result.drop(columns=drop_cols)

result = result.sort_values(
    ["BookNumber", "WindowStartDate"]
)

date_cols = [
    "WindowStartDate",
    "WindowStartDateCpy",
    "WindowEndDate"
]

for col in date_cols:
    if col in result.columns:
        result[col] = pd.to_datetime(result[col]).dt.strftime("%-m/%-d/%Y")

result.to_csv(
    OUTPUT_FILE,
    index=False
)

print(f"Saved: {OUTPUT_FILE}")
print(f"Rows: {len(result):,}")

matched_detox = detox["person_key"].isin(
    housing["person_key"]
).sum()

print("\nQA SUMMARY")
print("-" * 40)
print(f"Bookings: {housing['BookNumber'].nunique():,}")
print(f"Housing Rows Input: {len(housing):,}")
print(f"Detox Records: {len(detox):,}")
print(f"Matched Detox Records: {matched_detox:,}")
print(f"Output Rows: {len(result):,}")

unmatched = detox[
    ~detox["person_key"].isin(housing["person_key"])
]

unmatched.to_csv(
    r"C:\lwf\sbx-data-vis\data\input\detox_unmatched.csv",
    index=False
)