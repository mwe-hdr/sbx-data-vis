# =============================================================================
# Report Name : Facility Census with Peak Period and Capacity Benchmarks
#
# Description :
# Calculates Emergency Department census levels from patient arrival and
# departure timestamps and summarizes average census by the desired aggregation level. The
# report applies optional growth assumptions to projected census volumes,
# identifies user-defined peak operating periods, and evaluates capacity
# requirements based on target utilization thresholds.
#
# Census profiles are generated from a minute-level census model
# and aggregated into average occupancy values. The visualization
# highlights peak and off-peak periods and overlays percentile benchmarks
# to demonstrate expected census variation throughout the day.
#
# Key planning metrics include:
#   - Average census
#   - Peak-period census
#   - 70th, 80th, and 90th percentile census levels
#   - Projected room requirements based on target utilization
#   - Growth-adjusted demand forecasts
#
# This report supports:
#   - Facility capacity planning
#   - Space and room requirement analysis
#   - Throughput and occupancy monitoring
#   - Growth forecasting
#   - Peak demand assessment
#   - Strategic operational planning
#
# Inputs :
#   - tmt_start_dtm            : Facility arrival/start datetime
#   - tmt_stop_dtm             : Facility departure/stop datetime
#   - start_date              : Reporting period start date/time
#   - end_date                : Reporting period end date/time
#   - variable_10_year_growth : Projected growth adjustment factor
#   - utilization             : Target operational utilization rate
#   - peak_period_start       : Beginning of peak period
#   - peak_period_length: Duration of peak period
#
# Outputs :
#   - PNG chart displaying:
#       * Average aggregation-level census
#       * Peak and off-peak periods
#       * P70, P80, and P90 census benchmarks
#       * Peak census benchmark
#       * Estimated room need benchmark
#   - RDB records containing:
#       * Average aggregation-level census values
#       * aggregation-level percentile benchmarks
#       * Peak census capacity benchmarks
#       * Estimated room need calculations
#
# Key Metrics :
#   - Average census by aggregation-level
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
    save_title_png,
    generate_census
)
from utils.date_helpers import df_date_splitter

logger = logging.getLogger(__name__)

VISUAL_ID = "vis_10"

def get_bucket_label(level, value):

    if level == "hour":
        return f"{int(value):02d}:00"

    if level == "day_of_week":
        return [
            "Mon","Tue","Wed",
            "Thu","Fri","Sat","Sun"
        ][int(value)]

    if level == "month":
        return [
            None,
            "Jan","Feb","Mar","Apr",
            "May","Jun","Jul","Aug",
            "Sep","Oct","Nov","Dec"
        ][int(value)]

def _safe_param(params, key, default, cast_type=None):
    try:
        val = params.get(key, default)
        return cast_type(val) if cast_type else val
    except Exception:
        logger.warning(f"[{VISUAL_ID}] Invalid param for {key}; using default {default}")
        return default

def get_aggregation_range(level):

    if level == "hour":
        return range(24)

    if level == "day_of_week":
        return range(7)

    if level == "month":
        return range(1, 13)

    raise ValueError(
        f"Unsupported aggregation level: {level}"
    )

def create_aggregation_dimension(ts, aggregation_level):

    if aggregation_level == "hour":
        ts["aggregation_key"] = ts["interval"].dt.hour

    elif aggregation_level == "day_of_week":
        ts["aggregation_key"] = ts["interval"].dt.dayofweek

    elif aggregation_level == "month":
        ts["aggregation_key"] = ts["interval"].dt.month

    return ts

def run(df, params, start_date, end_date, output_dir, generate_output_name):

    cohort_desc = params.get("cohort_desc", "")

    aggregation_level = _safe_param(
        params,
        "aggregation_level",
        "hour",
        str
    ).lower()
    
    logger.info(f"[{VISUAL_ID}] Starting Facility {aggregation_level} Census with Peak Period and Capacity Benchmarks visualization")
    params = normalize_params(params)

    try:
        if df is None or df.empty:
            logger.warning(f"[{VISUAL_ID}] Input dataframe is empty")
            return

        # =========================
        # PARAMETERS
        # =========================
        growth = _safe_param(params, "variable_10_year_growth", 0.0, float)
        peak_start = _safe_param(
            params,
            "peak_period_start",
            0,
            int
        )

        peak_len = _safe_param(
            params,
            "peak_period_length",
            8,
            int
        )
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

        # --------------------------------------------------
        # TEMP DEBUG - CENSUS HELPER PARAMETERS
        # --------------------------------------------------
        logger.info(
            f"[{VISUAL_ID}] census_helper_csv="
            f"{params.get('census_helper_csv')}"
        )

        logger.info(
            f"[{VISUAL_ID}] census_helper_type="
            f"{params.get('census_helper_type')}"
        )

        logger.info(
            f"[{VISUAL_ID}] census_helper_operation="
            f"{params.get('census_helper_operation')}"
        )

        # --------------------------------------------------
        # HELP MY DATAFRAME
        # --------------------------------------------------
        ts, census_df = generate_census(
            df,
            start_date,
            end_date,
            census_helper_csv=params.get(
                "census_helper_csv"
            ),
            census_helper_type=params.get(
                "census_helper_type"
            ),
            census_helper_operation=params.get(
                "census_helper_operation"
            ),
            max_census_delta=25
        )

        if ts.empty:
            logger.warning(f"[{VISUAL_ID}] Census dataset empty after generation")
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
            logger.warning(f"[{VISUAL_ID}] Dataset empty after date filtering")
            return

        # Growth adjustment
        ts["adj_census"] = ts["census"] * (1 + growth)

        # aggregation-level extraction
        ts = create_aggregation_dimension(
            ts,
            aggregation_level
        )

        aggregation_range = get_aggregation_range(
            aggregation_level
        )

        # aggregation
        aggregation_df = (
            ts.groupby("aggregation_key")["adj_census"]
            .mean()
            .reindex(aggregation_range, fill_value=0)
            .reset_index()
        )

        aggregation_df.columns = ["aggregation_key", f"{aggregation_level}_census"]

        aggregation_df["bucket_position"] = range(len(aggregation_df))

        # =========================
        # Peak classification
        # =========================
        bucket_count = len(aggregation_range)

        peak_start = max(
            0,
            min(
                peak_start,
                bucket_count - 1
            )
        )

        peak_len = max(
            1,
            min(
                peak_len,
                bucket_count
            )
        )

        def is_peak(bucket_position):

            end = peak_start + peak_len

            if end <= bucket_count:
                return peak_start <= bucket_position < end

            return (
                bucket_position >= peak_start
                or
                bucket_position < (end - bucket_count)
            )

        aggregation_df["peak_flag"] = (
            aggregation_df["bucket_position"]
            .apply(
                lambda x:
                "Peak" if is_peak(x)
                else "Off-Peak"
            )
        )

        graph_start = _safe_param(
            params,
            "graph_start",
            params.get("graph_start", 0),
            int
        )

        graph_start = min(
            max(graph_start, 0),
            len(aggregation_range) - 1
        )

        # =========================
        # Percentiles
        # =========================
        percentiles = (
            ts.groupby("aggregation_key")["adj_census"]
            .agg(
                p70=lambda x: np.percentile(x, 70),
                p80=lambda x: np.percentile(x, 80),
                p90=lambda x: np.percentile(x, 90),
            )
            .reindex(aggregation_range)
            .reset_index()
        )

        aggregation_df = aggregation_df.merge(percentiles, on="aggregation_key", how="left")

        bucket_values = list(aggregation_range)

        display_buckets = (
            bucket_values[graph_start:]
            +
            bucket_values[:graph_start]
        )

        aggregation_df["display_order"] = pd.Categorical(
            aggregation_df["aggregation_key"],
            categories=display_buckets,
            ordered=True
        )

        aggregation_df = (
            aggregation_df.sort_values("display_order")
            .reset_index(drop=True)
        )

        aggregation_df["plot_position"] = range(len(aggregation_df))

        # =========================
        # Capacity metrics
        # =========================
        peak_values = aggregation_df.loc[aggregation_df["peak_flag"] == "Peak", f"{aggregation_level}_census"]
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

        # =========================================================
        # INSPECTION FILES
        # =========================================================

        census_input_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id=f"{VISUAL_ID}_census_input",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="csv"
            )
        )

        df.to_csv(
            census_input_file,
            index=False
        )

        logger.info(
            f"[{VISUAL_ID}] Census Input File exported: "
            f"{census_input_file} ({len(df):,} rows)"
        )

        census_df_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id=f"{VISUAL_ID}_census_df",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="csv"
            )
        )

        census_df.to_csv(
            census_df_file,
            index=False
        )

        logger.info(
            f"[{VISUAL_ID}] Census DF exported: "
            f"{census_df_file} ({len(census_df):,} rows)"
        )

        ts_df_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id=f"{VISUAL_ID}_ts_df",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="csv"
            )
        )

        ts.to_csv(
            ts_df_file,
            index=False
        )

        logger.info(
            f"[{VISUAL_ID}] TS DF exported: "
            f"{ts_df_file} ({len(ts):,} rows)"
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
        peak_mask = aggregation_df["peak_flag"] == "Peak"

        ax.bar(
            aggregation_df.loc[~peak_mask, "plot_position"],
            aggregation_df.loc[~peak_mask, f"{aggregation_level}_census"],
            color=colors["offpeak"],
            label="Off-Peak",
        )

        ax.bar(
            aggregation_df.loc[peak_mask, "plot_position"],
            aggregation_df.loc[peak_mask, f"{aggregation_level}_census"],
            color=colors["peak"],
            label="Peak",
        )

        # Percentiles
        ax.plot(aggregation_df["plot_position"], aggregation_df["p70"], linestyle="--", color=colors["p70"], label="P70")
        ax.plot(aggregation_df["plot_position"], aggregation_df["p80"], linestyle="--", color=colors["p80"], label="P80")
        ax.plot(aggregation_df["plot_position"], aggregation_df["p90"], linestyle="--", color=colors["p90"], label="P90")

        # Capacity lines
        aggregation_df["peak_line"] = np.nan
        aggregation_df["room_line"] = np.nan

        aggregation_df.loc[
            aggregation_df["peak_flag"] == "Peak",
            "peak_line"
        ] = peak_census

        aggregation_df.loc[
            aggregation_df["peak_flag"] == "Peak",
            "room_line"
        ] = room_need

        ax.plot(
            aggregation_df["plot_position"],
            aggregation_df["peak_line"],
            color=colors["peak_line"],
            linewidth=2,
            label="Peak Census",
        )

        ax.plot(
            aggregation_df["plot_position"],
            aggregation_df["room_line"],
            color=colors["room_need"],
            linestyle="-.",
            linewidth=2,
            label="Room Need",
        )

        # Labels
        date_range_str = format_date_range(start_date, end_date)

        axis_labels = {
            "hour": "Hour of Day",
            "day_of_week": "Day of Week",
            "month": "Month"
        }

        ax.set_title("")
        ax.set_xlabel(
            axis_labels.get(
                aggregation_level,
                "Bucket"
            )
        )
        ax.set_ylabel(
            "Facility Census",
            fontfamily=font_family
        )

        aggregation_df["dimension_label"] = (
            aggregation_df["aggregation_key"]
            .apply(
                lambda x:
                get_bucket_label(
                    aggregation_level,
                    x
                )
            )
        )

        ax.set_xticks(aggregation_df["plot_position"])
        ax.set_xticklabels(
            aggregation_df["dimension_label"]
        )
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

        logger.info(
            f"Peak Census={peak_census}, "
            f"Room Need={room_need}, "
            f"Y Max={ax.get_ylim()[1]}"
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

        aggregation_name = {
            "hour": "Hourly",
            "day_of_week": "Day-of-Week",
            "month": "Monthly"
        }

        report_title = (
            f"{cohort_desc} | "
            f"Facility {aggregation_name[aggregation_level]} "
            f"Census with Peak Period and Projected Room Need"
        )

        save_title_png(
            title=report_title,
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
        # ROOM NEED TABLE
        # =========================

        room_need_png = os.path.join(
            output_dir,
            generate_output_name(
                visual_id=f"{VISUAL_ID}_room_need",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        fig, ax = plt.subplots(
            figsize=(3.6, 1.5),
            dpi=dpi
        )

        ax.axis("off")

        tbl = ax.table(
            cellText=[[f"{room_need:,.1f}"]],
            colLabels=["Projected Facility Room Need"],
            cellLoc="center",
            colLoc="center",
            loc="center",
            bbox=[0.08, 0.20, 0.84, 0.60]
        )

        tbl.auto_set_font_size(False)
        tbl.scale(1.0, 1.35)

        # HEADER CELL
        header = tbl[(0, 0)]
        header.set_facecolor("#d9d9d9")
        header.set_edgecolor("black")
        header.set_linewidth(1.0)
        header.set_text_props(
            fontsize=9,
            fontweight="bold",
            fontfamily=font_family
        )

        # VALUE CELL
        value = tbl[(1, 0)]
        value.set_facecolor("white")
        value.set_edgecolor("black")
        value.set_linewidth(1.0)
        value.set_text_props(
            fontsize=10,
            fontfamily=font_family
        )

        plt.savefig(
            room_need_png,
            bbox_inches="tight",
            pad_inches=0.025,
            dpi=dpi
        )

        plt.close()

        logger.info(
            f"[{VISUAL_ID}] Room Need table saved to "
            f"{room_need_png}"
        )

        # =========================
        # RDB OUTPUT
        # =========================
        write_rdb = int(params.get("write_rdb", 0))
        rdb_rows = []

        if write_rdb == 1:

            # ----------------------------------
            # Census values
            # ----------------------------------
            for _, row in aggregation_df.iterrows():

                rdb_rows.append({
                    "run_id": params.get("run_id"),
                    "visual_id": VISUAL_ID,
                    "client_name": params.get("client_name"),

                    "domain": params.get("domain"),
                    "cohort_id": params.get("cohort_id"),

                    "domain_cohort":
                        f"{params.get('domain')}.{params.get('cohort_id')}",

                    "dimension": aggregation_level,
                    "dimension_value": int(row["aggregation_key"]),
                    "dimension_value_label": row["dimension_label"],

                    "secondary_dimension": "period_type",
                    "secondary_dimension_value": row["peak_flag"],

                    "metric": "average_census",
                    "metric_type": "average",
                    "value": float(row[f"{aggregation_level}_census"]),

                    "start_date": start_date,
                    "end_date": end_date,

                    "report_title": report_title
                })

            # ----------------------------------
            # Percentiles
            # ----------------------------------
            for _, row in aggregation_df.iterrows():

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

                        "dimension": aggregation_level,
                        "dimension_value": int(row["aggregation_key"]),
                        "dimension_value_label": row["dimension_label"],

                        "secondary_dimension": "percentile",
                        "secondary_dimension_value": metric_name.upper(),

                        "metric": "average_census",
                        "metric_type": metric_name,
                        "value": float(metric_value),

                        "start_date": start_date,
                        "end_date": end_date,

                        "report_title": report_title
                    })

            # ----------------------------------
            # Peak Census Benchmark
            # ----------------------------------
            for _, row in aggregation_df.iterrows():

                if row["peak_flag"] != "Peak":
                    continue

                rdb_rows.append({
                    "run_id": params.get("run_id"),
                    "visual_id": VISUAL_ID,
                    "client_name": params.get("client_name"),

                    "domain": params.get("domain"),
                    "cohort_id": params.get("cohort_id"),

                    "domain_cohort":
                        f"{params.get('domain')}.{params.get('cohort_id')}",

                    "dimension": aggregation_level,
                    "dimension_value": int(row["aggregation_key"]),
                    "dimension_value_label": row["dimension_label"],

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
            # Room Need Benchmark
            # ----------------------------------
            for _, row in aggregation_df.iterrows():

                rdb_rows.append({
                    "run_id": params.get("run_id"),
                    "visual_id": VISUAL_ID,
                    "client_name": params.get("client_name"),

                    "domain": params.get("domain"),
                    "cohort_id": params.get("cohort_id"),

                    "domain_cohort":
                        f"{params.get('domain')}.{params.get('cohort_id')}",

                    "dimension": aggregation_level,
                    "dimension_value": int(row["aggregation_key"]),
                    "dimension_value_label": row["dimension_label"],

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