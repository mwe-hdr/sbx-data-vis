import os
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from utils.vis_helpers import format_date_range, apply_yaxis_format

VISUAL_ID = "vis_04"


def run(df, params, start_date, end_date, output_dir, generate_output_name):
    """
    Visualization 04: ESI Level Distribution
    """

    logging.info(f"[{VISUAL_ID}] Starting visualization")

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

    required_columns = ["visit_dtm", "esi"]

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
        df["visit_dtm"] = pd.to_datetime(df["visit_dtm"], errors="coerce")
        mask = (df["visit_dtm"] >= pd.to_datetime(start_date)) & \
               (df["visit_dtm"] <= pd.to_datetime(end_date))
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
        filename = generate_output_name(VISUAL_ID, start_date, end_date)
        filepath = os.path.join(output_dir, filename)

        plt.savefig(filepath)
        plt.close()

        logging.info(f"[{VISUAL_ID}] Saved output to {filepath}")
    except Exception as e:
        logging.error(f"[{VISUAL_ID}] Failed to save output: {str(e)}")