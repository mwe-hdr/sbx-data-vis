# =============================================================================
# Report Name : Facility ESI Level Distribution
#
# Description :
# Generates a distribution analysis of Facility encounters by
# Emergency Severity Index (ESI) acuity level. Encounters are categorized
# into standard ESI classifications and summarized as a percentage of total
# Facility volume for the selected reporting period.
#
# The visualization displays the relative acuity mix of Facility patients across
# the following categories:
#   - 1 - Immediate
#   - 2 - Emergent
#   - 3 - Urgent
#   - 4 - Less Urgent
#   - 5 - Non-Urgent
#   - 0 - Unknown
#
# This report supports patient acuity analysis, operational planning,
# resource allocation, staffing evaluation, and monitoring of changes in
# Facility case mix over time.
#
# Inputs :
#   - arrival_dtm    : Facility arrival/start datetime
#   - esi          : Emergency Severity Index score
#   - start_date   : Reporting period start date
#   - end_date     : Reporting period end date
#
# Outputs :
#   - PNG bar chart showing percent distribution of encounters by ESI level
#   - RDB records containing:
#       * Total encounter count (denominator)
#       * Encounter count by ESI category
#       * ESI distribution metrics for downstream reporting
#
# Key Metrics :
#   - Total Facility encounters
#   - Encounter count by ESI level
#   - Percent of encounters by ESI level
#   - Overall Facility acuity mix
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
from utils.date_helpers import df_date_splitter

logger = logging.getLogger(__name__)

VISUAL_ID = "vis_04"


def run(df, params, start_date, end_date, output_dir, generate_output_name):
    """
    Visualization 04: ESI Level Distribution
    """

    logger.info(f"[{VISUAL_ID}] Starting ESI Level Distribution visualization")
    params = normalize_params(params)

    # ======================================================
    # DEFAULT PARAMETERS
    # ======================================================
    defaults = {
        # figure
        "fig_width": 12,
        "fig_height": 6,
        "dpi": 100,

        # fonts
        "title_fontsize": 14,
        "axis_fontsize": 11,
        "label_fontsize": 9,

        # labels
        "label_decimals": 1,
        "label_threshold": 0.0,
        "label_color": "black",

        # axis
        "y_axis_mode": "percent",
        "y_axis_decimals": 1,
        "y_axis_multiplier": 100,
        "y_axis_suffix": "%",

        # colors
        "0 - Unknown": "#7f7f7f",
        "1 - Immediate": "#ff7f0e",
        "2 - Emergent": "#17becf",
        "3 - Urgent": "#1f77b4",
        "4 - Less Urgent": "#2ca02c",
        "5 - Non-Urgent": "#ffd966",
    }

    # merge params
    cfg = defaults.copy()
    if params:
        cfg.update({k: v for k, v in params.items() if v is not None})
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

    # ---- Legend ----

    legend_width = float(
        cfg.get("legend_width", 4) or 4
    )

    legend_height = float(
        cfg.get("legend_height", 1) or 1
    )

    # ---- Tick Labels ----

    tick_fontsize = int(
        cfg.get("tick_fontsize", 10) or 10
    )

    x_tick_rotation = float(
        cfg.get("x_tick_rotation", 30) or 30
    )

    params = params or {}

    # --------------------------------------------------
    # HELP MY DATAFRAME
    # --------------------------------------------------
    _, df = df_date_splitter(df, start_date, end_date)

    logger.info(
        f"[{VISUAL_ID}] Dataset received after helper preparation. "
        f"Rows available for ESI distribution: {len(df):,}"
    )

    # ======================================================
    # VALIDATION
    # ======================================================
    required_columns = ["arrival_dtm", "esi_category"]
    for col in required_columns:
        if col not in df.columns:
            logger.error(f"[{VISUAL_ID}] Missing required column: {col}")
            return

    df = df.copy()

    # ======================================================
    # AGGREGATION
    # ======================================================
    category_order = [
        "1 - Immediate",
        "2 - Emergent",
        "3 - Urgent",
        "4 - Less Urgent",
        "5 - Non-Urgent",
    ]

    logger.info(
        f"[{VISUAL_ID}] Calculating ESI distribution from "
        f"{len(df):,} encounters."
    )

    counts = df["esi_category"].value_counts().reindex(category_order, fill_value=0)

    total = counts.sum()
    if total == 0:
        logger.warning(f"[{VISUAL_ID}] Total encounter count is zero")
        return

    percents = counts / total

    # ======================================================
    # PLOTTING
    # ======================================================
    plt.rcParams["font.family"] = font_family

    fig, ax = plt.subplots(
        figsize=(float(cfg["fig_width"]), float(cfg["fig_height"])),
        dpi=int(cfg["dpi"])
    )

    colors = [cfg.get(cat, "#333333") for cat in category_order]

    bars = ax.bar(category_order, percents.values, color=colors)

    legend_handles = [
        Patch(
            facecolor="#1f77b4",
            label="Percent of Encounters"
        )
    ]

    legend_labels = [
        "Percent of Encounters"
    ]

    # ======================================================
    # LABELS
    # ======================================================
    for bar, val in zip(bars, percents.values):
        if val < float(cfg["label_threshold"]):
            continue

        mult = float(cfg.get("y_axis_multiplier", 100))
        dec = int(cfg["label_decimals"])
        suffix = cfg.get("y_axis_suffix", "%")

        label = f"{val * mult:.{dec}f}{suffix}"
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            label,
            ha='center',
            va='bottom',
            fontsize=float(cfg["label_fontsize"]),
            color=cfg["label_color"],
            fontfamily=font_family
        )

    # ======================================================
    # TITLES AND AXES
    # ======================================================

    ax.set_xlabel(
        "ESI Level",
        fontsize=float(cfg["axis_fontsize"]),
        fontfamily=font_family
    )
    ax.set_ylabel(
        "Percent of Encounters",
        fontsize=float(cfg["axis_fontsize"]),
        fontfamily=font_family
    )

    ax.tick_params(
        axis="both",
        labelsize=tick_fontsize
    )

    ax.tick_params(
        axis="x",
        labelrotation=x_tick_rotation
    )

    # apply y-axis formatting helper
    apply_yaxis_format(
    ax,
    mode=cfg.get("y_axis_mode", "percent"),
    decimals=cfg.get("y_axis_decimals", 1),
    multiplier=cfg.get("y_axis_multiplier", 100),
    suffix=cfg.get("y_axis_suffix", "%")
    )

    ax.set_ylim(0, max(percents.values) * 1.15)

    plt.tight_layout()
    for tick in ax.get_xticklabels():
        tick.set_fontfamily(font_family)
        tick.set_fontsize(tick_fontsize)

    for tick in ax.get_yticklabels():
        tick.set_fontfamily(font_family)
        tick.set_fontsize(tick_fontsize)
    # ======================================================
    # OUTPUT
    # ======================================================
    try:
        output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id="vis_04",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        plt.savefig(output_file)
        legend_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id="vis_04_legend",
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
            font_size=float(cfg["axis_fontsize"]),
            width=legend_width,
            height=legend_height
        )

        logger.info(
            f"[{VISUAL_ID}] Legend written: "
            f"{legend_output_file}"
        )

        date_range_str = format_date_range(
            start_date,
            end_date
        )

        title_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id="vis_04_title",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        save_title_png(
            title="ESI Level Distribution",
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

        logger.info(
            f"[{VISUAL_ID}] Title written: "
            f"{title_output_file}"
        )


        plt.close()

        logger.info(f"[{VISUAL_ID}] Saved output to {output_file}")

    except Exception as e:
        logger.error(f"[{VISUAL_ID}] Failed to save output: {str(e)}")
        return

    # ======================================================
    # RDB METRICS
    # ======================================================
    write_rdb = int(params.get("write_rdb", 0))
    rdb_rows = []

    if write_rdb == 1:

        # denominator
        rdb_rows.append({
            "run_id": params.get("run_id"),
            "visual_id": "vis_04",
            "client_name": params.get("client_name"),

            "domain": params.get("domain"),
            "cohort_id": params.get("cohort_id"),

            "domain_cohort":
                f"{params.get('domain')}.{params.get('cohort_id')}",

            "dimension": "esi_distribution",
            "dimension_value": "all",
            "dimension_value_label": "All Encounters",

            "secondary_dimension": None,
            "secondary_dimension_value": None,

            "metric": "encounters",
            "metric_type": "count",
            "value": int(total),

            "start_date": start_date,
            "end_date": end_date,

            "report_title":
                "ESI Level Distribution"
        })

        # numerators
        for category, count in counts.items():

            rdb_rows.append({
                "run_id": params.get("run_id"),
                "visual_id": "vis_04",
                "client_name": params.get("client_name"),

                "domain": params.get("domain"),
                "cohort_id": params.get("cohort_id"),

                "domain_cohort":
                    f"{params.get('domain')}.{params.get('cohort_id')}",

                "dimension": "esi_distribution",
                "dimension_value": category,
                "dimension_value_label": category,

                "secondary_dimension": None,
                "secondary_dimension_value": None,

                "metric": "encounters",
                "metric_type": "count",
                "value": int(count),

                "start_date": start_date,
                "end_date": end_date,

                "report_title":
                    "ESI Level Distribution"
            })

    return {
        "output_path": output_file,
        "rdb": rdb_rows
    }