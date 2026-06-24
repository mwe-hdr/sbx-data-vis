import os
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from utils.vis_helpers import format_date_range, apply_yaxis_format


def run(df, params, start_date, end_date, output_dir, generate_output_name):
    """
    Visualization 02: Length of Stay Distribution (Hours)

    Generates a histogram-style bar chart showing the distribution of
    ED Length of Stay (LOS) in hourly buckets as percentages.
    """

    logging.info("Starting vis_02: Length of Stay Distribution")

    try:
        # --------------------------------------------------
        # DEFAULT PARAMETERS
        # --------------------------------------------------
        defaults = {
            "fig_width": 12,
            "fig_height": 6,
            "dpi": 100,
            "title_fontsize": 14,
            "axis_fontsize": 11,
            "label_fontsize": 9,
            "label_decimals": 1,
            "label_threshold": 0.0,  # show all by default
            "max_bucket": None  # optional cap (e.g., 24)
        }

        y_axis_mode = params.get("y_axis_mode", "percent")
        y_axis_decimals = params.get("y_axis_decimals", 1)
        y_axis_multiplier = params.get("y_axis_multiplier", 100)
        y_axis_suffix = params.get("y_axis_suffix", "%")

        # Merge params (override defaults)
        p = {**defaults, **(params or {})}

        # Cast numeric params safely
        for key in ["fig_width", "fig_height", "dpi",
                    "title_fontsize", "axis_fontsize",
                    "label_fontsize", "label_decimals",
                    "label_threshold"]:
            try:
                p[key] = float(p[key])
            except Exception:
                logging.warning(f"Invalid param for {key}, using default")
                p[key] = defaults[key]

        if p["max_bucket"] not in (None, ""):
            try:
                p["max_bucket"] = int(p["max_bucket"])
            except Exception:
                logging.warning("Invalid max_bucket, ignoring")
                p["max_bucket"] = None

        # --------------------------------------------------
        # REQUIRED COLUMNS CHECK
        # --------------------------------------------------
        required_cols = ["ed_start_dtm", "ed_end_dtm"]
        for col in required_cols:
            if col not in df.columns:
                logging.error(f"Missing required column: {col}")
                return

        # --------------------------------------------------
        # DATETIME HANDLING
        # --------------------------------------------------
        df["ed_start_dtm"] = pd.to_datetime(df["ed_start_dtm"], errors="coerce")
        df["ed_end_dtm"] = pd.to_datetime(df["ed_end_dtm"], errors="coerce")

        # Drop null timestamps
        df = df.dropna(subset=["ed_start_dtm", "ed_end_dtm"])

        # --------------------------------------------------
        # DATE FILTERING
        # --------------------------------------------------
        try:
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
        except Exception:
            logging.error("Invalid start_date or end_date")
            return

        df = df[(df["ed_start_dtm"] >= start_dt) & (df["ed_start_dtm"] <= end_dt)]

        if df.empty:
            logging.warning("vis_02: No data after filtering")
            return

        # --------------------------------------------------
        # LOS CALCULATION (HOURS)
        # --------------------------------------------------
        df["los_hours"] = (
            (df["ed_end_dtm"] - df["ed_start_dtm"])
            .dt.total_seconds() / 3600.0
        )

        # Remove invalid LOS
        df = df[(df["los_hours"].notna()) & (df["los_hours"] >= 0)]

        if df.empty:
            logging.warning("vis_02: No valid LOS values")
            return

        # --------------------------------------------------
        # BUCKETING
        # --------------------------------------------------
        df["los_bucket"] = np.floor(df["los_hours"]).astype(int)

        # Optional max bucket cap
        if p["max_bucket"] is not None:
            df["los_bucket"] = np.where(
                df["los_bucket"] >= p["max_bucket"],
                p["max_bucket"],
                df["los_bucket"]
            )

        # --------------------------------------------------
        # AGGREGATION
        # --------------------------------------------------
        grouped = df.groupby("los_bucket").size().reset_index(name="count")

        total = grouped["count"].sum()
        grouped["percent"] = grouped["count"] / total

        # Ensure continuity of buckets
        min_bucket = int(grouped["los_bucket"].min())
        max_bucket = int(grouped["los_bucket"].max())

        all_buckets = pd.DataFrame({
            "los_bucket": range(min_bucket, max_bucket + 1)
        })

        grouped = all_buckets.merge(grouped, on="los_bucket", how="left").fillna(0)

        # --------------------------------------------------
        # PLOTTING
        # --------------------------------------------------
        fig, ax = plt.subplots(figsize=(p["fig_width"], p["fig_height"]))

        ax.bar(
            grouped["los_bucket"],
            grouped["percent"],
            width=0.8
        )

        # Labels above bars
        for _, row in grouped.iterrows():
            if row["percent"] >= p["label_threshold"]:
                ax.text(
                    row["los_bucket"],
                    row["percent"] + 0.001,
                    f"{row['percent'] * 100:.{int(p['label_decimals'])}f}%",
                    ha="center",
                    fontsize=p["label_fontsize"]
                )
        
        date_range = format_date_range(start_date, end_date)
        ax.set_title(
            f"Length of Stay Distribution (Hours)\n{date_range}",
            fontsize=p["title_fontsize"]
        )
        ax.set_xlabel("Length of Stay (Hours)", fontsize=p["axis_fontsize"])
        ax.set_ylabel("Percent of Encounters", fontsize=p["axis_fontsize"])

        # Improve layout
        ax.set_xticks(grouped["los_bucket"])
        plt.xticks(rotation=45)
        
        apply_yaxis_format(
            ax,
            mode=y_axis_mode,
            decimals=y_axis_decimals,
            multiplier=y_axis_multiplier,
            suffix=y_axis_suffix
        )
        
        plt.tight_layout()

        # --------------------------------------------------
        # SAVE OUTPUT
        # --------------------------------------------------
        filename = generate_output_name("vis_02", start_date, end_date)
        output_path = os.path.join(output_dir, filename)

        plt.savefig(output_path, dpi=int(p["dpi"]))
        plt.close()

        logging.info(f"vis_02 saved to {output_path}")

    except Exception as e:
        logging.error(f"vis_02 failed: {str(e)}")