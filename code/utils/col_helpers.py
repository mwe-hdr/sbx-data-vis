import pandas as pd
import logging
from utils.vis_helpers import map_arrival_method, map_disposition   
logger = logging.getLogger(__name__)

def add_common_helper_columns(df):

    df["esi"] = pd.to_numeric(
    df["esi"],
    errors="coerce"
    )

    ESI_MAP = {
    0: "0 - Unknown",
    1: "1 - Immediate",
    2: "2 - Emergent",
    3: "3 - Urgent",
    4: "4 - Less Urgent",
    5: "5 - Non-Urgent"
    }

    df["esi_category"] = (
        df["esi"]
        .map(ESI_MAP)
        .fillna("0 - Unknown")
    )

    df["valid_esi"] = (
    df["esi"]
    .isin([0,1,2,3,4,5])
    )

    df["arrival_method_clean"] = (
    df["arrival_method"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df["arrival_group"] = (
    df["arrival_method_clean"]
        .apply(map_arrival_method)
    )

    df["patient_zipcode"] = (
    df["patient_zipcode"]
      .astype(str)
      .str.strip()
      .str.zfill(5)
    )

    df["los_hours"] = (
    (
        df["tmt_stop_dtm"]
        - df["arrival_dtm"]
    )
    .dt.total_seconds()
    / 3600
    )

    df.loc[
    df["los_hours"] < 0,
    "los_hours"
    ] = pd.NA

    df["valid_los"] = (
    df["los_hours"]
    .notna()
    &
    (df["los_hours"] >= 0)
    )

    df["has_triage"] = (
    df["triage_start_dtm"].notna()
    )

    df["has_ed"] = (
    df["tmt_start_dtm"].notna()
    )

    df["disposition_group"] = (
    df["disch_disp_desc"]
        .apply(map_disposition)
    )

    return df