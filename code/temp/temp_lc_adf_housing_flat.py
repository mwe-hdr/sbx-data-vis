import pandas as pd
from datetime import timedelta

HOUSING_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf_20260824\HOUSING_HISTORY.CSV"
BOOKINGS_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf_20260824\INMATES_BOOKED.CSV"
OUTPUT_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf_housing_history_flat.csv"

# Read housing history
df = pd.read_csv(HOUSING_FILE)

# Read booking file
bookings = pd.read_csv(
    BOOKINGS_FILE,
    parse_dates=["RELEASEDATE"]
)

# Normalize booking number fields
df["BOOK#"] = df["BOOK#"].astype(str).str.strip()
bookings["BOOKNUMBER"] = bookings["BOOKNUMBER"].astype(str).str.strip()

# Use 2099-12-31 for active inmates with no release date
bookings["RELEASEDATE"] = bookings["RELEASEDATE"].fillna(
    pd.Timestamp("2099-12-31")
)

# Create lookup dictionary
booking_lookup = (
    bookings[["BOOKNUMBER", "RELEASEDATE", "SEX"]]
    .drop_duplicates(subset=["BOOKNUMBER"])
    .set_index("BOOKNUMBER")
    .to_dict("index")
)

# Parse housing dates
df["ADATE"] = pd.to_datetime(df["ADATE"])

# Sort chronologically
df = df.sort_values(["BOOK#", "ADATE"])

results = []

for book_no, grp in df.groupby("BOOK#", sort=False):

    grp = grp[["BOOK#", "POD", "ADATE"]].copy()

    # Remove consecutive duplicate housing assignments
    grp = grp.loc[
        (grp["POD"] != grp["POD"].shift()) |
        (grp["POD"].shift().isna())
    ].reset_index(drop=True)

    booking_info = booking_lookup.get(
        str(book_no).strip(),
        {
            "RELEASEDATE": pd.Timestamp("2099-12-31"),
            "SEX": None
        }
    )

    release_date = booking_info["RELEASEDATE"]
    sex = booking_info["SEX"]

    for i in range(len(grp)):

        housing = grp.loc[i, "POD"]
        start_date = grp.loc[i, "ADATE"]

        if i < len(grp) - 1:
            end_date = max(
                start_date,
                grp.loc[i + 1, "ADATE"] - timedelta(days=1)
            )
        else:
            if release_date < start_date:
                print(
                    f"WARNING: BOOK# {book_no} "
                    f"release date {release_date:%Y-%m-%d} "
                    f"before housing start {start_date:%Y-%m-%d}"
                )

            end_date = max(start_date, release_date)

        results.append({
            "BOOK#": book_no,
            "SEX": sex,
            "HOUSING": housing,
            "HOUSING_START_DATE": start_date,
            "HOUSING_END_DATE": end_date
        })

out_df = pd.DataFrame(results)

out_df.to_csv(OUTPUT_FILE, index=False)

print(f"Wrote {len(out_df):,} rows to {OUTPUT_FILE}")
print(f"Bookings loaded: {len(booking_lookup):,}")