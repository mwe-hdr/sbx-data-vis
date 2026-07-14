## =============================================================================
##
## Domain      : ED (Emergency Department)
##
## Report Name : Arrival Method vs ESI Heatmap
##
## Description :
##
## Generates a heatmap showing Emergency Department encounters by
## Arrival Method and Emergency Severity Index (ESI).
##
## Raw arrival methods are standardized into operational categories:
##
## - Ambulance
## - Car / Walk-in
## - Wheelchair
## - Other
##
## Encounters are cross-tabulated against ESI levels 1-5.
##
## Cell values display the percent distribution within arrival method.
##
## Outputs:
##
## - PNG heatmap
## - RDB records containing:
##   * Total encounters
##   * Encounter counts by arrival type and ESI
##   * Percent within arrival type
##   * Percent of total encounters
##
## =============================================================================

import os
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from utils.vis_helpers import (
    normalize_params,
    format_date_range,
    save_legend_png,
    get_display_parameters,
    save_parameter_table_png
)

VISUAL_ID = "vis_13"

logger = logging.getLogger(__name__)


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

    logger.info("[vis_13] Starting execution")

    params = normalize_params(params)

    fig_width = float(
        params.get("fig_width", 10)
    )

    fig_height = float(
        params.get("fig_height", 4)
    )

    dpi = int(
        float(params.get("dpi", 300))
    )

    required_cols = ["arrival_method", "esi"]

    missing_cols = [c for c in required_cols if c not in df.columns]

    if missing_cols:
        raise ValueError(
            f"{VISUAL_ID}: Missing required columns: {missing_cols}"
        )

    work_df = df.copy()

    work_df["esi"] = pd.to_numeric(
        work_df["esi"],
        errors="coerce"
    )

    work_df = work_df[
        work_df["esi"].isin([1, 2, 3, 4, 5])
    ]

    work_df["arrival_group"] = (
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

    esi_order = [1, 2, 3, 4, 5]

    counts = pd.crosstab(
        work_df["arrival_group"],
        work_df["esi"]
    )

    counts = counts.reindex(
        index=arrival_order,
        columns=esi_order,
        fill_value=0
    )

    row_pct = (
        counts.div(
            counts.sum(axis=1).replace(0, np.nan),
            axis=0
        )
        .fillna(0)
        * 100
    )

    # ------------------------------------------------------------------
    # Heatmap
    # ------------------------------------------------------------------

    fig, ax = plt.subplots(
        figsize=(fig_width, fig_height)
    )

    img = ax.imshow(
        row_pct.values,
        cmap="Blues",
        aspect="auto"
    )

    ax.set_xticks(range(len(esi_order)))
    ax.set_xticklabels([f"ESI {e}" for e in esi_order])

    ax.set_yticks(range(len(arrival_order)))
    ax.set_yticklabels(arrival_order)

    ax.set_title(
        "Arrival Method vs ESI Distribution\n"
        + format_date_range(start_date, end_date)
    )

    for r in range(len(arrival_order)):
        for c in range(len(esi_order)):

            pct = row_pct.iloc[r, c]
            cnt = counts.iloc[r, c]

            ax.text(
                c,
                r,
                f"{pct:.1f}%\n(n={cnt})",
                ha="center",
                va="center",
                fontsize=8
            )

    cbar = plt.colorbar(
        img,
        ax=ax
    )

    cbar.set_label("% Within Arrival Type")

    plt.tight_layout()

    output_name = generate_output_name(
        visual_id=VISUAL_ID,
        start_date=start_date,
        end_date=end_date,
        ext="png"
    )

    png_path = os.path.join(
        output_dir,
        output_name
    )

    plt.savefig(
        png_path,
        dpi=dpi,
        bbox_inches="tight"
    )

    plt.close()

    # ------------------------------------------------------------------
    # Parameter image
    # ------------------------------------------------------------------

    try:
        display_params = get_display_parameters(params)

        if display_params:
            save_parameter_table_png(
                display_params,
                png_path.replace(".png", "_params.png")
            )
    except Exception as ex:
        logger.warning(
            f"[vis_13] Parameter export failed: {ex}"
        )

    # ------------------------------------------------------------------
    # RDB Output
    # ------------------------------------------------------------------

    total_encounters = len(work_df)

    write_rdb = int(params.get("write_rdb", 0))

    rdb_rows = []

    if write_rdb == 1:

        rdb_rows.append({
            "visual_id": VISUAL_ID,
            "metric": "total_encounters",
            "value": total_encounters
        })

        for arrival in arrival_order:

            arrival_total = counts.loc[arrival].sum()

            for esi in esi_order:

                count = int(
                    counts.loc[arrival, esi]
                )

                pct_arrival = float(
                    row_pct.loc[arrival, esi]
                )

                pct_total = (
                    count / total_encounters * 100
                    if total_encounters
                    else 0
                )

                rdb_rows.append({
                    "run_id": params.get("run_id"),
                    "client_name": params.get("client_name"),
                    "domain": params.get("domain"),
                    "cohort_id": params.get("cohort_id"),
                    "visual_id": VISUAL_ID,
                    "arrival_type": arrival,
                    "esi": esi,
                    "arrival_total": int(arrival_total),
                    "encounter_count": count,
                    "pct_within_arrival_type": round(
                        pct_arrival,
                        2
                    ),
                    "pct_of_total": round(
                        pct_total,
                        2
                    )
                })

    logger.info("[vis_13] Complete")

    return {
        "output_path": png_path,
        "rdb": rdb_rows
    }