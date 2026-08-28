import pandas as pd

# ============================================================
# Files
# ============================================================

BOOKINGS_FILE = (
    r"C:\lwf\sbx-data-vis\data\input\lc_adf_20260824\INMATES_BOOKED.CSV"
)

HOUSING_FILE = (
    r"C:\lwf\sbx-data-vis\data\input\lc_adf_housing_history_flat.csv"
)

CLASS_FILE = (
    r"C:\lwf\sbx-data-vis\data\input\lc_adf_class_pod_history_flat_enriched.csv"
)

OUTPUT_FILE = (
    r"C:\lwf\sbx-data-vis\data\input\lc_adf_booking_housing_classification.csv"
)

FUTURE_DATE = pd.Timestamp("2099-12-31")

# ============================================================
# Load bookings
# ============================================================

bookings = pd.read_csv(
    BOOKINGS_FILE,
    parse_dates=[
        "BOOKINGDATE",
        "RELEASEDATE"
    ]
)

bookings["BOOKNUMBER"] = (
    bookings["BOOKNUMBER"]
    .astype(str)
    .str.strip()
)

bookings["RELEASEDATE"] = (
    bookings["RELEASEDATE"]
    .fillna(FUTURE_DATE)
)

bookings = bookings.rename(
    columns={
        "BOOKNUMBER": "BookNumber",
        "BOOKINGDATE": "BookingStart",
        "RELEASEDATE": "BookingEnd",
        "SEX": "Sex"
    }
)

# ============================================================
# Load housing
# ============================================================

housing = pd.read_csv(
    HOUSING_FILE,
    parse_dates=[
        "HOUSING_START_DATE",
        "HOUSING_END_DATE"
    ]
)

housing = housing.rename(
    columns={
        "BOOK#": "BookNumber",
        "HOUSING_START_DATE": "HousingStart",
        "HOUSING_END_DATE": "HousingEnd"
    }
)

housing["BookNumber"] = (
    housing["BookNumber"]
    .astype(str)
    .str.strip()
)

# ============================================================
# Load classification
# ============================================================

classification = pd.read_csv(
    CLASS_FILE,
    parse_dates=[
        "WindowStartDate",
        "WindowEndDate"
    ]
)

classification = classification.rename(
    columns={
        "custody_class": "CustodyClass",
        "WindowStartDate": "ClassStart",
        "WindowEndDate": "ClassEnd"
    }
)

classification["BookNumber"] = (
    classification["BookNumber"]
    .astype(str)
    .str.strip()
)

# ============================================================
# Build final result
# ============================================================

results = []

for _, booking in bookings.iterrows():

    book_no = booking["BookNumber"]

    booking_start = booking["BookingStart"]
    booking_end = booking["BookingEnd"]

    sex = booking["Sex"]

    h = housing[housing["BookNumber"] == book_no].copy()
    c = classification[classification["BookNumber"] == book_no].copy()

    # --------------------------------------------------------
    # Case 1
    # No housing and no classification
    # --------------------------------------------------------

    if len(h) == 0 and len(c) == 0:

        results.append({
            "BookNumber": book_no,
            "Sex": sex,
            "SegmentStart": booking_start,
            "SegmentEnd": booking_end,
            "Housing": None,
            "CustodyClass": None
        })

        continue

    # --------------------------------------------------------
    # Housing only
    # --------------------------------------------------------

    if len(h) > 0 and len(c) == 0:

        for _, hh in h.iterrows():

            results.append({
                "BookNumber": book_no,
                "Sex": sex,
                "SegmentStart": max(
                    booking_start,
                    hh["HousingStart"]
                ),
                "SegmentEnd": min(
                    booking_end,
                    hh["HousingEnd"]
                ),
                "Housing": hh["HOUSING"],
                "CustodyClass": None
            })

        continue

    # --------------------------------------------------------
    # Classification only
    # --------------------------------------------------------

    if len(h) == 0 and len(c) > 0:

        for _, cc in c.iterrows():

            results.append({
                "BookNumber": book_no,
                "Sex": sex,
                "SegmentStart": max(
                    booking_start,
                    cc["ClassStart"]
                ),
                "SegmentEnd": min(
                    booking_end,
                    cc["ClassEnd"]
                ),
                "Housing": None,
                "CustodyClass": cc["CustodyClass"]
            })

        continue

    # --------------------------------------------------------
    # Housing + Classification
    # --------------------------------------------------------

    pairwise = h.merge(
        c,
        how="cross"
    )

    overlap = (
        (pairwise["HousingStart"] <= pairwise["ClassEnd"])
        &
        (pairwise["HousingEnd"] >= pairwise["ClassStart"])
    )

    pairwise = pairwise.loc[overlap]

    for _, row in pairwise.iterrows():

        seg_start = max(
            booking_start,
            row["HousingStart"],
            row["ClassStart"]
        )

        seg_end = min(
            booking_end,
            row["HousingEnd"],
            row["ClassEnd"]
        )

        if seg_start <= seg_end:

            results.append({
                "BookNumber": book_no,
                "Sex": sex,
                "SegmentStart": seg_start,
                "SegmentEnd": seg_end,
                "Housing": row["HOUSING"],
                "CustodyClass": row["CustodyClass"]
            })

# ============================================================
# Save
# ============================================================

final_df = pd.DataFrame(results)

final_df = final_df.sort_values(
    ["BookNumber", "SegmentStart"]
)

final_df.to_csv(
    OUTPUT_FILE,
    index=False
)

print(f"Output rows: {len(final_df):,}")
print(f"Output file: {OUTPUT_FILE}")