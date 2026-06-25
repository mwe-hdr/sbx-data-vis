import os
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from utils.vis_helpers import format_date_range, apply_yaxis_format


VISUAL_ID = "vis_06"


def run(df, params, start_date, end_date, output_dir, generate_output_name):
    """
    Visualization 06: Weekday Arrival Distribution
    """

    logging.info(f"Starting {VISUAL_ID}")

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

        # Merge params
        cfg = {**defaults, **(params or {})}

        # =============================
        # VALIDATION
        # =============================
        required_cols = ["visit_dtm"]
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            logging.error(f"{VISUAL_ID} missing required columns: {missing_cols}")
            return

        df = df.copy()

        # =============================
        # DATETIME HANDLING
        # =============================
        df["visit_dtm"] = pd.to_datetime(df["visit_dtm"], errors="coerce")

        df = df.dropna(subset=["visit_dtm"])

        if df.empty:
            logging.warning(f"{VISUAL_ID}: No valid visit_dtm after conversion")
            return

        # =============================
        # DATE FILTER
        # =============================
        try:
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)

            df = df[(df["visit_dtm"] >= start_dt) & (df["visit_dtm"] <= end_dt)]
        except Exception as e:
            logging.warning(f"{VISUAL_ID}: Date filtering failed: {str(e)}")

        if df.empty:
            logging.warning(f"{VISUAL_ID}: No data after date filtering")
            return

        # =============================
        # DERIVE WEEKDAY
        # =============================
        df["weekday_num"] = df["visit_dtm"].dt.dayofweek

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

        # Required display order per spec
        ordered_days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

        # =============================
        # AGGREGATION
        # =============================
        counts = df["weekday"].value_counts().reindex(ordered_days, fill_value=0)

        total = counts.sum()

        if total == 0:
            logging.warning(f"{VISUAL_ID}: Total encounters = 0")
            return

        percents = counts / total

        # =============================
        # PLOT
        # =============================
        fig, ax = plt.subplots(
            figsize=(float(cfg["fig_width"]), float(cfg["fig_height"])),
            dpi=int(cfg["dpi"])
        )

        bars = ax.bar(
            ordered_days,
            percents.values,
            color=cfg["bar_color"]
        )

        # =============================
        # LABELS
        # =============================
        for bar, val in zip(bars, percents.values):
            if val < float(cfg["label_threshold"]):
                continue

            label = f"{val * 100:.{int(cfg['label_decimals'])}f}%"

            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                label,
                ha="center",
                va="bottom",
                fontsize=int(cfg["label_fontsize"]),
                color=cfg["label_color"]
            )

        # =============================
        # TITLES / AXES
        # =============================
        date_range_str = format_date_range(start_date, end_date)

        ax.set_title(
            f"Weekday Arrival Distribution {date_range_str}",
            fontsize=int(cfg["title_fontsize"])
        )

        ax.set_xlabel("Day of Week", fontsize=int(cfg["axis_fontsize"]))
        ax.set_ylabel("Percent of Arrivals", fontsize=int(cfg["axis_fontsize"]))

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

        # =============================
        # OUTPUT
        # =============================
        filename = generate_output_name(VISUAL_ID, start_date, end_date)
        output_path = os.path.join(output_dir, filename)

        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()

        logging.info(f"{VISUAL_ID} saved to {output_path}")

    except Exception as e:
        logging.error(f"{VISUAL_ID} failed: {str(e)}", exc_info=True)