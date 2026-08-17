import pandas as pd

bookings = pd.read_csv(
    r"C:\lwf\sbx-data-vis\data\input\lc_adf\INMATES_BOOKED.CSV",
    parse_dates=["BOOKINGDATE", "RELEASEDATE"]
)

cls = pd.read_csv(
    r"C:\lwf\sbx-data-vis\data\input\lc_adf_class_pod_history_flat.csv",
    parse_dates=["WindowStartDate", "WindowEndDate"]
)

bookings["BOOKNUMBER"] = bookings["BOOKNUMBER"].astype(str).str.strip()
cls["BookNumber"] = cls["BookNumber"].astype(str).str.strip()

# Restrict bookings to only inmates with classification history
classified_bookings = bookings.merge(
    cls[["BookNumber"]].drop_duplicates(),
    left_on="BOOKNUMBER",
    right_on="BookNumber",
    how="inner"
)

results = []

for _, booking in classified_bookings.iterrows():

    booknum = booking["BOOKNUMBER"]
    booking_start = booking["BOOKINGDATE"]
    booking_end = booking["RELEASEDATE"]

    windows = (
        cls.loc[cls["BookNumber"] == booknum]
        .sort_values(["WindowStartDate", "WindowEndDate"])
        .reset_index(drop=True)
    )

    if windows.empty:
        continue

    first = windows.iloc[0]

    # Backfill first observed classification to booking start
    results.append({
        "BookNumber": booknum,
        "Pod": first["Pod"],
        "WindowStartDate": booking_start,
        "WindowEndDate": first["WindowEndDate"]
    })

    prev_pod = first["Pod"]
    prev_end = first["WindowEndDate"]

    for i in range(1, len(windows)):

        row = windows.iloc[i]

        # Fill gap using prior classification
        if row["WindowStartDate"] > prev_end + pd.Timedelta(days=1):

            results.append({
                "BookNumber": booknum,
                "Pod": prev_pod,
                "WindowStartDate": prev_end + pd.Timedelta(days=1),
                "WindowEndDate": row["WindowStartDate"] - pd.Timedelta(days=1)
            })

        # Current classified window
        results.append({
            "BookNumber": booknum,
            "Pod": row["Pod"],
            "WindowStartDate": row["WindowStartDate"],
            "WindowEndDate": row["WindowEndDate"]
        })

        prev_pod = row["Pod"]
        prev_end = row["WindowEndDate"]

    # Carry final classification through release
    if prev_end < booking_end:

        results.append({
            "BookNumber": booknum,
            "Pod": prev_pod,
            "WindowStartDate": prev_end + pd.Timedelta(days=1),
            "WindowEndDate": booking_end
        })

enriched = pd.DataFrame(results)

enriched = enriched.sort_values(
    ["BookNumber", "WindowStartDate"]
).reset_index(drop=True)

collapsed = []

for booknum, grp in enriched.groupby("BookNumber"):

    grp = grp.sort_values("WindowStartDate")

    current = grp.iloc[0].to_dict()

    for _, row in grp.iloc[1:].iterrows():

        contiguous = (
            row["WindowStartDate"]
            <= current["WindowEndDate"] + pd.Timedelta(days=1)
        )

        same_pod = (
            row["Pod"] == current["Pod"]
        )

        if contiguous and same_pod:

            current["WindowEndDate"] = max(
                current["WindowEndDate"],
                row["WindowEndDate"]
            )

        else:

            collapsed.append(current)
            current = row.to_dict()

    collapsed.append(current)

enriched = pd.DataFrame(collapsed)

enriched.to_csv(
    r"C:\lwf\sbx-data-vis\data\input\lc_adf_class_pod_history_flat_enriched.csv",
    index=False
)

print(f"Bookings processed: {len(classified_bookings):,}")
print(f"Output windows: {len(enriched):,}")