# =============================================================================
# Domain      : ED (Emergency Department)
# Report Name : ED Hourly Census with Peak Period and Capacity Benchmarks
#
# Description :
# Calculates Emergency Department census levels from patient arrival and
# departure timestamps and summarizes average census by hour of day. The
# report applies optional growth assumptions to projected census volumes,
# identifies user-defined peak operating periods, and evaluates capacity
# requirements based on target utilization thresholds.
#
# Hourly census profiles are generated from a minute-level census model
# and aggregated into average hourly occupancy values. The visualization
# highlights peak and off-peak periods and overlays percentile benchmarks
# to demonstrate expected census variation throughout the day.
#
# Key planning metrics include:
#   - Average hourly census
#   - Peak-period census
#   - 70th, 80th, and 90th percentile census levels
#   - Projected room requirements based on target utilization
#   - Growth-adjusted demand forecasts
#
# This report supports:
#   - ED capacity planning
#   - Space and room requirement analysis
#   - Throughput and occupancy monitoring
#   - Growth forecasting
#   - Peak demand assessment
#   - Strategic operational planning
#
# Inputs :
#   - ed_start_dtm            : ED arrival/start datetime
#   - ed_stop_dtm             : ED departure/stop datetime
#   - start_date              : Reporting period start date/time
#   - end_date                : Reporting period end date/time
#   - variable_10_year_growth : Projected growth adjustment factor
#   - utilization             : Target operational utilization rate
#   - peak_period_start       : Beginning hour of peak period
#   - peak_period_length_hours: Duration of peak period
#
# Outputs :
#   - PNG chart displaying:
#       * Average hourly census
#       * Peak and off-peak periods
#       * P70, P80, and P90 census benchmarks
#       * Peak census benchmark
#       * Estimated room need benchmark
#   - RDB records containing:
#       * Average hourly census values
#       * Hourly percentile benchmarks
#       * Peak census capacity benchmarks
#       * Estimated room need calculations
#
# Key Metrics :
#   - Average census by hour
#   - Peak census
#   - P70 census
#   - P80 census
#   - P90 census
#   - Peak-period occupancy
#   - Estimated room requirement
#   - Capacity utilization benchmark
# =============================================================================

import os
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from utils.vis_helpers import (
    normalize_params,
    format_date_range,
    apply_axis_range,
    apply_yaxis_format,
    save_legend_png,
    format_display_value,
    get_display_parameters,
    save_parameter_table_png,
    save_title_png
)
from utils.io_helpers import (
    load_data,
    load_driver,
    load_params,
    load_cohort_params
)

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
            return pd.DataFrame()

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
    params = normalize_params(params)

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
        font_family = _safe_param(
            params,
            "font_family",
            "Segoe UI",
            str
        )
        # ==================================
        # TITLE IMAGE PARAMETERS
        # ==================================

        title_width = _safe_param(
            params,
            "title_width",
            6.40,
            float
        )

        title_height = _safe_param(
            params,
            "title_height",
            0.25,
            float
        )

        title_fontsize = _safe_param(
            params,
            "title_fontsize",
            10,
            int
        )

        subtitle_fontsize = _safe_param(
            params,
            "subtitle_fontsize",
            8,
            int
        )

        title_background_color = params.get(
            "title_background_color",
            "#d9d9d9"
        )

        title_weight = params.get(
            "title_weight",
            "bold"
        )

        # ==================================
        # LEGEND PARAMETERS
        # ==================================

        legend_width = _safe_param(
            params,
            "legend_width",
            6,
            float
        )

        legend_height = _safe_param(
            params,
            "legend_height",
            1,
            float
        )

        legend_fontsize = _safe_param(
            params,
            "legend_fontsize",
            8,
            int
        )

        legend_ncol = _safe_param(
            params,
            "legend_ncol",
            4,
            int
        )

        # ==================================
        # TICK FORMATTING
        # ==================================

        tick_fontsize = _safe_param(
            params,
            "tick_fontsize",
            8,
            int
        )

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
        plt.rcParams["font.family"] = font_family

        fig, ax = plt.subplots(
            figsize=(fig_width, fig_height),
            dpi=dpi
        )

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

        ax.set_title("")
        ax.set_xlabel(
            "Hour of Day",
            fontfamily=font_family
        )
        ax.set_ylabel(
            "ED Census",
            fontfamily=font_family
        )

        ax.set_xticks(range(24))

        handles, labels = ax.get_legend_handles_labels()

        plt.tight_layout()
        for tick in ax.get_xticklabels():
            tick.set_fontfamily(font_family)
            tick.set_fontsize(tick_fontsize)

        for tick in ax.get_yticklabels():
            tick.set_fontfamily(font_family)
            tick.set_fontsize(tick_fontsize)

        y_axis_mode = params.get(
            "y_axis_mode",
            "raw"
        )

        y_axis_decimals = _safe_param(
            params,
            "y_axis_decimals",
            0,
            int
        )

        y_axis_multiplier = _safe_param(
            params,
            "y_axis_multiplier",
            1,
            float
        )

        y_axis_suffix = params.get(
            "y_axis_suffix",
            ""
        )
        apply_yaxis_format(
            ax,
            mode=y_axis_mode,
            decimals=y_axis_decimals,
            multiplier=y_axis_multiplier,
            suffix=y_axis_suffix
        )


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

        legend_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id=f"{VISUAL_ID}_legend",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        save_legend_png(
            handles=handles,
            labels=labels,
            output_file=legend_output_file,
            ncol=legend_ncol,
            font_family=font_family,
            font_size=legend_fontsize,
            width=legend_width,
            height=legend_height
        )

        # ==================================
        # TITLE IMAGE
        # ==================================

        title_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id=f"{VISUAL_ID}_title",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        save_title_png(
            title="ED Hourly Census with Peak Period and Capacity Benchmarks",
            subtitle=date_range_str,
            output_file=title_output_file,
            width=title_width,
            height=title_height,
            dpi=dpi,
            font_family=font_family,
            title_fontsize=title_fontsize,
            subtitle_fontsize=subtitle_fontsize,
            background_color=title_background_color,
            title_weight=title_weight
        )

        logger.info(
            f"[{VISUAL_ID}] Title image saved to "
            f"{title_output_file}"
        )

        parameter_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id=f"{VISUAL_ID}_parameters",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        save_parameter_table_png(
            params=params,
            output_file=parameter_output_file,
            font_family=font_family
        )

        logger.info(
            f"[{VISUAL_ID}] Parameter table saved to "
            f"{parameter_output_file}"
        )

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