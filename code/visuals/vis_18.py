## =============================================================================
##
## Domain      : ED (Emergency Department)
##
## Report Name : Ambulatory Arrival Disposition by ESI
##
## Description :
##
## Evaluates disposition outcomes across ESI levels for ambulatory
## Emergency Department patients.
##
## Arrival methods are standardized using the same arrival grouping
## logic implemented in vis_13.
##
## Dispositions are normalized into operational categories:
##
## - Discharge
## - Admit
## - Observation
## - Transfer
## - Left Without Being Seen
## - Left Against Medical Advice
## - Expired
## - Other
##
## Generates:
##
## - 100% stacked disposition distribution by ESI
## - Summary metrics panel
## - Parameter image
## - Legend image
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
    save_legend_png,
    get_display_parameters,
    save_parameter_table_png
)

VISUAL_ID = "vis_18"

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


def _map_disposition(value):

    if pd.isna(value):
        return "Other"

    txt = str(value).strip().lower()

    if (
        "observation" in txt
        or txt.startswith("obs")
    ):
        return "Observation"

    if (
        "admit" in txt
        or "inpatient" in txt
    ):
        return "Admit"

    if (
        "transfer" in txt
    ):
        return "Transfer"

    if (
        "lwbs" in txt
        or "left without being seen" in txt
        or "left before triage" in txt
    ):
        return "Left Without Being Seen"

    if (
        "against medical advice" in txt
        or txt == "ama"
    ):
        return "Left Against Medical Advice"

    if (
        "expired" in txt
        or "death" in txt
        or "deceased" in txt
    ):
        return "Expired"

    if (
        "discharge" in txt
        or "home" in txt
    ):
        return "Discharge"

    return "Other"


def run(
    df,
    params,
    start_date,
    end_date,
    output_dir,
    generate_output_name
):

    logger.info("[vis_18] Starting execution")

    params = normalize_params(params)

    fig_width = float(params.get("fig_width", 12))
    fig_height = float(params.get("fig_height", 7))
    dpi = int(float(params.get("dpi", 300)))

    required_cols = [
        "arrival_method",
        "esi",
        "disch_disp_desc"
    ]

    missing_cols = [
        c
        for c in required_cols
        if c not in df.columns
    ]

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

    selected_arrivals = [
        x.strip()
        for x in str(
            params.get(
                "arrival_groups",
                "Ambulance"
            )
        ).split("|")
        if x.strip()
    ]

    work_df = work_df[
        work_df["arrival_group"].isin(
            selected_arrivals
        )
    ]

    work_df["disposition_group"] = (
        work_df["disch_disp_desc"]
        .apply(_map_disposition)
    )

    total_encounters = len(work_df)

    esi_order = [1, 2, 3, 4, 5]

    disp_order = [
        "Discharge",
        "Admit",
        "Observation",
        "Transfer",
        "Left Without Being Seen",
        "Left Against Medical Advice",
        "Expired",
        "Other"
    ]

    counts = pd.crosstab(
        work_df["esi"],
        work_df["disposition_group"]
    )

    counts = counts.reindex(
        index=esi_order,
        columns=disp_order,
        fill_value=0
    )

    row_pct = (
        counts.div(
            counts.sum(axis=1).replace(
                0,
                np.nan
            ),
            axis=0
        )
        .fillna(0)
        * 100
    )

    colors = [
        params.get("discharge_color", "#4E79A7"),
        params.get("admit_color", "#E15759"),
        params.get("observation_color", "#F28E2B"),
        params.get("transfer_color", "#76B7B2"),
        params.get("lwbs_color", "#59A14F"),
        params.get("ama_color", "#EDC948"),
        params.get("expired_color", "#AF7AA1"),
        params.get("other_color", "#BAB0AC")
    ]

    show_labels = int(
        params.get(
            "show_bar_labels",
            1
        )
    )

    show_chart_legend = int(
        params.get(
            "show_chart_legend",
            1
        )
    )

    fig, ax = plt.subplots(
        figsize=(fig_width, fig_height)
    )

    bottom = np.zeros(len(esi_order))

    for idx, disp in enumerate(disp_order):

        values = row_pct[disp].values

        bars = ax.bar(
            [f"ESI {x}" for x in esi_order],
            values,
            bottom=bottom,
            label=disp,
            color=colors[idx]
        )

        if show_labels == 1:

            for bar, val in zip(
                bars,
                values
            ):
                if val >= 4:

                    ax.text(
                        bar.get_x() + bar.get_width()/2,
                        bar.get_y() + bar.get_height()/2,
                        f"{val:.0f}%",
                        ha="center",
                        va="center",
                        fontsize=7
                    )

        bottom += values

    ax.set_ylim(0, 100)

    ax.set_ylabel(
        "Percent of Encounters"
    )

    arrival_display = ", ".join(selected_arrivals)

    ax.set_title(
        "Ambulatory Arrival Disposition by ESI\n"
        + format_date_range(start_date, end_date)
        + f"  |  n = {total_encounters:,} encounters"
    )

    if show_chart_legend == 1:

        ax.legend(
            loc="upper left",
            bbox_to_anchor=(1.02, 1)
        )

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

    total_encounters = len(work_df)

    admit_rate_overall = (
        (work_df["disposition_group"] == "Admit")
        .mean()
    )

    obs_rate_overall = (
        (work_df["disposition_group"] == "Observation")
        .mean()
    )

    discharge_rate_overall = (
        (work_df["disposition_group"] == "Discharge")
        .mean()
    )

    admission_rates = (
        row_pct["Admit"] / 100
    )

    observation_rates = (
        row_pct["Observation"] / 100
    )

    highest_admission_esi = (
        admission_rates.idxmax()
    )

    highest_observation_esi = (
        observation_rates.idxmax()
    )

    esi4_threshold = float(
        params.get(
            "esi4_admit_alert_threshold",
            0.10
        )
    )

    esi5_threshold = float(
        params.get(
            "esi5_admit_alert_threshold",
            0.05
        )
    )

    summary_df = pd.DataFrame({
        "Metric": [
            "Overall Admission Rate",
            "Overall Observation Rate",
            "Overall Discharge Rate",
            "Highest Admission ESI",
            "Highest Observation ESI",
            "ESI 4 Admission Alert",
            "ESI 5 Admission Alert"
        ],
        "Value": [
            f"{admit_rate_overall:.1%}",
            f"{obs_rate_overall:.1%}",
            f"{discharge_rate_overall:.1%}",
            f"ESI {highest_admission_esi}",
            f"ESI {highest_observation_esi}",
            (
                "YES"
                if admission_rates.get(4,0)
                > esi4_threshold
                else "NO"
            ),
            (
                "YES"
                if admission_rates.get(5,0)
                > esi5_threshold
                else "NO"
            )
        ]
    })

    summary_path = png_path.replace(
        ".png",
        "_summary.png"
    )

    save_parameter_table_png(
        summary_df,
        summary_path
    )


    legend_handles = [
        Patch(
            color=colors[i],
            label=disp_order[i]
        )
        for i in range(len(disp_order))
    ]
    
    legend_labels = disp_order.copy()

    try:
        save_legend_png(
            legend_handles,
            legend_labels,
            png_path.replace(
                ".png",
                "_legend.png"
            ),
            ncol=4
        )
        
    except Exception as ex:
        logger.warning(
            f"[vis_18] Legend export failed: {ex}"
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
                png_path.replace(
                    ".png",
                    "_params.png"
                )
            )

    except Exception as ex:

        logger.warning(
            f"[vis_18] Parameter export failed: {ex}"
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
            "visual_id": VISUAL_ID,
            "metric": "total_encounters",
            "value": total_encounters
        })

        for esi in esi_order:

            row_total = counts.loc[
                esi
            ].sum()

            for disp in disp_order:

                count = int(
                    counts.loc[
                        esi,
                        disp
                    ]
                )

                pct = float(
                    row_pct.loc[
                        esi,
                        disp
                    ]
                )

                rdb_rows.append({

                    "run_id": params.get("run_id"),
                    "client_name": params.get("client_name"),
                    "domain": params.get("domain"),
                    "cohort_id": params.get("cohort_id"),
                    "domain_cohort": params.get("domain_cohort"),
                    "start_date": start_date,
                    "end_date": end_date,
                    "report_title":
                        "Ambulatory Arrival Disposition by ESI",
                    "visual_id": VISUAL_ID,
                    "dimension": "esi",
                    "secondary_dimension":
                        "disposition",
                    "esi": esi,
                    "disposition": disp,
                    "esi_total": int(row_total),
                    "encounter_count": count,
                    "percent_within_esi":
                        round(pct, 2)
                })

            rdb_rows.append({
                "run_id": params.get("run_id"),
                "client_name": params.get("client_name"),
                "domain": params.get("domain"),
                "cohort_id": params.get("cohort_id"),
                "visual_id": VISUAL_ID,
                "esi": esi,
                "admission_rate":
                    round(
                        row_pct.loc[esi,"Admit"],
                        2
                    ),
                "observation_rate":
                    round(
                        row_pct.loc[esi,"Observation"],
                        2
                    ),
                "discharge_rate":
                    round(
                        row_pct.loc[esi,"Discharge"],
                        2
                    )
            })

        rdb_rows.append({
            "run_id": params.get("run_id"),
            "client_name": params.get("client_name"),
            "visual_id": VISUAL_ID,
            "metric": "total_admissions",
            "value": int(
                (
                    work_df["disposition_group"]
                    == "Admit"
                ).sum()
            )
        })

        rdb_rows.append({
            "run_id": params.get("run_id"),
            "client_name": params.get("client_name"),
            "visual_id": VISUAL_ID,
            "metric": "total_observations",
            "value": int(
                (
                    work_df["disposition_group"]
                    == "Observation"
                ).sum()
            )
        })

        rdb_rows.append({
            "run_id": params.get("run_id"),
            "client_name": params.get("client_name"),
            "visual_id": VISUAL_ID,
            "metric": "total_discharges",
            "value": int(
                (
                    work_df["disposition_group"]
                    == "Discharge"
                ).sum()
            )
        })

    logger.info("[vis_18] Complete")

    return {
        "output_path": png_path,
        "rdb": rdb_rows
    }