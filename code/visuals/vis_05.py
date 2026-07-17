# =============================================================================
# Domain      : ED (Emergency Department)
# Report Name : Monthly ED Arrivals Trend
#
# Description :
# Generates a monthly trend analysis of Emergency Department arrival
# volume over the selected reporting period. ED arrival timestamps are
# grouped by month and aggregated into encounter counts to display changes
# in visit volume over time.
#
# The visualization presents monthly arrival counts as a time-series line
# chart, enabling users to identify seasonal patterns, growth trends,
# utilization fluctuations, and operational demand across the reporting
# period.
#
# Continuous monthly periods are included in the trend line, with zero
# counts displayed for months containing no arrivals to preserve timeline
# continuity.
#
# This report supports:
#   - ED volume trend analysis
#   - Seasonal utilization monitoring
#   - Capacity and staffing planning
#   - Demand forecasting
#   - Operational performance assessment
#
# Inputs :
#   - ed_start_dtm : ED arrival/start datetime
#   - start_date   : Reporting period start date
#   - end_date     : Reporting period end date
#
# Outputs :
#   - PNG line chart displaying monthly ED arrival counts
#       * X-axis: Month
#       * Y-axis: Number of Arrivals
#   - RDB records containing:
#       * Monthly arrival counts
#       * Year-month reporting dimensions
#       * Trend metrics for downstream reporting
#
# Key Metrics :
#   - Monthly ED arrivals
#   - Arrival volume trends over time
#   - Month-to-month utilization patterns
# =============================================================================

import os
import logging
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
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
VISUAL_ID = "vis_05"


def run(df, params, start_date, end_date, output_dir, generate_output_name):
    """
    Visualization 05: Monthly ED Arrivals Trend
    """

    logging.info(f"Starting {VISUAL_ID}")
    params = normalize_params(params)

    # =========================
    # DEFAULT PARAMETERS
    # =========================
    defaults = {
        # Figure
        "fig_width": 12,
        "fig_height": 6,
        "dpi": 100,

        # Fonts
        "title_fontsize": 14,
        "axis_fontsize": 11,
        "label_fontsize": 9,

        # Line styling
        "line_color": "#1f77b4",
        "marker": "o",
        "marker_size": 4,

        # Labels
        "show_labels": True,
        "label_first_last_only": True,
        "label_decimals": 0,

        # Axis
        "y_axis_separator": True,

        # Axis range
        "y_min": None,
        "y_max": None,

        # Title
        "title": "Monthly ED Arrivals",
    }

    # Merge params
    try:
        cfg = {k: params.get(k, v) for k, v in defaults.items()}
    except Exception:
        cfg = defaults
    font_family = str(
        params.get("font_family", "Segoe UI")
    ).strip()
    # ---- Title Image ----

    title_width = float(
        params.get("title_width", 6.25) or 6.25
    )

    title_height = float(
        params.get("title_height", 0.6) or 0.6
    )

    subtitle_fontsize = int(
        params.get("subtitle_fontsize", 12) or 12
    )

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
    tick_fontsize = int(
        params.get("tick_fontsize", 10) or 10
    )

    x_tick_rotation = float(
        params.get("x_tick_rotation", 45) or 45
    )

    # =========================
    # VALIDATION
    # =========================
    required_cols = ["ed_start_dtm"]
    for col in required_cols:
        if col not in df.columns:
            logging.error(f"{VISUAL_ID}: Missing required column '{col}'")
            return

    # =========================
    # DATA PREPARATION
    # =========================
    try:
        df = df.copy()

        # Convert datetime
        df["ed_start_dtm"] = pd.to_datetime(df["ed_start_dtm"], errors="coerce")

        # Drop invalid
        df = df.dropna(subset=["ed_start_dtm"])

        if df.empty:
            logging.warning(f"{VISUAL_ID}: No valid ed_start_dtm values")
            return

        # Filter by date range
        start_dt = pd.to_datetime(start_date, errors="coerce")
        end_dt = pd.to_datetime(end_date, errors="coerce")

        if pd.notna(start_dt):
            df = df[df["ed_start_dtm"] >= start_dt]
        if pd.notna(end_dt):
            df = df[df["ed_start_dtm"] <= end_dt]

        if df.empty:
            logging.warning(f"{VISUAL_ID}: No data after date filtering")
            return

    except Exception as e:
        logging.error(f"{VISUAL_ID}: Data preparation failed - {str(e)}")
        return

    # =========================
    # FEATURE ENGINEERING
    # =========================
    try:
        df["year_month"] = df["ed_start_dtm"].dt.to_period("M").dt.to_timestamp()

    except Exception as e:
        logging.error(f"{VISUAL_ID}: Feature engineering failed - {str(e)}")
        return

    # =========================
    # AGGREGATION
    # =========================
    try:
        monthly_counts = (
            df.groupby("year_month")
            .size()
            .rename("arrival_count")
            .reset_index()
        )

        write_rdb = int(params.get("write_rdb", 0))
        rdb_rows = []

        if write_rdb == 1:

            for _, row in monthly_counts.iterrows():

                month_dt = pd.to_datetime(row["year_month"])

                rdb_rows.append({
                    "run_id": params.get("run_id"),
                    "visual_id": VISUAL_ID,
                    "client_name": params.get("client_name"),

                    "domain": params.get("domain"),
                    "cohort_id": params.get("cohort_id"),

                    "domain_cohort":
                        f"{params.get('domain')}.{params.get('cohort_id')}",

                    "dimension": "year_month",
                    "dimension_value": month_dt.strftime("%Y-%m"),
                    "dimension_value_label": month_dt.strftime("%b %Y"),

                    "secondary_dimension": None,
                    "secondary_dimension_value": None,

                    "metric": "arrivals",
                    "metric_type": "count",
                    "value": int(row["arrival_count"]),

                    "start_date": start_date,
                    "end_date": end_date,

                    "report_title": "Monthly ED Arrivals"
                })

        if monthly_counts.empty:
            logging.warning(f"{VISUAL_ID}: Aggregation resulted in empty dataset")
            return

        # Create full continuous monthly index
        full_range = pd.date_range(
            start=monthly_counts["year_month"].min(),
            end=monthly_counts["year_month"].max(),
            freq="MS"
        )

        monthly_counts = monthly_counts.set_index("year_month").reindex(full_range, fill_value=0)
        monthly_counts.index.name = "year_month"
        monthly_counts = monthly_counts.reset_index()

    except Exception as e:
        logging.error(f"{VISUAL_ID}: Aggregation failed - {str(e)}")
        return

    # =========================
    # LABEL FORMATTING HELPERS
    # =========================
    def format_number(x):
        try:
            return f"{int(round(x, 0)):,}"
        except Exception:
            return str(x)

    # =========================
    # PLOTTING
    # =========================
    try:
        plt.rcParams["font.family"] = font_family

        fig, ax = plt.subplots(
            figsize=(float(cfg["fig_width"]), float(cfg["fig_height"])),
            dpi=int(cfg["dpi"])
        )

        x = monthly_counts["year_month"]
        y = monthly_counts["arrival_count"]

        ax.plot(
            x,
            y,
            color=cfg["line_color"],
            marker=cfg["marker"],
            markersize=float(cfg["marker_size"])
        )

        legend_handles = [
            Line2D(
                [0],
                [0],
                color=cfg["line_color"],
                marker=cfg["marker"],
                label="Monthly Arrivals"
            )
        ]

        legend_labels = [
            "Monthly Arrivals"
        ]

        # X-axis labels
        if len(x) > 24:
            labels = x.dt.strftime("%Y-%m")
        else:
            labels = x.dt.strftime("%b %Y")

        ax.set_xticks(x)
        ax.set_xticklabels(
            labels,
            rotation=x_tick_rotation,
            ha="right"
        )

        # Titles
        ax.set_xlabel(
            "Month",
            fontsize=int(cfg["axis_fontsize"]),
            fontfamily=font_family
        )
        ax.set_ylabel(
            "Number of Arrivals",
            fontsize=int(cfg["axis_fontsize"]),
            fontfamily=font_family
        )

        ax.tick_params(
            axis="both",
            labelsize=tick_fontsize
        )

        # Y-axis formatting
        if cfg["y_axis_separator"]:
            ax.get_yaxis().set_major_formatter(
                plt.FuncFormatter(lambda val, pos: f"{int(val):,}")
            )

        # Apply axis range (after plotting)
        apply_axis_range(
            ax,
            axis="y",
            min_val=cfg.get("y_min"),
            max_val=cfg.get("y_max")
        )

        # =========================
        # DATA LABELS
        # =========================
        if cfg["show_labels"]:
            try:
                indices = range(len(y))

                if cfg["label_first_last_only"]:
                    indices = [0, len(y) - 1]

                for i in indices:
                    ax.text(
                        x.iloc[i],
                        y.iloc[i],
                        format_number(y.iloc[i]),
                        fontsize=int(cfg["label_fontsize"]),
                        ha="center",
                        va="bottom",
                        fontfamily=font_family
                    )
            except Exception as e:
                logging.warning(f"{VISUAL_ID}: Label rendering failed - {str(e)}")

        plt.tight_layout()
        for tick in ax.get_xticklabels():
            tick.set_fontfamily(font_family)
            tick.set_fontsize(tick_fontsize)

        for tick in ax.get_yticklabels():
            tick.set_fontfamily(font_family)
            tick.set_fontsize(tick_fontsize)
        # =========================
        # SAVE OUTPUT
        # =========================
        filepath = os.path.join(
                    output_dir,
                    generate_output_name(
                        visual_id=VISUAL_ID,
                        start_date=start_date,
                        end_date=end_date,
                        cohort_id=params.get("cohort_id"),
                        ext="png"
                    )
                )

        plt.savefig(filepath)
        legend_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id="vis_05_legend",
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
            f"{VISUAL_ID}: Legend written: "
            f"{legend_output_file}"
        )

        date_range_str = format_date_range(
            start_date,
            end_date
        )

        title_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id="vis_05_title",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        save_title_png(
            title=cfg["title"],
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
            f"{VISUAL_ID}: Title written: "
            f"{title_output_file}"
        )



        plt.close()

        logging.info(f"{VISUAL_ID}: Saved output to {filepath}")

        return {
            "output_path": filepath,
            "rdb": rdb_rows
        }

    except Exception as e:
        logging.error(f"{VISUAL_ID}: Plotting failed - {str(e)}")
        return