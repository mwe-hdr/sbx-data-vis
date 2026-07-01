import os
import logging
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from utils.vis_helpers import format_date_range, apply_yaxis_format

def run(df, params, start_date, end_date, output_dir, generate_output_name):

    logging.info("Running vis_01_ed_hourly_arrivals")

    # =========================
    # DEFENSIVE CHECKS
    # =========================
    required_cols = ["ed_start_dtm", "esi"]
    for col in required_cols:
        if col not in df.columns:
            logging.error(f"vis_01: missing required column '{col}'")
            return

    # =========================
    # PARAM HANDLING
    # =========================
    params = params or {}
    chart_mode = params.get("chart_mode", "percent").lower()

    # ---- Label behavior ----
    label_threshold = float(params.get("label_threshold", 0.005))
    label_decimals = int(params.get("label_decimals", 1))
    label_multiplier = float(params.get("label_multiplier", 100))
    label_prefix = str(params.get("label_prefix", "")).strip()
    label_suffix = str(params.get("label_suffix", "")).strip()
    label_color = str(params.get("label_color", "white"))

    # ---- Figure ----
    fig_width = float(params.get("fig_width", 12))
    fig_height = float(params.get("fig_height", 6))
    dpi = int(params.get("dpi", 100))

    # ---- Fonts ----
    title_fs = int(params.get("title_fontsize", 14))
    axis_fs = int(params.get("axis_fontsize", 11))
    label_fs = int(params.get("label_fontsize", 8))
    legend_fs = int(params.get("legend_fontsize", 10))

    # ---- Legend ----
    legend_pos = params.get("legend_position", "upper left")
    legend_x = float(params.get("legend_anchor_x", 1.05))
    legend_y = float(params.get("legend_anchor_y", 1.0))

    # ---- Axis ----
    y_max = float(params.get("y_max", 1))
    y_axis_mode = params.get("y_axis_mode", chart_mode)
    y_axis_decimals = params.get("y_axis_decimals", 1)
    y_axis_multiplier = params.get("y_axis_multiplier", 100)
    y_axis_suffix = params.get("y_axis_suffix", "%")

    # ---- Colors ----
    colors = {
        '5 - Non-Urgent': params.get('5 - Non-Urgent', '#2ca02c'),
        '4 - Less Urgent': params.get('4 - Less Urgent', '#8fd0ff'),
        '3 - Urgent': params.get('3 - Urgent', '#1f77b4'),
        '2 - Emergent': params.get('2 - Emergent', '#17becf'),
        '1 - Immediate': params.get('1 - Immediate', '#ff7f0e'),
    }

    # =========================
    # FILTER
    # =========================
    subset = df[
        (df["ed_start_dtm"] >= start_date) &
        (df["ed_start_dtm"] <= end_date)
    ].copy()

    if subset.empty:
        logging.warning("vis_01: no data after filtering")
        return

    # =========================
    # DATA PREP
    # =========================
    subset["ed_start_dtm"] = pd.to_datetime(
    subset["ed_start_dtm"],
    errors="coerce"
    )

    subset = subset[
        subset["ed_start_dtm"].notna()
    ].copy()
    
    subset["arrival_hour"] = subset["ed_start_dtm"].dt.hour

    subset["esi"] = pd.to_numeric(
        subset["esi"],
        errors="coerce"
    )

    esi_map = {
        1: '1 - Immediate',
        2: '2 - Emergent',
        3: '3 - Urgent',
        4: '4 - Less Urgent',
        5: '5 - Non-Urgent'
    }

    subset["esi_category"] = subset["esi"].map(esi_map)

    subset = subset[subset["esi_category"].notna()]

    if subset.empty:
        logging.warning("vis_01: no valid ESI data")
        return

    # =========================
    # AGGREGATION
    # =========================
    grouped = (
        subset.groupby(["arrival_hour", "esi_category"])
        .size()
        .reset_index(name="count")
    )

    totals = grouped.groupby("arrival_hour")["count"].sum().reset_index(name="total")

    write_rdb = int(params.get("write_rdb", 0))
    rdb_rows = []

    merged = grouped.merge(totals, on="arrival_hour")
    merged["percent"] = merged["count"] / merged["total"]
    merged["percent"] = pd.to_numeric(merged["percent"], errors="coerce")
    merged["percent"] = merged["percent"].fillna(0)

    pivot_counts = (
        subset.groupby(["arrival_hour", "esi_category"])
        .size()
        .unstack(fill_value=0)
    )

    pivot_pct = merged.pivot(
        index="arrival_hour",
        columns="esi_category",
        values="percent"
    ).fillna(0)

    if chart_mode == "count":
        plot_data = pivot_counts
    else:
        plot_data = pivot_pct

    plot_data = plot_data.reindex(range(24), fill_value=0)

    esi_order = [
        '5 - Non-Urgent',
        '4 - Less Urgent',
        '3 - Urgent',
        '2 - Emergent',
        '1 - Immediate'
    ]

    for col in esi_order:
        if col not in plot_data.columns:
            plot_data[col] = 0

    plot_data = plot_data[esi_order]

    # =========================
    # LABEL FORMATTER
    # =========================
    def format_label(val):
        if not np.isfinite(val):
            return ""

        return f"{val:.{label_decimals}%}"
    
    # =========================
    # PLOT
    # =========================
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)

    
    if chart_mode == "count":
        pivot_plot = pivot_counts  
        y_label = "Number of Arrivals"
        y_limit = None
    else:
        pivot_plot = pivot_pct
        y_label = "Percentage"
        y_limit = y_max

    bottom = np.zeros(len(plot_data))

    ax.set_ylabel(y_label, fontsize=axis_fs)

    if y_limit:
        ax.set_ylim(0, y_limit)

    pivot_pct = pivot_pct.reindex(range(24), fill_value=0)
    
    for col in esi_order:
        values = plot_data[col].values

        ax.bar(
            plot_data.index,
            values,
            bottom=bottom,
            label=col,
            color=colors[col]
        )
        
        for i, v in enumerate(values):

            if chart_mode == "percent":
                value_for_label = v
            else:
                value_for_label = pivot_pct.loc[i, col]

            if not np.isfinite(value_for_label):
                continue

            if chart_mode == "percent":
                show_label = v > label_threshold
            else:
                show_label = value_for_label > label_threshold

            if show_label:
                ax.text(
                    i,
                    bottom[i] + v / 2,
                    format_label(value_for_label),
                    ha='center',
                    va='center',
                    color=label_color,
                    fontsize=label_fs
                )

        bottom += values

    # =========================
    # FORMATTING
    # =========================
    ax.set_xticks(range(24))
    ax.set_xlabel("Hour of Day", fontsize=axis_fs)

    date_range = format_date_range(start_date, end_date)
    title = f"Hourly Arrivals Distribution by ESI\n{date_range}"
    ax.set_title(title, fontsize=title_fs)

    ax.legend(
        loc=legend_pos,
        bbox_to_anchor=(legend_x, legend_y),
        fontsize=legend_fs
    )

    apply_yaxis_format(
    ax,
    mode=y_axis_mode,
    decimals=y_axis_decimals,
    multiplier=y_axis_multiplier,
    suffix=y_axis_suffix
    )

    plt.tight_layout()

    # =========================
    # SAVE
    # =========================
    output_file = os.path.join(
        output_dir,
        generate_output_name(
            visual_id="vis_01",
            start_date=start_date,
            end_date=end_date,
            cohort_id=params.get("cohort_id"),
            ext="png"
        )
    )

    plt.savefig(output_file)
    plt.close()

    logging.info(f"vis_01 output written: {output_file}")

    if write_rdb == 1:

        for _, row in totals.iterrows():

            hour_label = f"{int(row['arrival_hour']):02d}:00"

            rdb_rows.append({
                "run_id": params.get("run_id"),
                "visual_id": "vis_01",
                "client_name": params.get("client_name"),

                "domain": params.get("domain"),
                "cohort_id": params.get("cohort_id"),

                "domain_cohort":
                    f"{params.get('domain')}.{params.get('cohort_id')}",

                "dimension": "arrival_hour",
                "dimension_value": int(row["arrival_hour"]),
                "dimension_value_label": hour_label,

                "secondary_dimension": None,
                "secondary_dimension_value": None,

                "metric": "arrivals",
                "metric_type": "count",
                "value": int(row["total"]),

                "start_date": start_date,
                "end_date": end_date,

                "report_title":
                    "Hourly Arrivals Distribution by ESI"
            })

        for _, row in grouped.iterrows():

            hour_label = f"{int(row['arrival_hour']):02d}:00"

            rdb_rows.append({
                "run_id": params.get("run_id"),
                "visual_id": "vis_01",
                "client_name": params.get("client_name"),

                "domain": params.get("domain"),
                "cohort_id": params.get("cohort_id"),

                "domain_cohort":
                    f"{params.get('domain')}.{params.get('cohort_id')}",

                "dimension": "arrival_hour",
                "dimension_value": int(row["arrival_hour"]),
                "dimension_value_label": hour_label,

                "secondary_dimension": "esi_category",
                "secondary_dimension_value": row["esi_category"],

                "metric": "arrivals",
                "metric_type": "count",
                "value": int(row["count"]),

                "start_date": start_date,
                "end_date": end_date,

                "report_title":
                    "Hourly Arrivals Distribution by ESI"
            })

    return {
    "output_path": output_file,
    "rdb": rdb_rows
    }

