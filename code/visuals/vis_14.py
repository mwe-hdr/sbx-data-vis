import os
import math
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from utils.vis_helpers import (
    normalize_params,
    format_date_range,
    get_display_parameters,
    save_parameter_table_png
)

VISUAL_ID = "vis_14"
logger = logging.getLogger(__name__)


def _safe_param(params, key, default, cast_type=None):
    try:
        value = params.get(key, default)
        return cast_type(value) if cast_type else value
    except Exception:
        return default


def _generate_hourly_census(df, start_date, end_date):
    """
    Consistent with vis_10 / vis_11 approach:
    generate hourly census from encounter windows.
    """

    if df.empty:
        return pd.DataFrame(columns=["timestamp", "census"])

    work = df.copy()

    work["ed_start_dtm"] = pd.to_datetime(
        work["ed_start_dtm"],
        errors="coerce"
    )

    work["ed_stop_dtm"] = pd.to_datetime(
        work["ed_stop_dtm"],
        errors="coerce"
    )

    work = work.dropna(
        subset=["ed_start_dtm", "ed_stop_dtm"]
    )

    if work.empty:
        return pd.DataFrame(columns=["timestamp", "census"])

    start_ts = pd.to_datetime(start_date)
    end_ts = pd.to_datetime(end_date)

    rng = pd.date_range(
        start=start_ts.floor("h"),
        end=end_ts.ceil("h"),
        freq="h"
    )

    census_values = []

    for ts in rng:
        census = (
            (
                (work["ed_start_dtm"] <= ts)
                &
                (work["ed_stop_dtm"] > ts)
            )
        ).sum()

        census_values.append(census)

    return pd.DataFrame({
        "timestamp": rng,
        "census": census_values
    })


def run(
    df,
    params,
    start_date,
    end_date,
    output_dir,
    generate_output_name
):
    logger.info("[vis_14] Starting run")

    params = normalize_params(params)

    fig_width = _safe_param(params, "fig_width", 12, float)
    fig_height = _safe_param(params, "fig_height", 7, float)
    dpi = _safe_param(params, "dpi", 300, int)

    utilization = _safe_param(
        params,
        "utilization",
        0.85,
        float
    )

    baseline_color = params.get(
        "baseline_color",
        "#4E79A7"
    )

    scenario_color = params.get(
        "scenario_color",
        "#F28E2B"
    )

    required = [
        "esi",
        "ed_start_dtm",
        "ed_stop_dtm"
    ]

    missing = [
        c for c in required
        if c not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    work = df.copy()

    work["esi"] = pd.to_numeric(
        work["esi"],
        errors="coerce"
    )

    work["ed_start_dtm"] = pd.to_datetime(
        work["ed_start_dtm"],
        errors="coerce"
    )

    work["ed_stop_dtm"] = pd.to_datetime(
        work["ed_stop_dtm"],
        errors="coerce"
    )

    work = work.dropna(
        subset=[
            "esi",
            "ed_start_dtm",
            "ed_stop_dtm"
        ]
    )

    los_hours = (
        work["ed_stop_dtm"] -
        work["ed_start_dtm"]
    ).dt.total_seconds() / 3600.0

    work["los_hours"] = los_hours

    work = work[
        (work["los_hours"] >= 0)
    ]

    esi_levels = [1, 2, 3, 4, 5]

    rows = []

    for esi in esi_levels:

        subset = work[
            work["esi"] == esi
        ]

        volume = len(subset)

        avg_los = (
            subset["los_hours"].mean()
            if volume > 0
            else 0
        )

        baseline_census = (
            volume * avg_los
        )

        multiplier = _safe_param(
            params,
            f"esi{esi}_multiplier",
            1.0,
            float
        )

        scenario_volume = (
            volume * multiplier
        )

        scenario_census = (
            scenario_volume * avg_los
        )

        rows.append({
            "esi": f"ESI {esi}",
            "baseline_volume": volume,
            "baseline_los": avg_los,
            "baseline_census": baseline_census,
            "multiplier": multiplier,
            "scenario_volume": scenario_volume,
            "scenario_census": scenario_census
        })

    metrics = pd.DataFrame(rows)

    current_total_census = metrics[
        "baseline_census"
    ].sum()

    scenario_total_census = metrics[
        "scenario_census"
    ].sum()

    scale_factor = (
        scenario_total_census / current_total_census
        if current_total_census > 0
        else 1.0
    )

    census_df = _generate_hourly_census(
        work,
        start_date,
        end_date
    )

    if census_df.empty:
        current_peak_census = 0
        current_avg_census = 0
    else:
        current_peak_census = (
            census_df["census"].max()
        )

        current_avg_census = (
            census_df["census"].mean()
        )

    scenario_peak_census = (
        current_peak_census * scale_factor
    )

    scenario_avg_census = (
        current_avg_census * scale_factor
    )

    current_room_need = (
        math.ceil(
            current_peak_census / utilization
        )
        if utilization > 0
        else 0
    )

    scenario_room_need = (
        math.ceil(
            scenario_peak_census / utilization
        )
        if utilization > 0
        else 0
    )

    fig, ax = plt.subplots(
        figsize=(fig_width, fig_height)
    )

    x = np.arange(len(metrics))

    width = 0.40

    bars1 = ax.bar(
        x - width / 2,
        metrics["baseline_census"],
        width,
        label="Current Census Contribution",
        color=baseline_color
    )

    bars2 = ax.bar(
        x + width / 2,
        metrics["scenario_census"],
        width,
        label="Scenario Census Contribution",
        color=scenario_color
    )

    for bars in [bars1, bars2]:
        for b in bars:
            h = b.get_height()

            ax.text(
                b.get_x() + b.get_width()/2,
                h,
                f"{h:,.1f}",
                ha="center",
                va="bottom",
                fontsize=8
            )

    ax.set_xticks(x)
    ax.set_xticklabels(metrics["esi"])

    ax.set_ylabel("Census Contribution")
    ax.set_title(
        "ESI Mix Scenario Simulator\n"
        + format_date_range(
            start_date,
            end_date
        )
    )

    ax.legend()

    summary_text = (
        f"Current Total Census: {current_total_census:,.1f}\n"
        f"Scenario Total Census: {scenario_total_census:,.1f}\n\n"
        f"Current Peak Census: {current_peak_census:,.1f}\n"
        f"Scenario Peak Census: {scenario_peak_census:,.1f}\n\n"
        f"Current Room Need: {current_room_need:,.0f}\n"
        f"Scenario Room Need: {scenario_room_need:,.0f}"
    )

    ax.text(
        1.02,
        0.98,
        summary_text,
        transform=ax.transAxes,
        va="top",
        bbox=dict(
            facecolor="white",
            alpha=0.9
        )
    )

    plt.tight_layout()

    output_file = os.path.join(
        output_dir,
        generate_output_name(VISUAL_ID, "png")
    )

    plt.savefig(
        output_file,
        dpi=dpi,
        bbox_inches="tight"
    )

    plt.close()

    display_params = get_display_parameters(params)

    if display_params:
        try:
            save_parameter_table_png(
                display_params,
                output_dir,
                generate_output_name
            )
        except Exception:
            pass

    rdb_rows = []

    common = {
        "visual_id": VISUAL_ID,
        "report_title": "ESI Mix Scenario Simulator",
        "start_date": str(start_date),
        "end_date": str(end_date),
        "client_name": params.get(
            "client_name",
            ""
        ),
        "domain": params.get(
            "domain",
            "ed"
        ),
        "cohort_id": params.get(
            "cohort_id",
            ""
        ),
        "run_id": params.get(
            "run_id",
            ""
        )
    }

    for _, row in metrics.iterrows():

        rdb_rows.append({
            **common,
            "metric_type": "baseline",
            "esi": row["esi"],
            "baseline_volume": row["baseline_volume"],
            "baseline_los": row["baseline_los"],
            "baseline_census": row["baseline_census"]
        })

        rdb_rows.append({
            **common,
            "metric_type": "scenario",
            "esi": row["esi"],
            "scenario_volume": row["scenario_volume"],
            "scenario_census": row["scenario_census"]
        })

    rdb_rows.append({
        **common,
        "metric_type": "summary",
        "current_total_census": current_total_census,
        "scenario_total_census": scenario_total_census,
        "current_peak_census": current_peak_census,
        "scenario_peak_census": scenario_peak_census,
        "current_room_need": current_room_need,
        "scenario_room_need": scenario_room_need
    })

    return {
        "output_path": output_file,
        "rdb": rdb_rows
    }