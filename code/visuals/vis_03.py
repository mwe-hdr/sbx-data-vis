# =============================================================================
# Report Name : Facility Visits by Year
#
# Description :
# Generates a yearly volume trend report showing the total number of
# Facility visits by calendar year. Facility visit dates are
# extracted from encounter timestamps and aggregated into annual visit
# counts for the selected reporting period.
#
# The visualization presents visit volume as a bar chart, allowing users
# to evaluate long-term demand trends, identify year-over-year changes in
# Facility utilization, and support strategic planning, resource allocation,
# and operational performance monitoring.
#
# Inputs :
#   - arrival_dtm  : Facility visit/arrival datetime
#   - start_date : Reporting period start date
#   - end_date   : Reporting period end date
#
# Outputs :
#   - PNG bar chart displaying total Facility visits by year
#       * X-axis: Arrival Year
#       * Y-axis: Number of Visits
#
# Key Metrics :
#   - Total Facility visits by year
#   - Annual volume trends across the reporting period
# =============================================================================

import os
import logging
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
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

VISUAL_ID = "vis_03"

def run(df, params, start_date, end_date, output_dir, generate_output_name):

    logger.info(f"[{VISUAL_ID}] Starting visualization")
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
        "title": "Facility Visits by Year",
    }

    # Merge params (override defaults)
    try:
        if params:
            default_params.update(params)
    except Exception as e:
        logger.warning(f"[{VISUAL_ID}] Failed to parse params: {e}")

    p = default_params
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
        p.get("legend_height", 1) or 1
    )
    tick_fontsize = int(
        p.get("tick_fontsize", 10) or 10
    )

    x_tick_rotation = float(
        p.get("x_tick_rotation", 0) or 0
    )

    # --------------------------------------------------
    # HELP MY DATAFRAME
    # --------------------------------------------------
    df = prepare_dates(df, start_date, end_date)
    df = add_common_helper_columns(df)

    logger.info(
        f"[{VISUAL_ID}] Dataset received after helper preparation. "
        f"Rows available for aggregation: {len(df):,}"
    )

    # =========================
    # VALIDATION
    # =========================
    required_columns = ["arrival_year"]

    for col in required_columns:
        if col not in df.columns:
            logger.error(f"[{VISUAL_ID}] Missing required column: {col}")
            return

    df = df.copy()

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
        logger.error(f"[{VISUAL_ID}] Aggregation failed: {e}")
        return

    if yearly.empty:
        logger.warning(f"[{VISUAL_ID}] No aggregated data available")
        return

    # =========================
    # RDB DATASET
    # =========================
    rdb_rows = []

    report_title = p.get("title", "Facility Visits by Year")

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
        logger.error(f"[{VISUAL_ID}] Failed to create figure: {e}")
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
        logger.error(f"[{VISUAL_ID}] Plotting failed: {e}")
        return

    legend_handles = [
        Patch(
            facecolor=p["bar_color"],
            label="Facility Visits"
        )
    ]

    legend_labels = [
        "Facility Visits"
    ]

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
        logger.warning(f"[{VISUAL_ID}] Labeling failed: {e}")

    # =========================
    # TITLES & AXES
    # =========================
    try:

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
        logger.warning(f"[{VISUAL_ID}] Axis labeling failed: {e}")

    ax.tick_params(
        axis="both",
        labelsize=tick_fontsize
    )

    ax.tick_params(
        axis="x",
        labelrotation=x_tick_rotation
    )

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
        logger.warning(f"[{VISUAL_ID}] Y-axis formatting failed: {e}")

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
            tick.set_fontsize(tick_fontsize)

        for tick in ax.get_yticklabels():
            tick.set_fontfamily(font_family)
            tick.set_fontsize(tick_fontsize)

        plt.savefig(output_path)

        legend_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id="vis_03_legend",
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
            f"[{VISUAL_ID}] Legend saved: "
            f"{legend_output_file}"
        )

        date_range_str = format_date_range(
            start_date,
            end_date
        )

        title_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id="vis_03_title",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        save_title_png(
            title=p["title"],
            subtitle=date_range_str,
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
            f"[{VISUAL_ID}] Title saved: "
            f"{title_output_file}"
        )

        plt.close()

        logger.info(
            f"[{VISUAL_ID}] Output saved: {output_path}"
        )

        logger.info(
            f"[{VISUAL_ID}] Generated "
            f"{len(rdb_rows):,} RDB rows"
        )

        return {
            "output_path": output_path,
            "rdb": rdb_rows
        }

    except Exception as e:
        logger.error(
            f"[{VISUAL_ID}] Failed to save output: {e}"
        )
        return