# =============================================================================
# Domain      : ED (Emergency Department)
# Report Name : Weekday Arrival Distribution
#
# Description :
# Generates a distribution analysis of Emergency Department arrivals by
# day of week. ED arrival timestamps are assigned to weekday categories
# and aggregated to determine the proportion of total arrivals occurring
# on each day.
#
# The visualization displays the percentage of arrivals occurring on
# Sunday through Saturday, providing insight into weekly utilization
# patterns, peak demand periods, and potential staffing requirements.
#
# This report supports:
#   - Arrival pattern analysis
#   - Weekly demand forecasting
#   - Staffing and scheduling optimization
#   - Capacity planning
#   - Operational workload assessment
#
# Inputs :
#   - ed_start_dtm : ED arrival/start datetime
#   - start_date   : Reporting period start date
#   - end_date     : Reporting period end date
#
# Outputs :
#   - PNG bar chart showing percent distribution of arrivals by weekday
#       * X-axis: Day of Week
#       * Y-axis: Percent of Arrivals
#   - RDB records containing:
#       * Total arrivals (denominator)
#       * Arrival counts by weekday
#       * Weekday distribution metrics for downstream reporting
#
# Key Metrics :
#   - Total ED arrivals
#   - Arrivals by weekday
#   - Percent of arrivals by weekday
#   - Weekly arrival distribution pattern
# =============================================================================

import os
import logging
import pandas as pd
import numpy as np
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

VISUAL_ID = "vis_06"

def run(df, params, start_date, end_date, output_dir, generate_output_name):
    """
    Visualization 06: Weekday Arrival Distribution
    """

    logging.info(f"Starting {VISUAL_ID}")
    params = normalize_params(params)

    try:
        # =============================
        # DEFAULT PARAMETERS
        # =============================
        defaults = {
            # Figure
            "fig_width": 12,
            "fig_height": 6,
            "dpi": 100,

            # Fonts
            "title_fontsize": 14,
            "axis_fontsize": 11,
            "label_fontsize": 9,

            # Labels
            "label_decimals": 1,
            "label_threshold": 0.0,
            "label_color": "black",

            # Axis
            "y_axis_mode": "percent",
            "y_axis_decimals": 1,
            "y_axis_multiplier": 100,
            "y_axis_suffix": "%",

            # Color
            "bar_color": "#1f77b4",
        }

        cfg = {**defaults, **(params or {})}
        font_family = str(
            cfg.get("font_family", "Segoe UI")
        ).strip()
        # ---- Title Image ----

        title_width = float(
            cfg.get("title_width", 6.25) or 6.25
        )

        title_height = float(
            cfg.get("title_height", 0.6) or 0.6
        )

        subtitle_fontsize = int(
            cfg.get("subtitle_fontsize", 12) or 12
        )

        title_background_color = str(
            cfg.get(
                "title_background_color",
                "#d9d9d9"
            )
        )

        title_weight = str(
            cfg.get(
                "title_weight",
                "bold"
            )
        )
        legend_width = float(
            cfg.get("legend_width", 4) or 4
        )

        legend_height = float(
            cfg.get("legend_height", 1) or 1
        )
        tick_fontsize = int(
            cfg.get("tick_fontsize", 10) or 10
        )

        x_tick_rotation = float(
            cfg.get("x_tick_rotation", 0) or 0
        )

        # =============================
        # VALIDATION
        # =============================
        required_cols = ["ed_start_dtm"]
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            logging.error(f"{VISUAL_ID} missing required columns: {missing_cols}")
            return

        df = df.copy()

        # =============================
        # DATETIME HANDLING
        # =============================
        df["ed_start_dtm"] = pd.to_datetime(df["ed_start_dtm"], errors="coerce")

        df = df.dropna(subset=["ed_start_dtm"])

        if df.empty:
            logging.warning(f"{VISUAL_ID}: No valid ed_start_dtm after conversion")
            return

        # =============================
        # DATE FILTER
        # =============================
        try:
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)

            df = df[
                (df["ed_start_dtm"] >= start_dt) &
                (df["ed_start_dtm"] <= end_dt)
            ]

        except Exception as e:
            logging.warning(
                f"{VISUAL_ID}: Date filtering failed: {str(e)}"
            )

        if df.empty:
            logging.warning(f"{VISUAL_ID}: No data after date filtering")
            return

        # =============================
        # DERIVE WEEKDAY
        # =============================
        df["weekday_num"] = df["ed_start_dtm"].dt.dayofweek

        weekday_map = {
            0: "Mon",
            1: "Tue",
            2: "Wed",
            3: "Thu",
            4: "Fri",
            5: "Sat",
            6: "Sun",
        }

        df["weekday"] = df["weekday_num"].map(weekday_map)

        ordered_days = [
            "Sun",
            "Mon",
            "Tue",
            "Wed",
            "Thu",
            "Fri",
            "Sat"
        ]

        # =============================
        # AGGREGATION
        # =============================
        counts = (
            df["weekday"]
            .value_counts()
            .reindex(ordered_days, fill_value=0)
        )

        total = counts.sum()

        if total == 0:
            logging.warning(f"{VISUAL_ID}: Total encounters = 0")
            return

        percents = counts / total

        write_rdb = int(params.get("write_rdb", 0))
        rdb_rows = []

        # =============================
        # PLOT
        # =============================
        plt.rcParams["font.family"] = font_family

        fig, ax = plt.subplots(
            figsize=(float(cfg["fig_width"]), float(cfg["fig_height"])),
            dpi=int(cfg["dpi"])
        )

        bars = ax.bar(
            ordered_days,
            percents.values,
            color=cfg["bar_color"]
        )

        legend_handles = [
            Patch(
                facecolor=cfg["bar_color"],
                label="Percent of Arrivals"
            )
        ]

        legend_labels = [
            "Percent of Arrivals"
        ]

        # =============================
        # LABELS
        # =============================
        for bar, val in zip(bars, percents.values):

            if val < float(cfg["label_threshold"]):
                continue

            label = (
                f"{val * 100:.{int(cfg['label_decimals'])}f}%"
            )

            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                label,
                ha="center",
                va="bottom",
                fontsize=int(cfg["label_fontsize"]),
                color=cfg["label_color"],
                fontfamily=font_family
            )

        # =============================
        # TITLES / AXES
        # =============================

        report_title = "Weekday Arrival Distribution"


        ax.set_xlabel(
            "Day of Week",
            fontsize=int(cfg["axis_fontsize"]),
            fontfamily=font_family
        )

        ax.set_ylabel(
            "Percent of Arrivals",
            fontsize=int(cfg["axis_fontsize"]),
            fontfamily=font_family
        )

        # =============================
        # AXIS FORMATTING
        # =============================
        apply_yaxis_format(
            ax,
            mode=cfg["y_axis_mode"],
            decimals=cfg["y_axis_decimals"],
            multiplier=cfg["y_axis_multiplier"],
            suffix=cfg["y_axis_suffix"]
        )

        ax.tick_params(
            axis="both",
            labelsize=tick_fontsize
        )

        ax.tick_params(
            axis="x",
            labelrotation=x_tick_rotation
        )

        # =============================
        # OUTPUT
        # =============================
        output_path = os.path.join(
            output_dir,
            generate_output_name(
                visual_id=VISUAL_ID,
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        plt.tight_layout()
        for tick in ax.get_xticklabels():
            tick.set_fontfamily(font_family)

        for tick in ax.get_yticklabels():
            tick.set_fontfamily(font_family)
        plt.savefig(output_path)
        legend_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id="vis_06_legend",
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
            font_size=int(cfg["axis_fontsize"]),
            width=legend_width,
            height=legend_height
        )

        logging.info(
            f"{VISUAL_ID} legend written: "
            f"{legend_output_file}"
        )
        date_range_str = format_date_range(
            start_date,
            end_date
        )

        title_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id="vis_06_title",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        save_title_png(
            title="Weekday Arrival Distribution",
            subtitle=date_range_str,
            output_file=title_output_file,
            width=title_width,
            height=title_height,
            dpi=int(cfg["dpi"]),
            font_family=font_family,
            title_fontsize=int(cfg["title_fontsize"]),
            subtitle_fontsize=subtitle_fontsize,
            background_color=title_background_color,
            title_weight=title_weight
        )

        logging.info(
            f"{VISUAL_ID} title written: "
            f"{title_output_file}"
        )


        plt.close()

        logging.info(f"{VISUAL_ID} saved to {output_path}")

        # =============================
        # RDB OUTPUT
        # =============================

        # Denominator rows
        if write_rdb == 1:

            for day in ordered_days:

                rdb_rows.append({
                    "run_id": params.get("run_id"),
                    "visual_id": VISUAL_ID,
                    "client_name": params.get("client_name"),

                    "domain": params.get("domain"),
                    "cohort_id": params.get("cohort_id"),

                    "domain_cohort":
                        f"{params.get('domain')}.{params.get('cohort_id')}",

                    "dimension": "weekday",
                    "dimension_value": day,
                    "dimension_value_label": day,

                    "secondary_dimension": None,
                    "secondary_dimension_value": None,

                    "metric": "arrivals",
                    "metric_type": "denominator",
                    "value": int(total),

                    "start_date": start_date,
                    "end_date": end_date,

                    "report_title": report_title
                })

            # Numerator rows
            for day in ordered_days:

                rdb_rows.append({
                    "run_id": params.get("run_id"),
                    "visual_id": VISUAL_ID,
                    "client_name": params.get("client_name"),

                    "domain": params.get("domain"),
                    "cohort_id": params.get("cohort_id"),

                    "domain_cohort":
                        f"{params.get('domain')}.{params.get('cohort_id')}",

                    "dimension": "weekday",
                    "dimension_value": day,
                    "dimension_value_label": day,

                    "secondary_dimension": None,
                    "secondary_dimension_value": None,

                    "metric": "arrivals",
                    "metric_type": "count",
                    "value": int(counts.loc[day]),

                    "start_date": start_date,
                    "end_date": end_date,

                    "report_title": report_title
                })

        return {
            "output_path": output_path,
            "rdb": rdb_rows
        }

    except Exception as e:
        logging.error(
            f"{VISUAL_ID} failed: {str(e)}",
            exc_info=True
        )