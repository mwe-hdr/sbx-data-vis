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
        f"[DATE HELPER] Filtering null arrival_dtm values. Rows before filter: {len(df):,}"
    )

    df = df[
        df["arrival_dtm"].notna()
    ].copy()

    logger.info(
        f"[DATE HELPER] Completed arrival_dtm null filter. Rows after filter: {len(df):,}"
    )

    if start_date.time() == datetime.time(0,0):
        end_date = (
            end_date
            + pd.Timedelta(days=1)
            - pd.Timedelta(minutes=1)
        )

    logger.info(
        f"[DATE HELPER] Applying arrival_dtm date filter. "
        f"Start={start_date}, End={end_date}, Rows before filter: {len(df):,}"
    )

    df = df[
        (df["arrival_dtm"] >= start_date) &
        (df["arrival_dtm"] <= end_date)
    ].copy()

    logger.info(
        f"[DATE HELPER] Completed arrival_dtm date filter. Rows after filter: {len(df):,}"
    )

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

