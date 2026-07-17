# =============================================================================
# Domain      : ED (Emergency Department)
# Report Name : Encounters by Arrival Type
#
# Description :
# Generates a distribution analysis of Emergency Department encounters by
# method of arrival. Raw arrival method values are standardized into major
# transportation categories and displayed as a pie chart showing each
# category's share of total ED encounters.
#
# Arrival methods are grouped into:
#   - Ambulance
#   - Car / Private Vehicle
#   - Wheelchair
#   - Other
#
# The report highlights how patients access Emergency Department services
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
#   - ed_start_dtm      : Encounter/visit datetime (optional date filtering)
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
#   - Total ED encounters
#   - Encounters arriving by ambulance
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
    save_parameter_table_png
)

VISUAL_ID = "vis_07"

def run(df, params, start_date, end_date, output_dir, generate_output_name):
    """
    Visualization 07: Encounters by Arrival Type (Pie Chart)
    """

    logging.info(f"Starting {VISUAL_ID}")
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
        "color_ambulance": "#1f77b4",
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

    # =========================
    # VALIDATION
    # =========================
    required_cols = ["arrival_method"]

    for col in required_cols:
        if col not in df.columns:
            logging.error(f"{VISUAL_ID}: Missing required column '{col}'")
            return

    # optional ed_start_dtm for filtering
    if "ed_start_dtm" not in df.columns:
        logging.warning(f"{VISUAL_ID}: 'ed_start_dtm' not found - skipping date filter")

    df = df.copy()

    # =========================
    # DATETIME FILTERING
    # =========================
    if "ed_start_dtm" in df.columns:
        try:
            df["ed_start_dtm"] = pd.to_datetime(df["ed_start_dtm"], errors="coerce")
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)

            df = df[
                (df["ed_start_dtm"] >= start) &
                (df["ed_start_dtm"] <= end)
            ]
        except Exception as e:
            logging.warning(f"{VISUAL_ID}: Date filtering failed: {str(e)}")

    if df.empty:
        logging.warning(f"{VISUAL_ID}: No data after filtering")
        return

    # =========================
    # DATA CLEANING
    # =========================
    df = df[~df["arrival_method"].isna()]
    df["arrival_method"] = df["arrival_method"].astype(str).str.strip().str.lower()

    if df.empty:
        logging.warning(f"{VISUAL_ID}: No valid arrival_method values")
        return

    # =========================
    # MAPPING LOGIC
    # =========================
    def map_arrival(val):
        if "ambulance" in val or "ems" in val:
            return "Ambulance"
        elif any(x in val for x in ["walk", "self", "car", "vehicle", "private"]):
            return "Car"
        elif "wheelchair" in val:
            return "Wheelchair"
        else:
            return "Other"

    df["arrival_type"] = df["arrival_method"].apply(map_arrival)

    # =========================
    # AGGREGATION
    # =========================
    counts = (
        df.groupby("arrival_type")
        .size()
        .reset_index(name="count")
    )

    total = counts["count"].sum()

    if total <= 0:
        logging.warning(f"{VISUAL_ID}: Total encounters is zero")
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
            (counts["arrival_type"] != "Other")
        )

        if small_mask.any():
            other_sum = counts.loc[small_mask, "count"].sum()

            counts = counts.loc[~small_mask].copy()

            if other_sum > 0:
                # if Other already exists, add to it
                if "Other" in counts["arrival_type"].values:
                    counts.loc[counts["arrival_type"] == "Other", "count"] += other_sum
                else:
                    counts = pd.concat([
                        counts,
                        pd.DataFrame([{
                            "arrival_type": "Other",
                            "count": other_sum
                        }])
                    ], ignore_index=True)

            counts["percent"] = counts["count"] / counts["count"].sum()
 
    # =========================
    # ENSURE CATEGORY COMPLETENESS
    # =========================
    base_categories = ["Ambulance", "Car", "Wheelchair"]
    if include_other:
        base_categories.append("Other")

    counts = counts.set_index("arrival_type").reindex(base_categories).fillna(0)
    counts = counts.reset_index()

    # avoid divide-by-zero
    total = counts["count"].sum()
    if total > 0:
        counts["percent"] = counts["count"] / total
    else:
        logging.warning(f"{VISUAL_ID}: No data after category alignment")
        return

    # =========================
    # COLORS
    # =========================
    color_map = {
        "Ambulance": p["color_ambulance"],
        "Car": p["color_car"],
        "Wheelchair": p["color_wheelchair"],
        "Other": p["color_other"],
    }

    colors = [color_map.get(cat, "#cccccc") for cat in counts["arrival_type"]]

    # =========================
    # LABEL FUNCTION WITH SUPPRESSION
    # =========================
    def make_label(row):
        count = row["count"]
        percent = row["percent"]

        if percent < label_threshold:
            return ""

        parts = [row["arrival_type"]]

        if show_counts:
            parts.append(f"{int(count):,}")

        if show_percent:
            parts.append(f"{percent * 100:.{label_decimals}f}%")

        return "\n".join(parts)

    # remove zero-count categories 
    counts = counts[counts["count"] > 0].reset_index(drop=True)

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

        wedges, texts = ax.pie(
            counts["percent"],
            labels=labels,
            colors=colors,
            startangle=90,
        )

        for text in texts:
            text.set_fontfamily(font_family)

        ax.axis("equal")

        # title
        date_str = format_date_range(start_date, end_date)
        ax.set_title(
            f"Encounters by Arrival Type {date_str}",
            fontfamily=font_family
        )

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
        plt.close()

        logging.info(f"{VISUAL_ID}: Saved to {output_file}")

    except Exception as e:
        logging.error(f"{VISUAL_ID}: Plotting failed - {str(e)}")

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

            "dimension": "arrival_type",
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

                "dimension": "arrival_type",
                "dimension_value": row["arrival_type"],
                "dimension_value_label": row["arrival_type"],

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