# =============================================================================
# Domain      : ED (Emergency Department)
# Report Name : ESI Level Distribution
#
# Description :
# Generates a distribution analysis of Emergency Department encounters by
# Emergency Severity Index (ESI) acuity level. Encounters are categorized
# into standard ESI classifications and summarized as a percentage of total
# ED volume for the selected reporting period.
#
# The visualization displays the relative acuity mix of ED patients across
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
# ED case mix over time.
#
# Inputs :
#   - ed_start_dtm : ED arrival/start datetime
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
#   - Total ED encounters
#   - Encounter count by ESI level
#   - Percent of encounters by ESI level
#   - Overall ED acuity mix
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

VISUAL_ID = "vis_04"


def run(df, params, start_date, end_date, output_dir, generate_output_name):
    """
    Visualization 04: ESI Level Distribution
    """

    logging.info(f"[{VISUAL_ID}] Starting visualization")
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

    required_columns = ["ed_start_dtm", "esi"]
    params = params or {}

    # ======================================================
    # VALIDATION
    # ======================================================
    for col in required_columns:
        if col not in df.columns:
            logging.error(f"[{VISUAL_ID}] Missing required column: {col}")
            return

    df = df.copy()

    # ======================================================
    # DATE HANDLING
    # ======================================================
    try:
        df["ed_start_dtm"] = pd.to_datetime(df["ed_start_dtm"], errors="coerce")
        mask = (df["ed_start_dtm"] >= pd.to_datetime(start_date)) & \
               (df["ed_start_dtm"] <= pd.to_datetime(end_date))
        df = df.loc[mask]
    except Exception as e:
        logging.error(f"[{VISUAL_ID}] Date filtering failed: {str(e)}")
        return

    if df.empty:
        logging.warning(f"[{VISUAL_ID}] No data after filtering")
        return

    # ======================================================
    # ESI CLEANING + MAPPING
    # ======================================================
    def map_esi(val):
        try:
            if pd.isna(val):
                return "0 - Unknown"
            val = int(val)
            if val == 1:
                return "1 - Immediate"
            elif val == 2:
                return "2 - Emergent"
            elif val == 3:
                return "3 - Urgent"
            elif val == 4:
                return "4 - Less Urgent"
            elif val == 5:
                return "5 - Non-Urgent"
            else:
                return "0 - Unknown"
        except Exception:
            return "0 - Unknown"

    df["esi_category"] = df["esi"].apply(map_esi)

    # ======================================================
    # AGGREGATION
    # ======================================================
    category_order = [
        "0 - Unknown",
        "1 - Immediate",
        "2 - Emergent",
        "3 - Urgent",
        "4 - Less Urgent",
        "5 - Non-Urgent",
    ]

    counts = df["esi_category"].value_counts().reindex(category_order, fill_value=0)

    total = counts.sum()
    if total == 0:
        logging.warning(f"[{VISUAL_ID}] Total encounter count is zero")
        return

    percents = counts / total

    # ======================================================
    # PLOTTING
    # ======================================================
    fig, ax = plt.subplots(
        figsize=(float(cfg["fig_width"]), float(cfg["fig_height"])),
        dpi=int(cfg["dpi"])
    )

    colors = [cfg.get(cat, "#333333") for cat in category_order]

    bars = ax.bar(category_order, percents.values, color=colors)

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
            color=cfg["label_color"]
        )

    # ======================================================
    # TITLES AND AXES
    # ======================================================
    date_range_str = format_date_range(start_date, end_date)

    ax.set_title(
        f"ESI Level Distribution\n{date_range_str}",
        fontsize=float(cfg["title_fontsize"])
    )

    ax.set_xlabel("ESI Level", fontsize=float(cfg["axis_fontsize"]))
    ax.set_ylabel("Percent of Encounters", fontsize=float(cfg["axis_fontsize"]))

    ax.tick_params(axis='x', rotation=30)

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
        plt.close()

        logging.info(f"[{VISUAL_ID}] Saved output to {output_file}")

    except Exception as e:
        logging.error(f"[{VISUAL_ID}] Failed to save output: {str(e)}")
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