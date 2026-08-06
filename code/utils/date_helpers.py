import os
import pandas as pd
import logging
import datetime
logger = logging.getLogger(__name__)

def prepare_dates(
    df,
    start_date,
    end_date
):

    def add_date_columns(df):
        dt = df["arrival_dtm"]

        df["arrival_hour"] = dt.dt.hour
        df["arrival_year"] = dt.dt.year
        df["arrival_month"] = dt.dt.month

        df["arrival_year_month"] = (
            dt.dt.to_period("M")
            .dt.to_timestamp()
        )

        df["arrival_weekday_num"] = dt.dt.dayofweek

        df["arrival_weekday"] = (
            dt.dt.day_name()
            .str[:3]
        )

        df["arrival_day_of_week"] = dt.dt.day_name()

        return df

    if "arrival_dtm" not in df.columns:
        raise ValueError("arrival_dtm column is required")

    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

    date_columns = [
    "arrival_dtm",
    "tmt_stop_dtm",
    "tmt_start_dtm",
    "triage_start_dtm"
    ]

    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(
                df[col],
                errors="coerce"
            )

    logger.info(
        f"[date helper] Filtering null arrival_dtm values. Rows before filter: {len(df):,}"
    )

    df = df[
        df["arrival_dtm"].notna()
    ].copy()

    logger.info(
        f"[date helper] Completed arrival_dtm null filter. Rows after filter: {len(df):,}"
    )

    if end_date.time() == datetime.time(0, 0):
        end_date = (
            end_date
            + pd.Timedelta(days=1)
            - pd.Timedelta(microseconds=1)
        )

    logger.info(
        f"[date helper] Applying arrival_dtm date filter. "
        f"Start={start_date}, End={end_date}, Rows before filter: {len(df):,}"
    )

    df_all = df.copy()

    df_filtered = df[
        (df["arrival_dtm"] >= start_date) &
        (df["arrival_dtm"] <= end_date)
    ].copy()

    logger.info(
        f"[date helper] Completed arrival_dtm date filter. "
        f"Start={start_date}, End={end_date}, Rows after filter: {len(df_filtered):,}"
    )    

    df_all = add_date_columns(df_all)
    df_filtered = add_date_columns(df_filtered)

    logger.info(
        f"[date helper] Returning "
        f"{len(df_all):,} total rows and "
        f"{len(df_filtered):,} arrival-filtered rows."
    )

    return df_all, df_filtered

