import os
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from utils.vis_helpers import format_date_range

VISUAL_ID = "vis_10"
logger = logging.getLogger(__name__)


def _safe_param(params, key, default, cast_type=None):
    try:
        val = params.get(key, default)
        return cast_type(val) if cast_type else val
    except Exception:
        logger.warning(f"Invalid param for {key}; using default {default}")
        return default


def _generate_census(df, start_date, end_date):
    """
    Minimal vis_08-equivalent census generation.
    Builds hourly time-series census from encounter windows.
    """
    try:
        df = df.copy()

        # =========================================================
        # VALIDATION
        # =========================================================
        if not all(col in df.columns for col in ["ed_start_dtm", "ed_stop_dtm"]):
            logging.error(f"[{VISUAL_ID}] Missing required columns")
            return

        # =========================================================
        # DATETIME PREP
        # =========================================================
        df["ed_start_dtm"] = pd.to_datetime(df["ed_start_dtm"], errors="coerce")
        df["ed_stop_dtm"] = pd.to_datetime(df["ed_stop_dtm"], errors="coerce")

        df = df.dropna(subset=["ed_start_dtm", "ed_stop_dtm"])

        invalid_mask = df["ed_stop_dtm"] < df["ed_start_dtm"]
        zero_mask = df["ed_stop_dtm"] == df["ed_start_dtm"]

        df.loc[invalid_mask, "ed_stop_dtm"] = (
            df.loc[invalid_mask, "ed_start_dtm"] + pd.Timedelta(minutes=1)
        )
        df.loc[zero_mask, "ed_stop_dtm"] = (
            df.loc[zero_mask, "ed_start_dtm"] + pd.Timedelta(minutes=1)
        )

        if "encounter_id" in df.columns:
            df = df.drop_duplicates(subset=["encounter_id"])

        # =========================================================
        # DATE RANGE
        # =========================================================
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        if end_date.hour == 0 and end_date.minute == 0 and end_date.second == 0:
            end_date = end_date + pd.Timedelta(days=1) - pd.Timedelta(minutes=1)

        # =========================================================
        # FILTER
        # =========================================================
        df = df[
            (df["ed_start_dtm"] <= end_date) &
            (df["ed_stop_dtm"] >= start_date)
        ].copy()

        if df.empty:
            logging.warning(f"[{VISUAL_ID}] No data after filtering")
            return

        # =========================================================
        # VISIT WINDOWS
        # =========================================================
        df["start"] = df["ed_start_dtm"]
        df["end"] = df["ed_stop_dtm"]

        df["end"] = df["end"].clip(lower=start_date, upper=end_date)
        df["end"] = df["end"] + pd.Timedelta(minutes=1)

        # =========================================================
        # TIME GRID
        # =========================================================
        intervals = pd.date_range(start=start_date, end=end_date, freq="min")
        base = pd.DataFrame({"interval": intervals})

        # =========================================================
        # EVENTS
        # =========================================================
        start_events = df[["start"]].rename(columns={"start": "interval"})
        start_events["delta"] = 1

        end_events = df[["end"]].rename(columns={"end": "interval"})
        end_events["delta"] = -1

        events = pd.concat([start_events, end_events])

        events = events[
            (events["interval"] >= start_date) &
            (events["interval"] <= end_date)
        ]

        events = (
            events.groupby("interval", as_index=False)["delta"]
            .sum()
            .sort_values("interval")
        )

        # =========================================================
        # MERGE + CENSUS
        # =========================================================
        ts = base.merge(events, on="interval", how="left")
        ts["delta"] = ts["delta"].fillna(0)

        initial_count = df[
            (df["ed_start_dtm"] < start_date) &
            (df["ed_stop_dtm"] >= start_date)
        ].shape[0]

        ts["census"] = ts["delta"].cumsum()
        ts["census"] += initial_count

        ts["census"] = (
            pd.to_numeric(ts["census"], errors="coerce")
            .round()
            .astype("Int64")
        )

        return ts

    except Exception as e:
        logger.error(f"Census generation failed: {e}")
        return pd.DataFrame()


def run(df, params, start_date, end_date, output_dir, generate_output_name):
    logger.info(f"[{VISUAL_ID}] Starting run")

    try:
        if df is None or df.empty:
            logger.warning("Input dataframe is empty")
            return

        # =========================
        # PARAMETERS
        # =========================
        growth = _safe_param(params, "variable_10_year_growth", 0.0, float)
        peak_start = _safe_param(params, "peak_period_start", 15, int)
        peak_len = _safe_param(params, "peak_period_length_hours", 8, int)
        utilization = _safe_param(params, "utilization", 0.85, float)

        fig_width = _safe_param(params, "fig_width", 14, float)
        fig_height = _safe_param(params, "fig_height", 7, float)
        dpi = _safe_param(params, "dpi", 100, int)

        colors = {
            "peak": params.get("peak_bar_color", "teal"),
            "offpeak": params.get("offpeak_bar_color", "gray"),
            "p70": params.get("p70_color", "green"),
            "p80": params.get("p80_color", "yellow"),
            "p90": params.get("p90_color", "orange"),
            "peak_line": params.get("peak_line_color", "darkblue"),
            "room_need": params.get("room_need_color", "magenta"),
        }

        # =========================
        # STEP 1: Census 
        # =========================
        ts = _generate_census(df, start_date, end_date)

        if ts.empty:
            logger.warning("Census dataset empty after generation")
            return

        # =========================
        # STEP 2: ADS Construction
        # =========================
        ts["interval"] = pd.to_datetime(ts["interval"], errors="coerce")
        ts = ts.dropna(subset=["interval", "census"])
        ts = ts[ts["census"] >= 0]

        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        ts = ts[(ts["interval"] >= start_date) & (ts["interval"] <= end_date)]

        if ts.empty:
            logger.warning("Dataset empty after date filtering")
            return

        # Growth adjustment
        ts["adj_census"] = ts["census"] * (1 + growth)

        # Hour extraction
        ts["hour"] = ts["interval"].dt.hour

        # Hourly aggregation
        hourly = (
            ts.groupby("hour")["adj_census"]
            .mean()
            .reindex(range(24), fill_value=0)
            .reset_index()
        )

        hourly.columns = ["hour", "hourly_census"]

        # Validate 24 hours
        if len(hourly) != 24:
            logger.warning("Hourly completeness issue; enforced 24 hours")

        # =========================
        # Peak classification
        # =========================
        def is_peak(hour):
            end = peak_start + peak_len
            if end <= 24:
                return peak_start <= hour < end
            else:
                return (hour >= peak_start) or (hour < (end - 24))

        hourly["peak_flag"] = hourly["hour"].apply(
            lambda h: "Peak" if is_peak(h) else "Off-Peak"
        )

        # =========================
        # Percentiles
        # =========================
        percentiles = (
            ts.groupby("hour")["adj_census"]
            .agg(
                p70=lambda x: np.percentile(x, 70),
                p80=lambda x: np.percentile(x, 80),
                p90=lambda x: np.percentile(x, 90),
            )
            .reindex(range(24))
            .reset_index()
        )

        hourly = hourly.merge(percentiles, on="hour", how="left")

        # =========================
        # Capacity metrics
        # =========================
        peak_values = hourly.loc[hourly["peak_flag"] == "Peak", "hourly_census"]
        peak_census = peak_values.max()

        room_need = peak_census / utilization if utilization > 0 else peak_census

        if utilization < 1:
            room_need = max(room_need, peak_census)

        logger.info(
            f"[{VISUAL_ID}] Capacity Metrics | "
            f"Peak Census: {round(peak_census, 2)} | "
            f"Room Need: {round(room_need, 2)} | "
            f"Utilization: {utilization}"
        )

        # =========================
        # Plot
        # =========================
        fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)

        # Bars
        peak_mask = hourly["peak_flag"] == "Peak"

        ax.bar(
            hourly.loc[~peak_mask, "hour"],
            hourly.loc[~peak_mask, "hourly_census"],
            color=colors["offpeak"],
            label="Off-Peak",
        )

        ax.bar(
            hourly.loc[peak_mask, "hour"],
            hourly.loc[peak_mask, "hourly_census"],
            color=colors["peak"],
            label="Peak",
        )

        # Percentiles
        ax.plot(hourly["hour"], hourly["p70"], linestyle="--", color=colors["p70"], label="P70")
        ax.plot(hourly["hour"], hourly["p80"], linestyle="--", color=colors["p80"], label="P80")
        ax.plot(hourly["hour"], hourly["p90"], linestyle="--", color=colors["p90"], label="P90")

        # Capacity lines
        peak_hours = hourly[hourly["peak_flag"] == "Peak"]["hour"]

        ax.plot(
            peak_hours,
            [peak_census] * len(peak_hours),
            color=colors["peak_line"],
            linewidth=2,
            label="Peak Census",
        )

        ax.plot(
            peak_hours,
            [room_need] * len(peak_hours),
            color=colors["room_need"],
            linestyle="-.",
            linewidth=2,
            label="Room Need",
        )

        # Labels
        date_range_str = format_date_range(start_date, end_date)

        ax.set_title(
            f"ED Hourly Census with Peak Period and Capacity Benchmarks {date_range_str}"
        )
        ax.set_xlabel("Hour of Day")
        ax.set_ylabel("ED Census")

        ax.set_xticks(range(24))

        ax.legend()

        plt.tight_layout()

        # =========================
        # Save output
        # =========================
        output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id=VISUAL_ID,
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        plt.savefig(output_file)
        plt.close()

        logger.info(f"[{VISUAL_ID}] Output saved to {output_file}")

        # =========================
        # RDB OUTPUT
        # =========================
        write_rdb = int(params.get("write_rdb", 0))
        rdb_rows = []

        if write_rdb == 1:

            report_title = (
                "ED Hourly Census with Peak Period and Capacity Benchmarks"
            )

            # ----------------------------------
            # Hourly census values
            # ----------------------------------
            for _, row in hourly.iterrows():

                hour_label = f"{int(row['hour']):02d}:00"

                rdb_rows.append({
                    "run_id": params.get("run_id"),
                    "visual_id": VISUAL_ID,
                    "client_name": params.get("client_name"),

                    "domain": params.get("domain"),
                    "cohort_id": params.get("cohort_id"),

                    "domain_cohort":
                        f"{params.get('domain')}.{params.get('cohort_id')}",

                    "dimension": "hour",
                    "dimension_value": int(row["hour"]),
                    "dimension_value_label": hour_label,

                    "secondary_dimension": "period_type",
                    "secondary_dimension_value": row["peak_flag"],

                    "metric": "hourly_census",
                    "metric_type": "average",
                    "value": float(row["hourly_census"]),

                    "start_date": start_date,
                    "end_date": end_date,

                    "report_title": report_title
                })

            # ----------------------------------
            # Percentiles
            # ----------------------------------
            for _, row in hourly.iterrows():

                hour_label = f"{int(row['hour']):02d}:00"

                for metric_name in ["p70", "p80", "p90"]:

                    metric_value = row[metric_name]

                    if pd.isna(metric_value):
                        continue

                    rdb_rows.append({
                        "run_id": params.get("run_id"),
                        "visual_id": VISUAL_ID,
                        "client_name": params.get("client_name"),

                        "domain": params.get("domain"),
                        "cohort_id": params.get("cohort_id"),

                        "domain_cohort":
                            f"{params.get('domain')}.{params.get('cohort_id')}",

                        "dimension": "hour",
                        "dimension_value": int(row["hour"]),
                        "dimension_value_label": hour_label,

                        "secondary_dimension": "percentile",
                        "secondary_dimension_value": metric_name.upper(),

                        "metric": "hourly_census",
                        "metric_type": metric_name,
                        "value": float(metric_value),

                        "start_date": start_date,
                        "end_date": end_date,

                        "report_title": report_title
                    })

            # ----------------------------------
            # Peak Census Benchmark by Hour
            # ----------------------------------
            peak_hours_set = set(
                hourly.loc[
                    hourly["peak_flag"] == "Peak",
                    "hour"
                ]
            )            
            
            for _, row in hourly.iterrows():

                if row["hour"] not in peak_hours_set:
                    continue

                hour_label = f"{int(row['hour']):02d}:00"

                rdb_rows.append({
                    "run_id": params.get("run_id"),
                    "visual_id": VISUAL_ID,
                    "client_name": params.get("client_name"),

                    "domain": params.get("domain"),
                    "cohort_id": params.get("cohort_id"),

                    "domain_cohort":
                        f"{params.get('domain')}.{params.get('cohort_id')}",

                    "dimension": "hour",
                    "dimension_value": int(row["hour"]),
                    "dimension_value_label": hour_label,

                    "secondary_dimension": "benchmark",
                    "secondary_dimension_value": "Peak Census",

                    "metric": "capacity",
                    "metric_type": "peak_census",
                    "value": float(peak_census),

                    "start_date": start_date,
                    "end_date": end_date,

                    "report_title": report_title
                })

            # ----------------------------------
            # Room Need Benchmark by Hour
            # ----------------------------------
            for _, row in hourly.iterrows():

                hour_label = f"{int(row['hour']):02d}:00"

                rdb_rows.append({
                    "run_id": params.get("run_id"),
                    "visual_id": VISUAL_ID,
                    "client_name": params.get("client_name"),

                    "domain": params.get("domain"),
                    "cohort_id": params.get("cohort_id"),

                    "domain_cohort":
                        f"{params.get('domain')}.{params.get('cohort_id')}",

                    "dimension": "hour",
                    "dimension_value": int(row["hour"]),
                    "dimension_value_label": hour_label,

                    "secondary_dimension": "benchmark",
                    "secondary_dimension_value": "Room Need",

                    "metric": "capacity",
                    "metric_type": "room_need",
                    "value": float(room_need),

                    "start_date": start_date,
                    "end_date": end_date,

                    "report_title": report_title
                })            

        return {
            "output_path": output_file,
            "rdb": rdb_rows
        }

    except Exception as e:
        logger.error(f"[{VISUAL_ID}] Execution failed: {e}")