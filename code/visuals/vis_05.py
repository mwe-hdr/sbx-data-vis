import os
import logging
import pandas as pd
import matplotlib.pyplot as plt

from utils.vis_helpers import format_date_range, apply_axis_range

VISUAL_ID = "vis_05"


def run(df, params, start_date, end_date, output_dir, generate_output_name):
    """
    Visualization 05: Monthly ED Arrivals Trend
    """

    logging.info(f"Starting {VISUAL_ID}")

    # =========================
    # DEFAULT PARAMETERS
    # =========================
    defaults = {
        # Figure
        "fig_width": 12,
        "fig_height": 6,
        "dpi": 100,

        # Fonts
        "title_fontsize": 14,
        "axis_fontsize": 11,
        "label_fontsize": 9,

        # Line styling
        "line_color": "#1f77b4",
        "marker": "o",
        "marker_size": 4,

        # Labels
        "show_labels": True,
        "label_first_last_only": True,
        "label_decimals": 0,

        # Axis
        "y_axis_separator": True,

        # Axis range
        "y_min": None,
        "y_max": None,

        # Title
        "title": "Monthly ED Arrivals",
    }

    # Merge params
    try:
        cfg = {k: params.get(k, v) for k, v in defaults.items()}
    except Exception:
        cfg = defaults

    # =========================
    # VALIDATION
    # =========================
    required_cols = ["visit_dtm"]
    for col in required_cols:
        if col not in df.columns:
            logging.error(f"{VISUAL_ID}: Missing required column '{col}'")
            return

    # =========================
    # DATA PREPARATION
    # =========================
    try:
        df = df.copy()

        # Convert datetime
        df["visit_dtm"] = pd.to_datetime(df["visit_dtm"], errors="coerce")

        # Drop invalid
        df = df.dropna(subset=["visit_dtm"])

        if df.empty:
            logging.warning(f"{VISUAL_ID}: No valid visit_dtm values")
            return

        # Filter by date range
        start_dt = pd.to_datetime(start_date, errors="coerce")
        end_dt = pd.to_datetime(end_date, errors="coerce")

        if pd.notna(start_dt):
            df = df[df["visit_dtm"] >= start_dt]
        if pd.notna(end_dt):
            df = df[df["visit_dtm"] <= end_dt]

        if df.empty:
            logging.warning(f"{VISUAL_ID}: No data after date filtering")
            return

    except Exception as e:
        logging.error(f"{VISUAL_ID}: Data preparation failed - {str(e)}")
        return

    # =========================
    # FEATURE ENGINEERING
    # =========================
    try:
        df["year_month"] = df["visit_dtm"].dt.to_period("M").dt.to_timestamp()

    except Exception as e:
        logging.error(f"{VISUAL_ID}: Feature engineering failed - {str(e)}")
        return

    # =========================
    # AGGREGATION
    # =========================
    try:
        monthly_counts = (
            df.groupby("year_month")
            .size()
            .rename("arrival_count")
            .reset_index()
        )

        if monthly_counts.empty:
            logging.warning(f"{VISUAL_ID}: Aggregation resulted in empty dataset")
            return

        # Create full continuous monthly index
        full_range = pd.date_range(
            start=monthly_counts["year_month"].min(),
            end=monthly_counts["year_month"].max(),
            freq="MS"
        )

        monthly_counts = monthly_counts.set_index("year_month").reindex(full_range, fill_value=0)
        monthly_counts.index.name = "year_month"
        monthly_counts = monthly_counts.reset_index()

    except Exception as e:
        logging.error(f"{VISUAL_ID}: Aggregation failed - {str(e)}")
        return

    # =========================
    # LABEL FORMATTING HELPERS
    # =========================
    def format_number(x):
        try:
            return f"{int(round(x, 0)):,}"
        except Exception:
            return str(x)

    # =========================
    # PLOTTING
    # =========================
    try:
        fig, ax = plt.subplots(
            figsize=(float(cfg["fig_width"]), float(cfg["fig_height"])),
            dpi=int(cfg["dpi"])
        )

        x = monthly_counts["year_month"]
        y = monthly_counts["arrival_count"]

        ax.plot(
            x,
            y,
            color=cfg["line_color"],
            marker=cfg["marker"],
            markersize=float(cfg["marker_size"])
        )

        # X-axis labels
        if len(x) > 24:
            labels = x.dt.strftime("%Y-%m")
        else:
            labels = x.dt.strftime("%b %Y")

        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha="right")

        # Titles
        date_range_str = format_date_range(start_date, end_date)
        ax.set_title(
            f"{cfg['title']} {date_range_str}",
            fontsize=int(cfg["title_fontsize"])
        )

        ax.set_xlabel("Month", fontsize=int(cfg["axis_fontsize"]))
        ax.set_ylabel("Number of Arrivals", fontsize=int(cfg["axis_fontsize"]))

        # Y-axis formatting
        if cfg["y_axis_separator"]:
            ax.get_yaxis().set_major_formatter(
                plt.FuncFormatter(lambda val, pos: f"{int(val):,}")
            )

        # Apply axis range (after plotting)
        apply_axis_range(
            ax,
            axis="y",
            min_val=cfg.get("y_min"),
            max_val=cfg.get("y_max")
        )

        # =========================
        # DATA LABELS
        # =========================
        if cfg["show_labels"]:
            try:
                indices = range(len(y))

                if cfg["label_first_last_only"]:
                    indices = [0, len(y) - 1]

                for i in indices:
                    ax.text(
                        x.iloc[i],
                        y.iloc[i],
                        format_number(y.iloc[i]),
                        fontsize=int(cfg["label_fontsize"]),
                        ha="center",
                        va="bottom"
                    )
            except Exception as e:
                logging.warning(f"{VISUAL_ID}: Label rendering failed - {str(e)}")

        plt.tight_layout()

        # =========================
        # SAVE OUTPUT
        # =========================
        filename = generate_output_name(VISUAL_ID, start_date, end_date)
        filepath = os.path.join(output_dir, filename)

        plt.savefig(filepath)
        plt.close()

        logging.info(f"{VISUAL_ID}: Saved output to {filepath}")

    except Exception as e:
        logging.error(f"{VISUAL_ID}: Plotting failed - {str(e)}")
        return