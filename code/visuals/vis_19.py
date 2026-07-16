# =============================================================================
#
# Domain      : ED (Emergency Department)
#
# Report Name : LOS by Arrival Method and ESI
#
# Description :
#
# Compares Emergency Department LOS across:
#
#     Arrival Method
#     x
#     ESI Level
#
# Supports:
#
#     boxplot
#     median_bar
#
# Calculates:
#
#     Encounter Count
#     Mean LOS
#     Median LOS
#     P25 LOS
#     P75 LOS
#     P90 LOS
#     Maximum LOS
#     Census Contribution
#
# Census Contribution =
#
#     Encounter Count * Mean LOS
#
# Outputs:
#
#     Main PNG
#     Summary Table PNG
#     Parameter PNG
#     Legend PNG
#     RDB Output
#
# =============================================================================

import os
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from utils.vis_helpers import (
    normalize_params,
    format_date_range,
    save_parameter_table_png,
    save_legend_png,
    get_display_parameters
)

VISUAL_ID = "vis_19"

logger = logging.getLogger(__name__)


def _safe_param(params, key, default, cast_type=None):
    try:
        val = params.get(key, default)
        return cast_type(val) if cast_type else val
    except Exception:
        logger.warning(
            f"[{VISUAL_ID}] invalid parameter {key}; "
            f"using default {default}"
        )
        return default


def _map_arrival_method(value):

    if pd.isna(value):
        return "Other"

    txt = str(value).strip().lower()

    ambulance_terms = [
        "ambulance",
        "medical flight",
        "hospital transport",
        "tc bls stretcher",
        "tc als stretcher",
        "tc critical care team",
        "tc pals stretcher",
        "tc bariatric"
    ]

    if any(term in txt for term in ambulance_terms):
        return "Ambulance"

    if (
        txt == "police"
        or "police" in txt
        or "sheriff" in txt
    ):
        return "Police"

    if (
        "wheelchair" in txt
        or "wheelchair van" in txt
    ):
        return "Wheelchair"

    car_walk_terms = [
        "car",
        "walk",
        "ambulatory",
        "assist from vehicle",
        "self",
        "taxi",
        "public transportation",
        "bus",
        "community assistance"
    ]

    if any(term in txt for term in car_walk_terms):
        return "Car / Walk-in"

    return "Other"


def run(
    df,
    params,
    start_date,
    end_date,
    output_dir,
    generate_output_name
):

    logger.info(f"[{VISUAL_ID}] Starting execution")

    params = normalize_params(params)

    required_cols = [
        "arrival_method",
        "esi",
        "ed_start_dtm",
        "ed_stop_dtm"
    ]

    missing_cols = [
        c for c in required_cols
        if c not in df.columns
    ]

    if missing_cols:
        raise ValueError(
            f"{VISUAL_ID}: Missing required columns: "
            f"{missing_cols}"
        )

    fig_width = _safe_param(
        params,
        "fig_width",
        14,
        float
    )

    fig_height = _safe_param(
        params,
        "fig_height",
        8,
        float
    )

    dpi = _safe_param(
        params,
        "dpi",
        300,
        int
    )

    display_mode = str(
        params.get(
            "display_mode",
            "boxplot"
        )
    ).strip().lower()

    show_outliers = int(
        float(
            params.get(
                "show_outliers",
                1
            )
        )
    )

    show_data_labels = int(
        float(
            params.get(
                "show_data_labels",
                0
            )
        )
    )

    min_los_hours = float(
        params.get(
            "min_los_hours",
            0
        )
    )

    max_los_hours = float(
        params.get(
            "max_los_hours",
            240
        )
    )

    table_fontsize = _safe_param(
        params,
        "table_fontsize",
        8,
        int
    )

    colors = {
        "Ambulance":
            params.get(
                "ambulance_color",
                "#E15759"
            ),
        "Car / Walk-in":
            params.get(
                "walkin_color",
                "#4E79A7"
            ),
        "Wheelchair":
            params.get(
                "wheelchair_color",
                "#76B7B2"
            ),
        "Police":
            params.get(
                "police_color",
                "#F28E2B"
            ),
        "Other":
            params.get(
                "other_color",
                "#BAB0AC"
            )
    }

    work_df = df.copy()

    work_df["ed_start_dtm"] = pd.to_datetime(
        work_df["ed_start_dtm"],
        errors="coerce"
    )

    work_df["ed_stop_dtm"] = pd.to_datetime(
        work_df["ed_stop_dtm"],
        errors="coerce"
    )

    work_df = work_df.dropna(
        subset=[
            "ed_start_dtm",
            "ed_stop_dtm"
        ]
    )

    work_df["esi"] = pd.to_numeric(
        work_df["esi"],
        errors="coerce"
    )

    work_df = work_df[
        work_df["esi"].isin([1, 2, 3, 4, 5])
    ]

    work_df["los_hours"] = (
        (
            work_df["ed_stop_dtm"]
            -
            work_df["ed_start_dtm"]
        ).dt.total_seconds()
        / 3600
    )

    work_df = work_df[
        work_df["los_hours"] >= min_los_hours
    ]

    work_df = work_df[
        work_df["los_hours"] <= max_los_hours
    ]

    work_df = work_df[
        work_df["los_hours"] > 0
    ]

    work_df["arrival_type"] = (
        work_df["arrival_method"]
        .apply(_map_arrival_method)
    )

    arrival_order = [
        "Ambulance",
        "Car / Walk-in",
        "Wheelchair",
        "Police",
        "Other"
    ]

    summary_rows = []

    for arrival in arrival_order:

        for esi in [1, 2, 3, 4, 5]:

            subset = work_df[
                (work_df["arrival_type"] == arrival)
                &
                (work_df["esi"] == esi)
            ]

            count = len(subset)

            if count == 0:

                stats = {
                    "mean_los": 0,
                    "median_los": 0,
                    "p25_los": 0,
                    "p75_los": 0,
                    "p90_los": 0,
                    "max_los": 0
                }

            else:

                vals = subset["los_hours"]

                stats = {
                    "mean_los": vals.mean(),
                    "median_los": vals.median(),
                    "p25_los": np.percentile(vals, 25),
                    "p75_los": np.percentile(vals, 75),
                    "p90_los": np.percentile(vals, 90),
                    "max_los": vals.max()
                }

            contribution = (
                count *
                stats["mean_los"]
            )

            summary_rows.append(
                {
                    "arrival_type": arrival,
                    "esi": esi,
                    "count": count,
                    **stats,
                    "census_contribution":
                        contribution
                }
            )

    summary_df = pd.DataFrame(summary_rows)

    # ==========================================================
    # KPI METRICS
    # ==========================================================

    overall_mean_los = (
        work_df["los_hours"].mean()
        if len(work_df)
        else 0
    )

    overall_median_los = (
        work_df["los_hours"].median()
        if len(work_df)
        else 0
    )

    overall_contribution = (
        summary_df[
            "census_contribution"
        ].sum()
    )

    highest_los_category = (
        summary_df.sort_values(
            "mean_los",
            ascending=False
        )
        .iloc[0]
    )

    highest_median_category = (
        summary_df.sort_values(
            "median_los",
            ascending=False
        )
        .iloc[0]
    )

    highest_census_category = (
        summary_df.sort_values(
            "census_contribution",
            ascending=False
        )
        .iloc[0]
    )

    # ==========================================================
    # MAIN FIGURE
    # ==========================================================

    fig, ax = plt.subplots(
        figsize=(fig_width, fig_height),
        dpi=dpi
    )

    esi_values = [1, 2, 3, 4, 5]
    width = 0.15

    if display_mode == "median_bar":

        offsets = np.linspace(
            -0.30,
            0.30,
            len(arrival_order)
        )

        for idx, arrival in enumerate(arrival_order):

            medians = []

            for esi in esi_values:

                row = summary_df[
                    (summary_df["arrival_type"] == arrival)
                    &
                    (summary_df["esi"] == esi)
                ].iloc[0]

                medians.append(
                    row["median_los"]
                )

            bars = ax.bar(
                np.array(esi_values) + offsets[idx],
                medians,
                width=width,
                color=colors[arrival],
                label=arrival
            )

            if show_data_labels:

                for bar in bars:
                    ax.text(
                        bar.get_x()
                        +
                        bar.get_width()/2,
                        bar.get_height(),
                        f"{bar.get_height():.1f}",
                        ha="center",
                        fontsize=8
                    )

    else:

        positions = []
        data_list = []
        colors_used = []

        base = np.arange(1, 6)

        offsets = np.linspace(
            -0.30,
            0.30,
            len(arrival_order)
        )

        for idx, arrival in enumerate(arrival_order):

            for esi in esi_values:

                vals = work_df.loc[
                    (
                        work_df["arrival_type"]
                        == arrival
                    )
                    &
                    (
                        work_df["esi"]
                        == esi
                    ),
                    "los_hours"
                ]

                positions.append(
                    esi + offsets[idx]
                )

                data_list.append(
                    vals.tolist()
                    if len(vals)
                    else [0]
                )

                colors_used.append(
                    colors[arrival]
                )

        bp = ax.boxplot(
            data_list,
            positions=positions,
            widths=0.10,
            patch_artist=True,
            showfliers=bool(show_outliers)
        )

        for patch, color in zip(
            bp["boxes"],
            colors_used
        ):
            patch.set_facecolor(color)

    ax.set_xticks([1, 2, 3, 4, 5])

    ax.set_xticklabels(
        [
            "ESI 1",
            "ESI 2",
            "ESI 3",
            "ESI 4",
            "ESI 5"
        ]
    )

    ax.set_ylabel(
        "LOS (Hours)"
    )

    ax.set_title(
        "LOS by Arrival Method and ESI\n"
        + format_date_range(
            start_date,
            end_date
        )
    )

    annotation = (
        f"Highest LOS: "
        f"{highest_los_category['arrival_type']} "
        f"ESI {highest_los_category['esi']}\n"
        f"Highest Census: "
        f"{highest_census_category['arrival_type']} "
        f"ESI {highest_census_category['esi']}"
    )

    ax.text(
        0.01,
        0.99,
        annotation,
        transform=ax.transAxes,
        va="top",
        fontsize=9
    )

    plt.tight_layout()

    output_file = os.path.join(
        output_dir,
        generate_output_name(
            visual_id=VISUAL_ID,
            start_date=start_date,
            end_date=end_date,
            cohort_id=params.get(
                "cohort_id"
            ),
            ext="png"
        )
    )

    plt.savefig(
        output_file,
        dpi=dpi,
        bbox_inches="tight"
    )

    plt.close()

    # ==========================================================
    # SUMMARY TABLE PNG
    # ==========================================================

    table_df = (
        summary_df.sort_values(
            "census_contribution",
            ascending=False
        )
        [
            [
                "arrival_type",
                "esi",
                "count",
                "mean_los",
                "median_los",
                "census_contribution"
            ]
        ]
    )

    table_fig, table_ax = plt.subplots(
        figsize=(12, 8)
    )

    table_ax.axis("off")

    table_display = table_df.copy()

    table_display["count"] = (
        table_display["count"]
        .astype(int)
        .map("{:,}".format)
    )

    for col in [
        "mean_los",
        "median_los",
        "census_contribution"
    ]:
        table_display[col] = (
            table_display[col]
            .astype(float)
            .round(2)
        )

    table = table_ax.table(
        cellText=table_display.values,
        colLabels=table_display.columns,
        loc="center"
    )
    table.auto_set_font_size(False)
    table.set_fontsize(table_fontsize)
    table.scale(1.0, 1.3)

    summary_output = output_file.replace(
        ".png",
        "_summary.png"
    )

    plt.savefig(
        summary_output,
        bbox_inches="tight"
    )

    plt.close()

    # ==========================================================
    # PARAMETER PNG
    # ==========================================================

    try:

        display_params = (
            get_display_parameters(params)
        )

        if display_params:

            save_parameter_table_png(
                display_params,
                output_file.replace(
                    ".png",
                    "_params.png"
                )
            )

    except Exception as ex:

        logger.warning(
            f"[{VISUAL_ID}] "
            f"parameter export failed: {ex}"
        )

    # ==========================================================
    # LEGEND
    # ==========================================================

    try:

        handles = [
            Patch(
                facecolor=colors[arrival],
                label=arrival
            )
            for arrival in arrival_order
        ]

        labels = arrival_order

        legend_output = output_file.replace(
            ".png",
            "_legend.png"
        )

        save_legend_png(
            handles=handles,
            labels=labels,
            output_file=legend_output,
            ncol=len(arrival_order)
        )

    except Exception as ex:

        logger.warning(
            f"[{VISUAL_ID}] "
            f"Legend generation failed: {ex}"
        )

    # ==========================================================
    # RDB
    # ==========================================================

    write_rdb = int(
        params.get(
            "write_rdb",
            0
        )
    )

    rdb_rows = []

    if write_rdb == 1:

        report_title = (
            "LOS by Arrival Method and ESI"
        )

        for _, row in summary_df.iterrows():

            metrics = {
                "encounter_count":
                    row["count"],
                "mean_los_hours":
                    row["mean_los"],
                "median_los_hours":
                    row["median_los"],
                "p25_los_hours":
                    row["p25_los"],
                "p75_los_hours":
                    row["p75_los"],
                "p90_los_hours":
                    row["p90_los"],
                "max_los_hours":
                    row["max_los"],
                "census_contribution":
                    row["census_contribution"]
            }

            for metric_name, metric_value in metrics.items():

                rdb_rows.append({

                    "run_id":
                        params.get("run_id"),

                    "visual_id":
                        VISUAL_ID,

                    "client_name":
                        params.get("client_name"),

                    "domain":
                        params.get("domain"),

                    "cohort_id":
                        params.get("cohort_id"),

                    "domain_cohort":
                        f"{params.get('domain')}."
                        f"{params.get('cohort_id')}",

                    "dimension":
                        "arrival_type",

                    "dimension_value":
                        row["arrival_type"],

                    "dimension_value_label":
                        row["arrival_type"],

                    "secondary_dimension":
                        "esi",

                    "secondary_dimension_value":
                        f"ESI {row['esi']}",

                    "metric":
                        metric_name,

                    "metric_type":
                        "value",

                    "value":
                        float(metric_value),

                    "start_date":
                        start_date,

                    "end_date":
                        end_date,

                    "report_title":
                        report_title
                })

        overall_metrics = {
            "overall_mean_los":
                overall_mean_los,
            "overall_median_los":
                overall_median_los,
            "overall_census_contribution":
                overall_contribution
        }

        for metric_name, metric_value in overall_metrics.items():

            rdb_rows.append({

                "run_id":
                    params.get("run_id"),

                "visual_id":
                    VISUAL_ID,

                "client_name":
                    params.get("client_name"),

                "domain":
                    params.get("domain"),

                "cohort_id":
                    params.get("cohort_id"),

                "domain_cohort":
                    f"{params.get('domain')}."
                    f"{params.get('cohort_id')}",

                "dimension":
                    "arrival_type",

                "dimension_value":
                    "Overall",

                "dimension_value_label":
                    "Overall",

                "secondary_dimension":
                    None,

                "secondary_dimension_value":
                    None,

                "metric":
                    metric_name,

                "metric_type":
                    "value",

                "value":
                    float(metric_value),

                "start_date":
                    start_date,

                "end_date":
                    end_date,

                "report_title":
                    report_title
            })

        for metric_name, metric_value in {
            "highest_los_category":
                f"{highest_los_category['arrival_type']}|ESI {highest_los_category['esi']}",
            "highest_median_los_category":
                f"{highest_median_category['arrival_type']}|ESI {highest_median_category['esi']}",
            "highest_census_category":
                f"{highest_census_category['arrival_type']}|ESI {highest_census_category['esi']}"
        }.items():

            rdb_rows.append({
                "run_id": params.get("run_id"),
                "visual_id": VISUAL_ID,
                "client_name": params.get("client_name"),
                "domain": params.get("domain"),
                "cohort_id": params.get("cohort_id"),
                "domain_cohort":
                    f"{params.get('domain')}.{params.get('cohort_id')}",
                "dimension": "arrival_type",
                "dimension_value": "Overall",
                "dimension_value_label": "Overall",
                "secondary_dimension": None,
                "secondary_dimension_value": None,
                "metric": metric_name,
                "metric_type": "value",
                "value": metric_value,
                "start_date": start_date,
                "end_date": end_date,
                "report_title": report_title
            })

    logger.info(f"[{VISUAL_ID}] Complete")

    return {
        "output_path": output_file,
        "rdb": rdb_rows
    }