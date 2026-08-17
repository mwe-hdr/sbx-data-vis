import pandas as pd
import numpy as np

BOOKINGS_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf\INMATES_BOOKED.CSV"
HOUSING_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf_housing_history_flat.csv"
CLASS_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf_class_pod_history_flat.csv"
OUTPUT_FILE = r"C:\lwf\sbx-data-vis\data\output\booking_data_coverage.csv"

START_DATE = pd.Timestamp("2020-04-01")
END_DATE = pd.Timestamp("2026-06-10")


def merge_intervals(intervals):
    """
    Returns total covered days from a set of date intervals.
    Assumes intervals are inclusive of both start and end dates.
    """
    if not intervals:
        return 0

    intervals = sorted(intervals, key=lambda x: x[0])

    merged = [list(intervals[0])]

    for start, end in intervals[1:]:
        if start <= merged[-1][1] + pd.Timedelta(days=1):
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    return sum(
        (end - start).days + 1
        for start, end in merged
    )


# -------------------------------------------------------
# BOOKINGS
# -------------------------------------------------------

bookings = pd.read_csv(
    BOOKINGS_FILE,
    dtype={"BOOKNUMBER": str},
    low_memory=False
)

bookings["BOOKINGDATE"] = pd.to_datetime(
    bookings["BOOKINGDATE"],
    errors="coerce"
)

bookings["RELEASEDATE"] = pd.to_datetime(
    bookings["RELEASEDATE"],
    errors="coerce"
)

# Treat null release dates as still incarcerated
bookings["RELEASEDATE"] = bookings["RELEASEDATE"].fillna(END_DATE)

# Booking overlaps study window
booking_mask = (
    (bookings["BOOKINGDATE"] <= END_DATE) &
    (bookings["RELEASEDATE"] >= START_DATE)
)

bookings = bookings.loc[booking_mask].copy()

bookings["WINDOW_START"] = bookings["BOOKINGDATE"].clip(lower=START_DATE)
bookings["WINDOW_END"] = bookings["RELEASEDATE"].clip(upper=END_DATE)

bookings["INCARCERATION_DAYS"] = (
    bookings["WINDOW_END"] -
    bookings["WINDOW_START"]
).dt.days + 1

# -------------------------------------------------------
# HOUSING
# -------------------------------------------------------

housing = pd.read_csv(
    HOUSING_FILE,
    dtype={"BOOK#": str},
    low_memory=False
)

housing["HOUSING_START_DATE"] = pd.to_datetime(
    housing["HOUSING_START_DATE"],
    errors="coerce"
)

housing["HOUSING_END_DATE"] = pd.to_datetime(
    housing["HOUSING_END_DATE"],
    errors="coerce"
)

housing["HOUSING_END_DATE"] = housing["HOUSING_END_DATE"].fillna(END_DATE)

# -------------------------------------------------------
# CLASSIFICATION
# -------------------------------------------------------

classification = pd.read_csv(
    CLASS_FILE,
    dtype={"BookNumber": str},
    low_memory=False
)

classification["WindowStartDate"] = pd.to_datetime(
    classification["WindowStartDate"],
    errors="coerce"
)

classification["WindowEndDate"] = pd.to_datetime(
    classification["WindowEndDate"],
    errors="coerce"
)

classification["WindowEndDate"] = (
    classification["WindowEndDate"]
    .fillna(END_DATE)
)

# -------------------------------------------------------
# ANALYSIS
# -------------------------------------------------------

results = []

for row in bookings.itertuples(index=False):

    booknum = row.BOOKNUMBER
    inc_start = row.WINDOW_START
    inc_end = row.WINDOW_END
    inc_days = row.INCARCERATION_DAYS

    # -------------------------
    # HOUSING
    # -------------------------

    h = housing[housing["BOOK#"] == booknum]

    housing_intervals = []

    for r in h.itertuples(index=False):

        overlap_start = max(
            inc_start,
            r.HOUSING_START_DATE
        )

        overlap_end = min(
            inc_end,
            r.HOUSING_END_DATE
        )

        if overlap_start <= overlap_end:
            housing_intervals.append(
                (overlap_start, overlap_end)
            )

    housing_days = merge_intervals(housing_intervals)

    # -------------------------
    # CLASSIFICATION
    # -------------------------

    c = classification[
        classification["BookNumber"] == booknum
    ]

    class_intervals = []

    for r in c.itertuples(index=False):

        overlap_start = max(
            inc_start,
            r.WindowStartDate
        )

        overlap_end = min(
            inc_end,
            r.WindowEndDate
        )

        if overlap_start <= overlap_end:
            class_intervals.append(
                (overlap_start, overlap_end)
            )

    class_days = merge_intervals(class_intervals)

    has_housing_records = len(h) > 0
    has_class_records = len(c) > 0

    housing_gap_days = max(
        inc_days - housing_days,
        0
    )

    class_gap_days = max(
        inc_days - class_days,
        0
    )

    housing_pct = (
        round(100 * housing_days / inc_days, 2)
        if inc_days > 0 else 0
    )

    class_pct = (
        round(100 * class_days / inc_days, 2)
        if inc_days > 0 else 0
    )

    results.append({
        "BOOKNUMBER": booknum,

        "INCARCERATION_START": inc_start.date(),
        "INCARCERATION_END": inc_end.date(),
        "INCARCERATION_DAYS": inc_days,

        # -------------------------
        # HOUSING
        # -------------------------
        "HAS_HOUSING_RECORDS": has_housing_records,
        "HAS_HOUSING_OVERLAP": housing_days > 0,
        "HOUSING_COVERED_DAYS": housing_days,
        "HOUSING_GAP_DAYS": housing_gap_days,
        "HOUSING_COVERAGE_PCT": housing_pct,
        "FULL_HOUSING_COVERAGE_FLAG":
            housing_days >= inc_days,

        # -------------------------
        # CLASSIFICATION
        # -------------------------
        "HAS_CLASS_RECORDS": has_class_records,
        "HAS_CLASS_OVERLAP": class_days > 0,
        "CLASS_COVERED_DAYS": class_days,
        "CLASS_GAP_DAYS": class_gap_days,
        "CLASS_COVERAGE_PCT": class_pct,
        "FULL_CLASS_COVERAGE_FLAG":
            class_days >= inc_days,

        # -------------------------
        # AUDIT FLAGS
        # -------------------------
        "MISSING_BOTH_FLAG":
            (housing_days == 0 and class_days == 0),

        "MISSING_HOUSING_FLAG":
            (housing_days == 0),

        "MISSING_CLASS_FLAG":
            (class_days == 0),

        "ANY_DATA_GAP_FLAG":
            (
                housing_days < inc_days
                or
                class_days < inc_days
            )
    })

results_df = pd.DataFrame(results)

results_df.to_csv(
    OUTPUT_FILE,
    index=False
)

print()
print("================================================")
print("DATA QUALITY SUMMARY")
print("================================================")

total = len(results_df)

print(f"Bookings analyzed: {total:,}")

print(
    f"Bookings with housing records: "
    f"{results_df['HAS_HOUSING_RECORDS'].sum():,}"
)

print(
    f"Bookings with classification records: "
    f"{results_df['HAS_CLASS_RECORDS'].sum():,}"
)

print(
    f"Bookings missing housing coverage: "
    f"{results_df['MISSING_HOUSING_FLAG'].sum():,}"
)

print(
    f"Bookings missing classification coverage: "
    f"{results_df['MISSING_CLASS_FLAG'].sum():,}"
)

print(
    f"Bookings missing BOTH sources: "
    f"{results_df['MISSING_BOTH_FLAG'].sum():,}"
)

print(
    f"Fully covered by housing: "
    f"{results_df['FULL_HOUSING_COVERAGE_FLAG'].sum():,}"
)

print(
    f"Fully covered by classification: "
    f"{results_df['FULL_CLASS_COVERAGE_FLAG'].sum():,}"
)

print(
    f"Average housing coverage %: "
    f"{results_df['HOUSING_COVERAGE_PCT'].mean():.2f}"
)

print(
    f"Average classification coverage %: "
    f"{results_df['CLASS_COVERAGE_PCT'].mean():.2f}"
)

print(
    f"Bookings with any gap: "
    f"{results_df['ANY_DATA_GAP_FLAG'].sum():,}"
)