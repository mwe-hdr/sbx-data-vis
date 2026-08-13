import os
import pandas as pd
import logging
import datetime
logger = logging.getLogger(__name__)

def df_date_splitter(
    df,
    start_date,
    end_date
):

    if "arrival_dtm" not in df.columns:
        raise ValueError(
            "arrival_dtm column is required"
        )

    logger.info(
        f"[date helper] Filtering null arrival_dtm values. "
        f"Rows before filter: {len(df):,}"
    )

    df_all = df[
        df["arrival_dtm"].notna()
    ].copy()

    logger.info(
        f"[date helper] Rows after null filter: "
        f"{len(df_all):,}"
    )

    df_filtered = df_all[
        (df_all["arrival_dtm"] >= start_date)
        &
        (df_all["arrival_dtm"] <= end_date)
    ].copy()

    logger.info(
        f"[date helper] Reporting window rows: "
        f"{len(df_filtered):,}"
    )

    return df_all, df_filtered

