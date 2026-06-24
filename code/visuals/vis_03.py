import os
import logging
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from utils.vis_helpers import format_date_range

VISUAL_ID = "vis_03"

def run(df, params, start_date, end_date, output_dir, generate_output_name):
    """
    Visualization 03: ED Visits by Year
    """

    logging.info(f"[{VISUAL_ID}] Starting visualization")

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

    # =========================
    # VALIDATION
    # =========================
    required_columns = ["visit_dtm"]

    for col in required_columns:
        if col not in df.columns:
            logging.error(f"[{VISUAL_ID}] Missing required column: {col}")
            return

    df = df.copy()

    # =========================
    # DATA PREP
    # =========================
    try:
        df["visit_dtm"] = pd.to_datetime(df["visit_dtm"], errors="coerce")
        df = df.dropna(subset=["visit_dtm"])
    except Exception as e:
        logging.error(f"[{VISUAL_ID}] Failed to process visit_dtm: {e}")
        return

    # =========================
    # DATE FILTERING
    # =========================
    try:
        if start_date:
            start_dt = pd.to_datetime(start_date, errors="coerce")
        else:
            start_dt = df["visit_dtm"].min()

        if end_date:
            end_dt = pd.to_datetime(end_date, errors="coerce")
        else:
            end_dt = df["visit_dtm"].max()

        df = df[
            (df["visit_dtm"] >= start_dt) &
            (df["visit_dtm"] <= end_dt)
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
        df["arrival_year"] = df["visit_dtm"].dt.year
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
    # FIGURE SETUP
    # =========================
    try:
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
                    color=p["label_color"]
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
            fontsize=p["title_fontsize"]
        )

        ax.set_xlabel("Year", fontsize=p["axis_fontsize"])
        ax.set_ylabel("Number of Visits", fontsize=p["axis_fontsize"])
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
        filename = generate_output_name(VISUAL_ID, start_date, end_date)
        output_path = os.path.join(output_dir, filename)

        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()

        logging.info(f"[{VISUAL_ID}] Output saved: {output_path}")
    except Exception as e:
        logging.error(f"[{VISUAL_ID}] Failed to save output: {e}")