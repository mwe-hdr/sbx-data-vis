import pandas as pd
import numpy as np

# ============================================================
# Configuration
# ============================================================

INPUT_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf_20260824\CLASSIFICATION_HISTORY.CSV"

DAILY_EVENTS_OUTPUT = r"C:\lwf\sbx-data-vis\data\input\lc_adf_20260824\daily_classification_events.csv"

WINDOWS_OUTPUT = r"C:\lwf\sbx-data-vis\data\input\lc_adf_class_history_flat.csv"

# ============================================================
# Load Data
# ============================================================

df = pd.read_csv(INPUT_FILE)

# Standardize column names
df.columns = [c.strip() for c in df.columns]

# Convert date field
df["ReviewDate"] = pd.to_datetime(df["ReviewDate"])

# Convert custody level to numeric
df["FinalCustodyLevel"] = pd.to_numeric(
    df["FinalCustodyLevel"],
    errors="coerce"
)

# Remove rows without a final custody level
df = df[df["FinalCustodyLevel"].notna()].copy()

# ============================================================
# STEP 1
# Force one review event per inmate per day
# Retain highest FinalCustodyLevel observed that day
# ============================================================

daily_events = (
    df.sort_values(
        ["BOOK#", "ReviewDate", "FinalCustodyLevel"],
        ascending=[True, True, False]
    )
    .drop_duplicates(
        subset=["BOOK#", "ReviewDate"],
        keep="first"
    )
    .sort_values(["BOOK#", "ReviewDate"])
    .reset_index(drop=True)
)

daily_events.to_csv(
    DAILY_EVENTS_OUTPUT,
    index=False
)

# ============================================================
# STEP 2
# Create custody classification windows
# A new window begins whenever FinalCustodyLevel changes
# ============================================================

daily_events = daily_events.sort_values(
    ["BOOK#", "ReviewDate"]
).copy()

daily_events["PrevCustodyLevel"] = (
    daily_events.groupby("BOOK#")["FinalCustodyLevel"]
    .shift(1)
)

daily_events["LevelChanged"] = (
    daily_events["FinalCustodyLevel"]
    != daily_events["PrevCustodyLevel"]
)

daily_events["WindowID"] = (
    daily_events.groupby("BOOK#")["LevelChanged"]
    .cumsum()
)

# ============================================================
# Aggregate windows
# ============================================================

windows = (
    daily_events
    .groupby(
        ["BOOK#", "WindowID", "FinalCustodyLevel"],
        as_index=False
    )
    .agg(
        WindowStartDate=("ReviewDate", "min"),
        WindowEndDate=("ReviewDate", "max"),
        ReviewCount=("ReviewDate", "size")
    )
)

windows["DaysInWindow"] = (
    windows["WindowEndDate"]
    - windows["WindowStartDate"]
).dt.days + 1

windows = windows.rename(
    columns={
        "BOOK#": "BookNumber",
        "FinalCustodyLevel": "CustodyLevel"
    }
)

windows = windows.sort_values(
    ["BookNumber", "WindowStartDate"]
)

# ============================================================
# Save Output
# ============================================================

windows.to_csv(
    WINDOWS_OUTPUT,
    index=False
)

print(f"Daily events written to: {DAILY_EVENTS_OUTPUT}")
print(f"Custody windows written to: {WINDOWS_OUTPUT}")
print(f"Windows created: {len(windows):,}")