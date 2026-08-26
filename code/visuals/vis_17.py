## =============================================================================
##
## Report Name : EMT Arrival Time Heatmap
##
## Description :
##
## Generates a day-of-week by hour-of-day heatmap for ambulatory,
## low-acuity Facility encounters.
##
## Population:
##
## - Arrival Method = Car / Walk-in
## - ESI = configurable (default 4,5)
##
## Heatmap Modes:
##
## - count
## - percent_total
## - percent_day
##
## Cell Label Modes:
##
## - count
## - percent
## - both
## - none
##
## Outputs:
##
## - PNG heatmap
## - Parameter PNG
## - Summary Table PNG
## - RDB output
##
## =============================================================================

import os
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from utils.vis_helpers import (
    normalize_params,
    format_date_range,
    get_display_parameters,
    save_parameter_table_png,
    save_title_png,
    save_legend_png,
    map_arrival_method
)
from utils.date_helpers import df_date_splitter

logger = logging.getLogger(__name__)

VISUAL_ID = "vis_17"

def _safe_int(value, default_value):
    try:
        return int(float(value))
    except Exception:
        return default_value


def run(
    df,
    params,
    start_date,
    end_date,
    output_dir,
    generate_output_name
):

    logger.info("[vis_17] Starting execution")

    params = normalize_params(params)

    fig_width = float(params.get("fig_width", 14))
    fig_height = float(params.get("fig_height", 7))
    dpi = _safe_int(params.get("dpi", 300), 300)
    font_family = str(
        params.get("font_family", "Segoe UI")
    ).strip()

    tick_fontsize = _safe_int(
        params.get("tick_fontsize", 8),
        8
    )

    title_width = float(
        params.get("title_width", 6.40) or 6.40
    )

    title_height = float(
        params.get("title_height", 0.25) or 0.25
    )

    title_fontsize = _safe_int(
        params.get("title_fontsize", 10),
        10
    )

    subtitle_fontsize = _safe_int(
        params.get("subtitle_fontsize", 8),
        8
    )

    title_background_color = str(
        params.get(
            "title_background_color",
            "#d9d9d9"
        )
    )

    title_weight = str(
        params.get(
            "title_weight",
            "bold"
        )
    )

    legend_width = float(
        params.get("legend_width", 4) or 4
    )

    legend_height = float(
        params.get("legend_height", 1) or 1
    )

    legend_fontsize = _safe_int(
        params.get("legend_fontsize", 8),
        8
    )


    heatmap_mode = str(
        params.get("heatmap_mode", "count")
    ).strip().lower()

    cmap = str(
        params.get("cmap", "YlOrRd")
    )

    show_cell_labels = _safe_int(
        params.get("show_cell_labels", 1),
        1
    )

    cell_label_mode = str(
        params.get("cell_label_mode", "both")
    ).strip().lower()

    cell_fontsize = _safe_int(
        params.get("cell_fontsize", 7),
        7
    )

    clinic_open_hour = _safe_int(
        params.get("clinic_open_hour", 8),
        8
    )

    clinic_close_hour = _safe_int(
        params.get("clinic_close_hour", 17),
        17
    )

    # --------------------------------------------------
    # HELP MY DATAFRAME
    # --------------------------------------------------
    _, df = df_date_splitter(df, start_date, end_date)

    required_cols = [
        "arrival_group",
        "esi",
        "arrival_day_of_week",
        "arrival_hour"
    ]

    missing_cols = [
        c for c in required_cols
        if c not in df.columns
    ]

    if missing_cols:
        raise ValueError(
            f"{VISUAL_ID}: Missing required columns: {missing_cols}"
        )

    df = df.copy()

    esi_values = str(
        params.get(
            "low_acuity_esi_values",
            "4;5"
        )
    )

    esi_list = []

    for value in esi_values.split(";"):
        value = value.strip()

        if value:
            try:
                esi_list.append(int(value))
            except Exception:
                pass

    df = df[
        df["arrival_group"]
        == "Car / Walk-in"
    ]

    df = df[
        df["esi"].isin(esi_list)
    ]

    weekday_order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday"
    ]

    counts = pd.crosstab(
        df["arrival_day_of_week"],
        df["arrival_hour"]
    )

    counts = counts.reindex(
        index=weekday_order,
        columns=list(range(24)),
        fill_value=0
    )

    total_visits = int(counts.values.sum())

    pct_total = (
        counts / total_visits * 100
        if total_visits > 0
        else counts * 0
    )

    pct_day = (
        counts.div(
            counts.sum(axis=1).replace(0, np.nan),
            axis=0
        )
        .fillna(0)
        * 100
    )

    if heatmap_mode == "percent_total":
        display_matrix = pct_total
        colorbar_label = "% of Total Visits"

    elif heatmap_mode == "percent_day":
        display_matrix = pct_day
        colorbar_label = "% Within Day"

    else:
        display_matrix = counts
        colorbar_label = "Encounter Count"

    weekday_total = int(
        counts.loc[
            ["Monday",
             "Tuesday",
             "Wednesday",
             "Thursday",
             "Friday"]
        ].values.sum()
    )

    weekend_total = int(
        counts.loc[
            ["Saturday", "Sunday"]
        ].values.sum()
    )

    in_hours_mask = (
        (df["arrival_hour"] >= clinic_open_hour)
        &
        (df["arrival_hour"] < clinic_close_hour)
        &
        (
            df["arrival_day_of_week"].isin(
                [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday"
                ]
            )
        )
    )

    in_hours_total = int(
        in_hours_mask.sum()
    )

    after_hours_total = int(
        total_visits - in_hours_total
    )

    if total_visits > 0:

        peak_idx = np.unravel_index(
            np.argmax(counts.values),
            counts.shape
        )

        peak_day = counts.index[
            peak_idx[0]
        ]

        peak_hour = int(
            counts.columns[peak_idx[1]]
        )

        peak_hour_day = (
            f"{peak_day} {peak_hour:02d}:00"
        )

    else:

        peak_day = ""
        peak_hour = ""
        peak_hour_day = ""

    plt.rcParams["font.family"] = font_family

    fig, ax = plt.subplots(
        figsize=(fig_width, fig_height)
    )

    img = ax.imshow(
        display_matrix.values,
        cmap=cmap,
        aspect="auto"
    )

    ax.set_xticks(range(24))
    ax.set_xticklabels(
        [f"{h:02d}" for h in range(24)],
        rotation=0
    )

    ax.set_yticks(range(len(weekday_order)))
    ax.set_yticklabels(weekday_order)

    ax.set_xlabel(
        "Hour of Day",
        fontfamily=font_family
    )

    ax.set_ylabel(
        "Day of Week",
        fontfamily=font_family
    )

    if show_cell_labels == 1:

        for r in range(len(weekday_order)):
            for c in range(24):

                count_val = int(
                    counts.iloc[r, c]
                )

                pct_val = float(
                    pct_total.iloc[r, c]
                )

                label = ""

                if cell_label_mode == "count":
                    label = f"{count_val}"

                elif cell_label_mode == "percent":
                    label = f"{pct_val:.1f}%"

                elif cell_label_mode == "both":
                    label = (
                        f"{count_val}\n"
                        f"{pct_val:.1f}%"
                    )

                if label:

                    ax.text(
                        c,
                        r,
                        label,
                        ha="center",
                        va="center",
                        fontsize=cell_fontsize,
                        fontfamily=font_family
                    )

    cbar = plt.colorbar(
        img,
        ax=ax
    )

    cbar.set_label(
        colorbar_label,
        fontfamily=font_family
    )

    plt.tight_layout()
    for tick in ax.get_xticklabels():
        tick.set_fontfamily(font_family)
        tick.set_fontsize(tick_fontsize)

    for tick in ax.get_yticklabels():
        tick.set_fontfamily(font_family)
        tick.set_fontsize(tick_fontsize)

    for tick in cbar.ax.get_yticklabels():
        tick.set_fontfamily(font_family)
        tick.set_fontsize(tick_fontsize)
    output_name = generate_output_name(
        visual_id=VISUAL_ID,
        start_date=start_date,
        end_date=end_date,
        ext="png"
    )

    output_file = os.path.join(
        output_dir,
        output_name
    )

    plt.savefig(
        output_file,
        dpi=dpi,
        bbox_inches="tight"
    )

    plt.close()

    legend_handles = [
        Patch(
            facecolor=plt.get_cmap(cmap)(0.75),
            label=colorbar_label
        )
    ]

    legend_labels = [
        colorbar_label
    ]

    legend_output_file = os.path.join(
        output_dir,
        generate_output_name(
            visual_id=f"{VISUAL_ID}_legend",
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
        font_size=legend_fontsize,
        width=legend_width,
        height=legend_height
    )

    logger.info(
        f"[vis_17] Legend written: "
        f"{legend_output_file}"
    )

    date_range = format_date_range(
        start_date,
        end_date
    )

    title_output_file = os.path.join(
        output_dir,
        generate_output_name(
            visual_id=f"{VISUAL_ID}_title",
            start_date=start_date,
            end_date=end_date,
            cohort_id=params.get("cohort_id"),
            ext="png"
        )
    )

    save_title_png(
        title="EMT Low-Acuity Arrival Time Heatmap",
        subtitle=date_range,
        output_file=title_output_file,
        width=title_width,
        height=title_height,
        dpi=dpi,
        font_family=font_family,
        title_fontsize=title_fontsize,
        subtitle_fontsize=subtitle_fontsize,
        background_color=title_background_color,
        title_weight=title_weight
    )

    logger.info(
        f"[vis_17] Title written: "
        f"{title_output_file}"
    )

    summary_rows = [
        ["Total Visits", f"{total_visits:,}"],
        ["Weekday Visits", f"{weekday_total:,}"],
        ["Weekend Visits", f"{weekend_total:,}"],
        ["In-Hours Visits", f"{in_hours_total:,}"],
        ["After-Hours Visits", f"{after_hours_total:,}"],
        ["Peak Day", peak_day],
        ["Peak Hour", peak_hour],
        ["Peak Hour-Day", peak_hour_day]
    ]

    try:

        summary_df = pd.DataFrame(
            summary_rows,
            columns=["Metric", "Value"]
        )

        fig, ax = plt.subplots(
            figsize=(6, 3)
        )

        ax.axis("off")

        table = ax.table(
            cellText=summary_df.values,
            colLabels=summary_df.columns,
            loc="center"
        )

        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.2)
        for cell in table.get_celld().values():
            cell.get_text().set_fontfamily(font_family)
        summary_png = output_file.replace(
            ".png",
            "_summary.png"
        )

        plt.tight_layout()

        plt.savefig(
            summary_png,
            dpi=dpi,
            bbox_inches="tight"
        )

        plt.close()

    except Exception as ex:

        logger.warning(
            f"[vis_17] Summary table export failed: {ex}"
        )

    try:

        display_params = (
            get_display_parameters(
                params
            )
        )

        if display_params:

            save_parameter_table_png(
                display_params,
                output_file.replace(
                    ".png",
                    "_params.png"
                ),
                font_family=font_family
            )

    except Exception as ex:

        logger.warning(
            f"[vis_17] Parameter export failed: {ex}"
        )

    write_rdb = int(
        params.get(
            "write_rdb",
            0
        )
    )

    rdb_rows = []

    if write_rdb == 1:

        rdb_rows.append({
            "run_id": params.get("run_id"),
            "client_name": params.get("client_name"),
            "domain": params.get("domain"),
            "cohort_id": params.get("cohort_id"),
            "domain_cohort": params.get("domain_cohort"),
            "visual_id": VISUAL_ID,
            "report_title": "EMT Arrival Time Heatmap",
            "start_date": start_date,
            "end_date": end_date,
            "metric": "summary",
            "total_visits": total_visits,
            "weekday_total": weekday_total,
            "weekend_total": weekend_total,
            "in_hours_total": in_hours_total,
            "after_hours_total": after_hours_total,
            "peak_day": peak_day,
            "peak_hour": peak_hour,
            "peak_hour_day": peak_hour_day
        })

        for day in weekday_order:

            for hour in range(24):

                count = int(
                    counts.loc[
                        day,
                        hour
                    ]
                )

                pct = float(
                    pct_total.loc[
                        day,
                        hour
                    ]
                )

                rdb_rows.append({
                    "run_id": params.get("run_id"),
                    "client_name": params.get("client_name"),
                    "domain": params.get("domain"),
                    "cohort_id": params.get("cohort_id"),
                    "domain_cohort": params.get("domain_cohort"),
                    "visual_id": VISUAL_ID,
                    "report_title": "EMT Arrival Time Heatmap",
                    "start_date": start_date,
                    "end_date": end_date,
                    "arrival_day_of_week": day,
                    "arrival_hour": hour,
                    "encounter_count": count,
                    "percent_of_total": round(
                        pct,
                        2
                    )
                })

    logger.info("[vis_17] Complete")

    return {
        "output_path": output_file,
        "rdb": rdb_rows
    }