# =============================================================================
# Report Name : Facility Length of Stay Distribution (Hours)
#
# Description :
# Generates a histogram-style visualization showing the distribution of
# Facility length of stay (LOS) measured in hourly intervals.
# Length of stay is calculated as the elapsed time between Facility arrival and
# Facility departure timestamps and grouped into whole-hour buckets.
#
# The report displays the percentage of encounters falling within each
# LOS bucket, allowing users to evaluate patient throughput patterns,
# identify prolonged stays, and assess overall department efficiency.
# Optional reporting database (RDB) output provides both encounter counts
# and percentage denominators for each LOS interval.
#
# This report supports:
#   - Facility throughput monitoring
#   - Length-of-stay benchmarking
#   - Operational performance assessment
#   - Capacity and staffing planning
#   - Patient flow analysis
#
# Inputs :
#   - arrival_dtm : Facility arrival/start datetime
#   - tmt_stop_dtm  : Facility departure/stop datetime
#   - start_date   : Reporting period start date
#   - end_date     : Reporting period end date
#
# Outputs :
#   - PNG histogram of Facility Length of Stay distribution by hour
#   - RDB records containing:
#       * Total encounter count (denominator)
#       * Encounter count by LOS hour bucket (numerator)
#       * LOS bucket labels and reporting dimensions
# =============================================================================

import os
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
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
from utils.date_helpers import prepare_dates
from utils.col_helpers import add_common_helper_columns

logger = logging.getLogger(__name__)

VISUAL_ID = "vis_02"

def run(df, params, start_date, end_date, output_dir, generate_output_name):

    logger.info(f"[{VISUAL_ID}] Starting Length of Stay Distribution")
    params = normalize_params(params)

    try:
        # --------------------------------------------------
        # DEFAULT PARAMETERS
        # --------------------------------------------------
        defaults = {
            "fig_width": 12,
            "fig_height": 6,
            "dpi": 100,
            "title_fontsize": 14,
            "axis_fontsize": 11,
            "label_fontsize": 9,
            "label_decimals": 1,
            "label_threshold": 0.0,  # show all by default
            "max_bucket": None  # optional cap (e.g., 24)
        }
        font_family = str(
            params.get("font_family", "Segoe UI")
        ).strip()
        # ---- Title Image ----

        title_height = float(
            params.get("title_height", 0.6) or 0.6
        )

        title_width = float(
            params.get("title_width", 6.25) or 6.25
        )

        subtitle_fontsize = int(
            params.get("subtitle_fontsize", 12) or 12
        )

        label_color = str(params.get("label_color", "white"))

        title_background_color = str(
            params.get(
                "title_background_color",
                "#d9d9d9"
            )
        )

        title_weight = str(
            params.get(
                "title_weight",
                "bold"
            )
        )
        legend_width = float(
            params.get("legend_width", 4) or 4
        )

        legend_height = float(
            params.get("legend_height", 1) or 1
        )
        y_axis_mode = params.get("y_axis_mode", "percent")
        y_axis_decimals = params.get("y_axis_decimals", 1)
        y_axis_multiplier = params.get("y_axis_multiplier", 100)
        y_axis_suffix = params.get("y_axis_suffix", "%")

        tick_fs = int(
            params.get("tick_fontsize", 10) or 10
        )

        # Merge params (override defaults)
        p = {**defaults, **(params or {})}

        # Cast numeric params safely
        for key in ["fig_width", "fig_height", "dpi",
                    "title_fontsize", "axis_fontsize",
                    "label_fontsize", "label_decimals",
                    "label_threshold"]:
            try:
                p[key] = float(p[key])
            except Exception:
                logger.warning(f"[{VISUAL_ID}] Invalid param for {key}, using default")
                p[key] = defaults[key]

        if p["max_bucket"] not in (None, ""):
            try:
                p["max_bucket"] = int(p["max_bucket"])
            except Exception:
                logger.warning(f"[{VISUAL_ID}] Invalid max_bucket, ignoring")
                p["max_bucket"] = None

        # --------------------------------------------------
        # HELP MY DATAFRAME
        # --------------------------------------------------
        _, df = prepare_dates(df, start_date, end_date)
        df = add_common_helper_columns(df)

        # --------------------------------------------------
        # REQUIRED COLUMNS CHECK
        # --------------------------------------------------
        required_cols = ["arrival_dtm", "tmt_stop_dtm", "valid_los"]
        for col in required_cols:
            if col not in df.columns:
                logger.error(f"[{VISUAL_ID}] Missing required column: {col}")
                return

        logger.info(
            f"[{VISUAL_ID}] Filtering records with null arrival_dtm or tmt_stop_dtm. "
            f"Rows before filter: {len(df):,}"
        )

        # Drop null timestamps
        df = df.dropna(subset=["arrival_dtm", "tmt_stop_dtm"])

        logger.info(
            f"[{VISUAL_ID}] Completed timestamp filter. "
            f"Rows after filter: {len(df):,}"
        )

        logger.info(
            f"[{VISUAL_ID}] Filtering to valid_los == 1. "
            f"Rows before filter: {len(df):,}"
        )

        # Remove invalid LOS
        df = df[(df["valid_los"] == 1)]

        logger.info(
            f"[{VISUAL_ID}] Completed valid_los filter. "
            f"Rows after filter: {len(df):,}"
        )

        if df.empty:
            logger.warning(f"[{VISUAL_ID}] No valid LOS values")
            return

        # --------------------------------------------------
        # LOS SUMMARY STATISTICS
        # --------------------------------------------------
        mean_los = float(df["los_hours"].mean())
        median_los = float(df["los_hours"].median())
        min_los = float(df["los_hours"].min())
        max_los = float(df["los_hours"].max())

        mode_series = df["los_hours"].mode()
        mode_los = (
            float(mode_series.iloc[0])
            if not mode_series.empty
            else None
        )

        # --------------------------------------------------
        # BUCKETING
        # --------------------------------------------------
        df["los_bucket"] = np.floor(df["los_hours"]).astype(int)

        # Optional max bucket cap
        if p["max_bucket"] is not None:
            df["los_bucket"] = np.where(
                df["los_bucket"] >= p["max_bucket"],
                p["max_bucket"],
                df["los_bucket"]
            )

        # --------------------------------------------------
        # AGGREGATION
        # --------------------------------------------------
        grouped = df.groupby("los_bucket").size().reset_index(name="count")

        total = grouped["count"].sum()
        grouped["percent"] = grouped["count"] / total

        # Ensure continuity of buckets
        min_bucket = int(grouped["los_bucket"].min())
        max_bucket = int(grouped["los_bucket"].max())

        all_buckets = pd.DataFrame({
            "los_bucket": range(min_bucket, max_bucket + 1)
        })

        grouped = all_buckets.merge(grouped, on="los_bucket", how="left").fillna(0)

        # --------------------------------------------------
        # RDB METRICS
        # --------------------------------------------------
        write_rdb = int(params.get("write_rdb", 0))
        rdb_rows = []

        total_encounters = int(total)

        if write_rdb == 1:

            summary_metrics = [
                ("los_mean_hours", mean_los),
                ("los_median_hours", median_los),
                ("los_min_hours", min_los),
                ("los_max_hours", max_los),
                ("los_mode_hours", mode_los),
            ]

            for metric_name, metric_value in summary_metrics:
                rdb_rows.append({
                    "run_id": params.get("run_id"),
                    "visual_id": "vis_02",
                    "client_name": params.get("client_name"),
                    "domain": params.get("domain"),
                    "cohort_id": params.get("cohort_id"),
                    "domain_cohort":
                        f"{params.get('domain')}.{params.get('cohort_id')}",

                    "dimension": "summary",
                    "dimension_value": None,
                    "dimension_value_label": metric_name,

                    "secondary_dimension": None,
                    "secondary_dimension_value": None,

                    "metric": metric_name,
                    "metric_type": "summary",
                    "value": metric_value,

                    "start_date": start_date,
                    "end_date": end_date,

                    "report_title":
                        "Length of Stay Distribution (Hours)"
                })

            for _, row in grouped.iterrows():

                bucket = int(row["los_bucket"])

                # Denominator
                rdb_rows.append({
                    "run_id": params.get("run_id"),
                    "visual_id": "vis_02",
                    "client_name": params.get("client_name"),

                    "domain": params.get("domain"),
                    "cohort_id": params.get("cohort_id"),

                    "domain_cohort":
                        f"{params.get('domain')}.{params.get('cohort_id')}",

                    "dimension": "los_bucket",
                    "dimension_value": bucket,
                    "dimension_value_label": f"{bucket} Hours",

                    "secondary_dimension": None,
                    "secondary_dimension_value": None,

                    "metric": "encounters",
                    "metric_type": "denominator",
                    "value": total_encounters,

                    "start_date": start_date,
                    "end_date": end_date,

                    "report_title":
                        "Length of Stay Distribution (Hours)"
                })

                # Numerator
                rdb_rows.append({
                    "run_id": params.get("run_id"),
                    "visual_id": "vis_02",
                    "client_name": params.get("client_name"),

                    "domain": params.get("domain"),
                    "cohort_id": params.get("cohort_id"),

                    "domain_cohort":
                        f"{params.get('domain')}.{params.get('cohort_id')}",

                    "dimension": "los_bucket",
                    "dimension_value": bucket,
                    "dimension_value_label": f"{bucket} Hours",

                    "secondary_dimension": None,
                    "secondary_dimension_value": None,

                    "metric": "encounters",
                    "metric_type": "numerator",
                    "value": int(row["count"]),

                    "start_date": start_date,
                    "end_date": end_date,

                    "report_title":
                        "Length of Stay Distribution (Hours)"
                })

        # --------------------------------------------------
        # PLOTTING
        # --------------------------------------------------
        plt.rcParams["font.family"] = font_family

        fig, ax = plt.subplots(
            figsize=(p["fig_width"], p["fig_height"])
        )

        ax.bar(
            grouped["los_bucket"],
            grouped["percent"],
            width=0.8
        )

        legend_handles = [
            Patch(
                facecolor="#1f77b4",
                label="Percent of Encounters"
            )
        ]

        legend_labels = [
            "Percent of Encounters"
        ]

        # Labels above bars
        for _, row in grouped.iterrows():
            if row["percent"] >= p["label_threshold"]:
                    ax.text(
                        row["los_bucket"],
                        row["percent"] / 2,
                        f"{row['percent'] * 100:.{int(p['label_decimals'])}f}%",
                        ha="center",
                        color=label_color,
                        fontsize=p["label_fontsize"],
                        fontfamily=font_family,
                        fontweight="normal",
                        rotation=0
                    )
        

        ax.set_xlabel(
            "Length of Stay (Hours)",
            fontsize=p["axis_fontsize"],
            fontfamily=font_family
        )
        ax.set_ylabel(
            "Percent of Encounters",
            fontsize=p["axis_fontsize"],
            fontfamily=font_family
        )

        # Improve layout
        ax.set_xticks(grouped["los_bucket"])
        plt.xticks(rotation=0)
        
        apply_yaxis_format(
            ax,
            mode=y_axis_mode,
            decimals=y_axis_decimals,
            multiplier=y_axis_multiplier,
            suffix=y_axis_suffix
        )

        for tick in ax.get_xticklabels():
            tick.set_fontfamily(font_family)
            tick.set_fontsize(tick_fs)

        for tick in ax.get_yticklabels():
            tick.set_fontfamily(font_family)
            tick.set_fontsize(tick_fs)

        plt.tight_layout()

        # --------------------------------------------------
        # SAVE OUTPUT
        # --------------------------------------------------
        output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id="vis_02",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        output_path = os.path.join(output_dir, output_file)

        plt.savefig(output_path, dpi=int(p["dpi"]))
        plt.close()

        logger.info(f"[{VISUAL_ID}] saved to {output_path}")

        legend_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id="vis_02_legend",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        save_legend_png(
            handles=legend_handles,
            labels=legend_labels,
            output_file=legend_output_file,
            ncol=1,
            font_family=font_family,
            font_size=p["axis_fontsize"],
            width=legend_width,
            height=legend_height
        )

        logger.info(
            f"[{VISUAL_ID}] legend written: "
            f"{legend_output_file}"
        )

        date_range = format_date_range(
            start_date,
            end_date
        )

        title_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id="vis_02_title",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        save_title_png(
            title="Length of Stay Distribution (Hours)",
            subtitle=date_range,
            output_file=title_output_file,
            width=title_width,
            height=title_height,
            dpi=int(p["dpi"]),
            font_family=font_family,
            title_fontsize=int(p["title_fontsize"]),
            subtitle_fontsize=subtitle_fontsize,
            background_color=title_background_color,
            title_weight=title_weight
        )

        logger.info(
            f"[{VISUAL_ID}] title written: "
            f"{title_output_file}"
        )

        return {
            "output_path": output_path,
            "rdb": rdb_rows
        }

    except Exception as e:
        logger.error(f"[{VISUAL_ID}] failed: {str(e)}")