# =============================================================================
# Report Name : Facility Encounters by Arrival Type
#
# Description :
# Generates a distribution analysis of Facility encounters by
# method of arrival. Raw arrival method values are standardized into major
# transportation categories and displayed as a pie chart showing each
# category's share of total Facility encounters.
#
# Arrival methods are grouped into:
#   - EMT
#   - Car / Private Vehicle
#   - Wheelchair
#   - Other
#
# The report highlights how patients access Facility services
# and provides insight into transportation patterns, emergency medical
# services utilization, and overall patient arrival mix. Small categories
# may optionally be consolidated into an "Other" group for improved
# visualization readability.
#
# This report supports:
#   - EMS utilization analysis
#   - Patient access pattern assessment
#   - Operational and resource planning
#   - Emergency transport utilization monitoring
#   - Population and case-mix reporting
#
# Inputs :
#   - arrival_method : Raw patient arrival method description
#   - arrival_dtm      : Encounter/visit datetime (optional date filtering)
#   - start_date     : Reporting period start date
#   - end_date       : Reporting period end date
#
# Outputs :
#   - PNG pie chart showing encounter distribution by arrival type
#   - RDB records containing:
#       * Total encounters (denominator)
#       * Encounter counts by arrival type
#       * Arrival type distribution metrics for downstream reporting
#
# Key Metrics :
#   - Total Facility encounters
#   - Encounters arriving by emt
#   - Encounters arriving by private vehicle/car
#   - Encounters arriving by wheelchair
#   - Encounters in other arrival categories
#   - Percent distribution by arrival type
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
    map_arrival_method
)
from utils.date_helpers import prepare_dates
from utils.col_helpers import add_common_helper_columns

logger = logging.getLogger(__name__)

VISUAL_ID = "vis_07"

def run(df, params, start_date, end_date, output_dir, generate_output_name):
    """
    Visualization 07: Encounters by Arrival Type (Pie Chart)
    """

    logger.info(f"Starting {VISUAL_ID}")
    params = normalize_params(params)

    # =========================
    # DEFAULT PARAMETERS
    # =========================
    defaults = {
        # behavior
        "include_other_category": True,
        "show_counts": True,
        "show_percent": True,
        "label_decimals": 1,

        # figure
        "fig_width": 8,
        "fig_height": 8,
        "dpi": 100,

        # colors
        "color_emt": "#1f77b4",
        "color_car": "#ff7f0e",
        "color_wheelchair": "#d62728",
        "color_other": "#7f7f7f",
    }

    # merge params safely
    p = defaults.copy()
    if params:
        for k, v in params.items():
            p[k] = v
    font_family = str(
        p.get("font_family", "Segoe UI")
    ).strip()

    # ---- Title Image ----

    title_width = float(
        p.get("title_width", 6.25) or 6.25
    )

    title_height = float(
        p.get("title_height", 0.6) or 0.6
    )

    subtitle_fontsize = int(
        p.get("subtitle_fontsize", 12) or 12
    )

    title_background_color = str(
        p.get(
            "title_background_color",
            "#d9d9d9"
        )
    )

    title_weight = str(
        p.get(
            "title_weight",
            "bold"
        )
    )

    legend_width = float(
        p.get("legend_width", 4) or 4
    )

    legend_height = float(
        p.get("legend_height", 2) or 2
    )

    legend_fontsize = int(
        p.get("legend_fontsize", 10) or 10
    )

    # =========================
    # PARAM HELPERS
    # =========================
    def to_bool(val):
        return str(val).lower() in ["true", "1", "yes"]

    def safe_float(val, default):
        try:
            return float(val)
        except Exception:
            return default

    # =========================
    # THRESHOLDS
    # =========================
    label_threshold = safe_float(p.get("label_threshold", 0.0), 0.0)
    group_other_threshold = safe_float(p.get("group_other_threshold", 0.0), 0.0)

    # =========================
    # LABEL PARAMS
    # =========================
    include_other = to_bool(p.get("include_other_category", True))
    show_counts = to_bool(p.get("show_counts", True))
    show_percent = to_bool(p.get("show_percent", True))

    try:
        label_decimals = int(p.get("label_decimals", 1))
    except Exception:
        label_decimals = 1

    # --------------------------------------------------
    # HELP MY DATAFRAME
    # --------------------------------------------------
    _, df = prepare_dates(df, start_date, end_date)
    df = add_common_helper_columns(df)

    logger.info(
        f"[{VISUAL_ID}] Dataset received after helper preparation. "
        f"Rows available for arrival-type analysis: {len(df):,}"
    )

    # =========================
    # VALIDATION
    # =========================
    required_cols = ["arrival_dtm","arrival_group"]

    for col in required_cols:
        if col not in df.columns:
            logger.error(f"{VISUAL_ID}: Missing required column '{col}'")
            return

    df = df.copy()

    # =========================
    # AGGREGATION
    # =========================
    counts = (
        df.groupby("arrival_group")
        .size()
        .reset_index(name="count")
    )

    total = counts["count"].sum()

    if total <= 0:
        logger.warning(f"{VISUAL_ID}: Total encounters is zero")
        return

    counts["percent"] = counts["count"] / total

    write_rdb = int(params.get("write_rdb", 0))
    rdb_rows = []

    # =========================
    # GROUP SMALL CATEGORIES INTO "OTHER"
    # =========================
    if group_other_threshold > 0:
        small_mask = (
            (counts["percent"] < group_other_threshold) &
            (counts["arrival_group"] != "Other")
        )

        if small_mask.any():
            other_sum = counts.loc[small_mask, "count"].sum()

            logger.info(
                f"[{VISUAL_ID}] Grouping small arrival categories into 'Other'. "
                f"Categories before filter: {len(counts):,}"
            )

            counts = counts.loc[~small_mask].copy()

            logger.info(
                f"[{VISUAL_ID}] Completed small-category consolidation. "
                f"Categories after filter: {len(counts):,}"
            )

            if other_sum > 0:
                # if Other already exists, add to it
                if "Other" in counts["arrival_group"].values:
                    counts.loc[counts["arrival_group"] == "Other", "count"] += other_sum
                else:
                    counts = pd.concat([
                        counts,
                        pd.DataFrame([{
                            "arrival_group": "Other",
                            "count": other_sum
                        }])
                    ], ignore_index=True)

            counts["percent"] = counts["count"] / counts["count"].sum()
 
    # =========================
    # ENSURE CATEGORY COMPLETENESS
    # =========================
    base_categories = ["EMT", "Car / Walk-in", "Wheelchair"]
    if include_other:
        base_categories.append("Other")

    counts = counts.set_index("arrival_group").reindex(base_categories).fillna(0)
    counts = counts.reset_index()

    # avoid divide-by-zero
    total = counts["count"].sum()
    if total > 0:
        counts["percent"] = counts["count"] / total
    else:
        logger.warning(f"{VISUAL_ID}: No data after category alignment")
        return

    # =========================
    # COLORS
    # =========================
    color_map = {
        "EMT": p["color_emt"],
        "Car / Walk-in": p["color_car"],
        "Wheelchair": p["color_wheelchair"],
        "Other": p["color_other"],
    }

    colors = [color_map.get(cat, "#cccccc") for cat in counts["arrival_group"]]

    # =========================
    # LABEL FUNCTION WITH SUPPRESSION
    # =========================
    def make_label(row):
        count = row["count"]
        percent = row["percent"]

        if percent < label_threshold:
            return ""

        parts = [row["arrival_group"]]

        if show_counts:
            parts.append(f"{int(count):,}")

        if show_percent:
            parts.append(f"{percent * 100:.{label_decimals}f}%")

        return "\n".join(parts)

    logger.info(
        f"[{VISUAL_ID}] Removing zero-count arrival categories. "
        f"Categories before filter: {len(counts):,}"
    )

    # remove zero-count categories 
    counts = counts[counts["count"] > 0].reset_index(drop=True)

    logger.info(
        f"[{VISUAL_ID}] Completed zero-count category filter. "
        f"Categories after filter: {len(counts):,}"
    )

    # rebuild labels 
    labels = [make_label(row) for _, row in counts.iterrows()]
    
    # =========================
    # PLOT
    # =========================
    try:
        plt.rcParams["font.family"] = font_family

        fig, ax = plt.subplots(
            figsize=(float(p["fig_width"]), float(p["fig_height"])),
            dpi=int(p["dpi"])
        )

        legend_labels = counts["arrival_group"].tolist()

        wedges, texts = ax.pie(
            counts["percent"],
            labels=labels,
            colors=colors,
            startangle=90,
        )

        legend_handles = wedges

        for text in texts:
            text.set_fontfamily(font_family)

        ax.axis("equal")

        # title

        # =========================
        # SAVE OUTPUT
        # =========================
        os.makedirs(output_dir, exist_ok=True)

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

        plt.tight_layout()
        plt.savefig(output_file)
        legend_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id="vis_07_legend",
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
            font_size=legend_fontsize,
            width=legend_width,
            height=legend_height
        )

        logger.info(
            f"{VISUAL_ID}: Legend saved: "
            f"{legend_output_file}"
        )
        date_str = format_date_range(
            start_date,
            end_date
        )

        title_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id="vis_07_title",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        save_title_png(
            title="Encounters by Arrival Type",
            subtitle=date_str,
            output_file=title_output_file,
            width=title_width,
            height=title_height,
            dpi=int(p["dpi"]),
            font_family=font_family,
            title_fontsize=14,
            subtitle_fontsize=subtitle_fontsize,
            background_color=title_background_color,
            title_weight=title_weight
        )

        logger.info(
            f"{VISUAL_ID}: Title saved: "
            f"{title_output_file}"
        )

        plt.close()

        logger.info(f"{VISUAL_ID}: Saved to {output_file}")

    except Exception as e:
        logger.error(f"{VISUAL_ID}: Plotting failed - {str(e)}")

    # =========================
    # RDB OUTPUT
    # =========================

    total_encounters = int(counts["count"].sum())

    if write_rdb == 1:
    
        rdb_rows.append({
            "run_id": params.get("run_id"),
            "visual_id": VISUAL_ID,
            "client_name": params.get("client_name"),

            "domain": params.get("domain"),
            "cohort_id": params.get("cohort_id"),

            "domain_cohort":
                f"{params.get('domain')}.{params.get('cohort_id')}",

            "dimension": "arrival_group",
            "dimension_value": "all",
            "dimension_value_label": "All Arrival Types",

            "secondary_dimension": None,
            "secondary_dimension_value": None,

            "metric": "encounters",
            "metric_type": "count",
            "value": total_encounters,

            "start_date": start_date,
            "end_date": end_date,

            "report_title":
                "Encounters by Arrival Type"
        })

        for _, row in counts.iterrows():

            rdb_rows.append({
                "run_id": params.get("run_id"),
                "visual_id": VISUAL_ID,
                "client_name": params.get("client_name"),

                "domain": params.get("domain"),
                "cohort_id": params.get("cohort_id"),

                "domain_cohort":
                    f"{params.get('domain')}.{params.get('cohort_id')}",

                "dimension": "arrival_group",
                "dimension_value": row["arrival_group"],
                "dimension_value_label": row["arrival_group"],

                "secondary_dimension": None,
                "secondary_dimension_value": None,

                "metric": "encounters",
                "metric_type": "count",
                "value": int(row["count"]),

                "start_date": start_date,
                "end_date": end_date,

                "report_title":
                    "Encounters by Arrival Type"
            })

        
        return {
            "output_path": output_file,
            "rdb": rdb_rows
        }
