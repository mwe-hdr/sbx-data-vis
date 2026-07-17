# =============================================================================
# Domain      : ED (Emergency Department)
# Report Name : ED Visits by Year
#
# Description :
# Generates a yearly volume trend report showing the total number of
# Emergency Department visits by calendar year. ED visit dates are
# extracted from encounter timestamps and aggregated into annual visit
# counts for the selected reporting period.
#
# The visualization presents visit volume as a bar chart, allowing users
# to evaluate long-term demand trends, identify year-over-year changes in
# ED utilization, and support strategic planning, resource allocation,
# and operational performance monitoring.
#
# Inputs :
#   - ed_start_dtm  : ED visit/arrival datetime
#   - start_date : Reporting period start date
#   - end_date   : Reporting period end date
#
# Outputs :
#   - PNG bar chart displaying total ED visits by year
#       * X-axis: Arrival Year
#       * Y-axis: Number of Visits
#
# Key Metrics :
#   - Total ED visits by year
#   - Annual volume trends across the reporting period
# =============================================================================

import os
import logging
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
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
VISUAL_ID = "vis_03"

def run(df, params, start_date, end_date, output_dir, generate_output_name):
    """
    Visualization 03: ED Visits by Year
    """

    logging.info(f"[{VISUAL_ID}] Starting visualization")
    params = normalize_params(params)

    # =========================
    # DEFAULT PARAMETERS
    # =========================
    default_params = {
        # Figure
        "fig_width": 12,
        "fig_height": 6,
        "dpi": 100,

        # Fonts
        "title_fontsize": 14,
        "axis_fontsize": 11,
        "label_fontsize": 9,

        # Labels
        "label_decimals": 0,
        "label_color": "black",
        "label_threshold": 0,

        # Axis
        "y_axis_use_commas": True,
        "y_axis_decimals": 0,

        # Colors
        "bar_color": "#1f77b4",

        # Title
        "title": "ED Visits by Year",
    }

    # Merge params (override defaults)
    try:
        if params:
            default_params.update(params)
    except Exception as e:
        logging.warning(f"[{VISUAL_ID}] Failed to parse params: {e}")

    p = default_params
    font_family = str(
        p.get("font_family", "Segoe UI")
    ).strip()

    # =========================
    # VALIDATION
    # =========================
    required_columns = ["ed_start_dtm"]

    for col in required_columns:
        if col not in df.columns:
            logging.error(f"[{VISUAL_ID}] Missing required column: {col}")
            return

    df = df.copy()

    # =========================
    # DATA PREP
    # =========================
    try:
        df["ed_start_dtm"] = pd.to_datetime(df["ed_start_dtm"], errors="coerce")
        df = df.dropna(subset=["ed_start_dtm"])
    except Exception as e:
        logging.error(f"[{VISUAL_ID}] Failed to process ed_start_dtm: {e}")
        return

    # =========================
    # DATE FILTERING
    # =========================
    try:
        if start_date:
            start_dt = pd.to_datetime(start_date, errors="coerce")
        else:
            start_dt = df["ed_start_dtm"].min()

        if end_date:
            end_dt = pd.to_datetime(end_date, errors="coerce")
        else:
            end_dt = df["ed_start_dtm"].max()

        df = df[
            (df["ed_start_dtm"] >= start_dt) &
            (df["ed_start_dtm"] <= end_dt)
        ]
    except Exception as e:
        logging.warning(f"[{VISUAL_ID}] Date filtering failed: {e}")

    if df.empty:
        logging.warning(f"[{VISUAL_ID}] No data after filtering")
        return

    # =========================
    # FEATURE ENGINEERING
    # =========================
    try:
        df["arrival_year"] = df["ed_start_dtm"].dt.year
    except Exception as e:
        logging.error(f"[{VISUAL_ID}] Failed to derive year: {e}")
        return

    # =========================
    # AGGREGATION
    # =========================
    try:
        yearly = (
            df.groupby("arrival_year")
            .size()
            .reset_index(name="visits")
            .sort_values("arrival_year")
        )
    except Exception as e:
        logging.error(f"[{VISUAL_ID}] Aggregation failed: {e}")
        return

    if yearly.empty:
        logging.warning(f"[{VISUAL_ID}] No aggregated data available")
        return

    # =========================
    # RDB DATASET
    # =========================
    rdb_rows = []

    report_title = p.get("title", "ED Visits by Year")

    for _, row in yearly.iterrows():

        rdb_rows.append({
            "run_id": params.get("run_id"),
            "visual_id": VISUAL_ID,
            "client_name": params.get("client_name"),

            "domain": params.get("domain"),
            "cohort_id": params.get("cohort_id"),

            "domain_cohort":
                f"{params.get('domain')}.{params.get('cohort_id')}",

            "dimension": "year",
            "dimension_value": int(row["arrival_year"]),
            "dimension_value_label": str(int(row["arrival_year"])),

            "secondary_dimension": "",
            "secondary_dimension_value": "",

            "metric": "ed_visits",
            "metric_type": "count",
            "value": float(row["visits"]),

            "start_date": start_date,
            "end_date": end_date,

            "report_title": report_title
        })

    # =========================
    # FIGURE SETUP
    # =========================
    try:
        plt.rcParams["font.family"] = font_family

        fig, ax = plt.subplots(
            figsize=(float(p["fig_width"]), float(p["fig_height"])),
            dpi=int(p["dpi"])
        )
    except Exception as e:
        logging.error(f"[{VISUAL_ID}] Failed to create figure: {e}")
        return

    # =========================
    # PLOT
    # =========================
    try:
        bars = ax.bar(
            yearly["arrival_year"].astype(str),
            yearly["visits"],
            color=p["bar_color"]
        )
    except Exception as e:
        logging.error(f"[{VISUAL_ID}] Plotting failed: {e}")
        return

    # =========================
    # LABELS ON BARS
    # =========================
    try:
        threshold = float(p["label_threshold"])
        decimals = int(p["label_decimals"])

        for bar, value in zip(bars, yearly["visits"]):
            if value >= threshold:
                label = f"{value:,.{decimals}f}"
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    label,
                    ha="center",
                    va="bottom",
                    fontsize=p["label_fontsize"],
                    color=p["label_color"],
                    fontfamily=font_family
                )
    except Exception as e:
        logging.warning(f"[{VISUAL_ID}] Labeling failed: {e}")

    # =========================
    # TITLES & AXES
    # =========================
    try:
        date_range_str = format_date_range(start_date, end_date)

        ax.set_title(
            f"{p['title']} {date_range_str}",
            fontsize=p["title_fontsize"],
            fontfamily=font_family
        )

        ax.set_xlabel(
            "Year",
            fontsize=p["axis_fontsize"],
            fontfamily=font_family
        )
        ax.set_ylabel(
            "Number of Visits",
            fontsize=p["axis_fontsize"],
            fontfamily=font_family
        )
    except Exception as e:
        logging.warning(f"[{VISUAL_ID}] Axis labeling failed: {e}")

    # =========================
    # CLEANUP
    # =========================
    try:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", linestyle="--", alpha=0.3)
    except Exception:
        pass

    # =========================
    # Y-AXIS FORMATTING
    # =========================
    try:
        if str(p.get("y_axis_use_commas", True)).lower() == "true":
            decimals = int(p.get("y_axis_decimals", 0))
            format_str = f'{{x:,.{decimals}f}}'
            ax.yaxis.set_major_formatter(
                mtick.StrMethodFormatter(format_str)
            )
    except Exception as e:
        logging.warning(f"[{VISUAL_ID}] Y-axis formatting failed: {e}")

    # =========================
    # SAVE OUTPUT
    # =========================
    try:
        filename = generate_output_name(
            visual_id=VISUAL_ID,
            start_date=start_date,
            end_date=end_date,
            cohort_id=params.get("cohort_id"),
            ext="png"
        )

        output_path = os.path.join(
            output_dir,
            filename
        )

        plt.tight_layout()
        for tick in ax.get_xticklabels():
            tick.set_fontfamily(font_family)

        for tick in ax.get_yticklabels():
            tick.set_fontfamily(font_family)

        plt.savefig(output_path)
        plt.close()

        logging.info(
            f"[{VISUAL_ID}] Output saved: {output_path}"
        )

        logging.info(
            f"[{VISUAL_ID}] Generated "
            f"{len(rdb_rows):,} RDB rows"
        )

        return {
            "output_path": output_path,
            "rdb": rdb_rows
        }

    except Exception as e:
        logging.error(
            f"[{VISUAL_ID}] Failed to save output: {e}"
        )
        return