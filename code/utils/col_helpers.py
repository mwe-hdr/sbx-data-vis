import pandas as pd
import logging

logger = logging.getLogger(__name__)

def add_calculated_helper_columns(df):

    if "esi" in df.columns:

        df["valid_esi"] = (
            df["esi"]
            .isin([0, 1, 2, 3, 4, 5])
        )

    if (
        "arrival_dtm" in df.columns
        and
        "tmt_stop_dtm" in df.columns
    ):

        logger.info(
            f"[col] arrival_dtm dtype="
            f"{df['arrival_dtm'].dtype}"
        )

        logger.info(
            f"[col] tmt_stop_dtm dtype="
            f"{df['tmt_stop_dtm'].dtype}"
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
            df["los_hours"].notna()
            &
            (df["los_hours"] >= 0)
        )

    if "triage_start_dtm" in df.columns:

        df["has_triage"] = (
            df["triage_start_dtm"].notna()
        )

    if "tmt_start_dtm" in df.columns:

        df["has_ed"] = (
            df["tmt_start_dtm"].notna()
        )

    return df

def add_date_helper_columns(df):

    if "arrival_dtm" not in df.columns:
        return df

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

    df["arrival_day_of_week"] = (
        dt.dt.day_name()
    )

    return df

def prepare_common_columns(df):

    if "arrival_dtm" in df.columns:

        if not pd.api.types.is_datetime64_any_dtype(
            df["arrival_dtm"]
        ):
            raise TypeError(
                "arrival_dtm must be datetime before "
                "calling prepare_common_columns()"
            )

    df = add_calculated_helper_columns(df)

    df = add_date_helper_columns(df)

    return df