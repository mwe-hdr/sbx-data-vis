import pandas as pd
import numpy as np

# ============================================================
# Configuration
# ============================================================

INPUT_FILE = r"C:\lwf\sbx-data-vis\data\input\lc_adf\CLASSIFICATION_HISTORY.CSV"

DAILY_EVENTS_OUTPUT = (
    r"C:\lwf\sbx-data-vis\data\input\lc_adf\daily_pod_events.csv"
)

WINDOWS_OUTPUT = (
    r"C:\lwf\sbx-data-vis\data\input\lc_adf_class_pod_history_flat.csv"
)

# ============================================================
# Load Data
# ============================================================

df = pd.read_csv(INPUT_FILE)

df.columns = [c.strip() for c in df.columns]

df["ReviewDate"] = pd.to_datetime(df["ReviewDate"])

df["Score"] = pd.to_numeric(df["Score"], errors="coerce")

# ============================================================
# Create EffectivePod
# FinalPod takes precedence, otherwise RecPod
# ============================================================

df["FinalPod"] = (
    df["FinalPod"]
    .replace("", np.nan)
    .astype("string")
)

df["RecPod"] = (
    df["RecPod"]
    .replace("", np.nan)
    .astype("string")
)

df["EffectivePod"] = df["FinalPod"].fillna(df["RecPod"])

# Remove records with no identifiable pod
df = df[df["EffectivePod"].notna()].copy()

# ============================================================
# Daily Record Selection Logic
# ============================================================

def select_daily_record(group):

    if group["FinalPod"].notna().any():
        group = group[group["FinalPod"].notna()]

    return group.sort_values(
        "Score",
        ascending=False,
        na_position="last"
    ).head(1)

selected_rows = []

for _, group in df.groupby(["BOOK#", "ReviewDate"]):

    if group["FinalPod"].notna().any():
        group = group[group["FinalPod"].notna()]

    selected_rows.append(
        group.sort_values(
            "Score",
            ascending=False,
            na_position="last"
        ).iloc[0]
    )

daily_events = pd.DataFrame(selected_rows)

daily_events = daily_events.reset_index(drop=True)

daily_events = daily_events.sort_values(
    ["BOOK#", "ReviewDate"]
)

# ============================================================
# Create Pod Windows
#
# Start a new window whenever EffectivePod changes
# ============================================================

daily_events["PrevPod"] = (
    daily_events.groupby("BOOK#")["EffectivePod"]
    .shift(1)
)

daily_events["PodChanged"] = (
    daily_events["EffectivePod"]
    != daily_events["PrevPod"]
)

daily_events["WindowID"] = (
    daily_events.groupby("BOOK#")["PodChanged"]
    .cumsum()
)

# ============================================================
# Aggregate Windows
# ============================================================

windows = (
    daily_events
    .groupby(
        ["BOOK#", "WindowID", "EffectivePod"],
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
        "EffectivePod": "Pod"
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

print(f"Daily pod events written to: {DAILY_EVENTS_OUTPUT}")
print(f"Pod windows written to: {WINDOWS_OUTPUT}")
print(f"Windows created: {len(windows):,}")