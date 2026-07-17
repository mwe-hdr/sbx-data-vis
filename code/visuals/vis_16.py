# =============================================================================
# Domain      : ED (Emergency Department)
#
# Report Name : Low-Acuity Ambulatory Patient Origin Map
#
# Description :
#
# Identifies geographic origin patterns for ambulatory low-acuity ED visits.
#
# Population:
#   - Car / Walk-in encounters
#   - ESI 4
#   - ESI 5
#
# Encounters are aggregated by patient ZIP code and joined to
# ZIP Code Tabulation Areas (ZCTAs).
#
# Produces:
#   - Choropleth map
#   - Top ZIP summary table image
#   - Parameter image
#   - Optional RDB outputs
#
# =============================================================================

import os
import logging

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import mapclassify

from utils.vis_helpers import (
    normalize_params,
    format_date_range,
    get_display_parameters,
    save_parameter_table_png
)

VISUAL_ID = "vis_16"

logger = logging.getLogger(__name__)


# ============================================================================
# Arrival Method Mapping
# Mirrors vis_13 implementation
# ============================================================================

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

    logger.info("[vis_16] Starting execution")

    # ======================================================================
    # Parameters
    # ======================================================================

    params = normalize_params(params)

    fig_width = float(params.get("fig_width", 16))
    fig_height = float(params.get("fig_height", 5))
    dpi = int(float(params.get("dpi", 600)))
    font_family = str(
        params.get("font_family", "Segoe UI")
    ).strip()
    zcta_file = params.get("zcta_file")
    county_file = params.get("county_file")

    classification_method = str(
        params.get("classification_method", "quantiles")
    ).lower()

    num_classes = int(
        float(params.get("num_classes", 5))
    )

    cmap = params.get("cmap", "YlOrRd")

    label_top_n_zips = int(
        float(params.get("label_top_n_zips", 10))
    )

    zip_label_fontsize = int(
        float(params.get("zip_label_fontsize", 6))
    )

    county_label_fontsize = int(
        float(params.get("county_label_fontsize", 6))
    )

    county_label_color = (
        params.get("county_label_color", "#444444")
    )

    county_label_weight = (
        params.get("county_label_weight", "bold")
    )

    low_acuity_esi_values = (
        params.get("low_acuity_esi_values", "4;5")
    )

    low_acuity_esi_values = [
        int(x.strip())
        for x in str(low_acuity_esi_values).split(";")
        if str(x).strip()
    ]

    focus_county_geoids = (
        params.get("focus_county_geoids")
    )

    if focus_county_geoids:
        focus_county_geoids = [
            x.strip()
            for x in str(focus_county_geoids).split(";")
            if x.strip()
        ]
    else:
        focus_county_geoids = []

    write_rdb = int(
        float(params.get("write_rdb", 0))
    )

    # ======================================================================
    # Required Columns
    # ======================================================================

    required_cols = [
        "patient_zipcode",
        "arrival_method",
        "esi"
    ]

    missing = [
        c for c in required_cols
        if c not in df.columns
    ]

    if missing:
        raise ValueError(
            f"{VISUAL_ID}: Missing required columns {missing}"
        )

    # ======================================================================
    # Filter Population
    # ======================================================================

    work_df = df.copy()

    work_df["arrival_group"] = (
        work_df["arrival_method"]
        .apply(_map_arrival_method)
    )

    work_df["esi"] = pd.to_numeric(
        work_df["esi"],
        errors="coerce"
    )

    work_df["patient_zipcode"] = (
        work_df["patient_zipcode"]
        .astype(str)
        .str.strip()
        .str.zfill(5)
    )

    work_df = work_df[
        work_df["arrival_group"] == "Ambulance"
    ]

    work_df = work_df[
        work_df["esi"].isin(low_acuity_esi_values)
    ]

    work_df = work_df[
        work_df["patient_zipcode"].notna()
    ]

    if work_df.empty:
        logger.warning(
            "[vis_16] No qualifying encounters"
        )
        return

    # ======================================================================
    # Aggregate ZIP Volumes
    # ======================================================================

    visits = (
        work_df
        .groupby("patient_zipcode")
        .size()
        .reset_index(name="encounter_count")
        .sort_values(
            "encounter_count",
            ascending=False
        )
    )

    total_visits = int(
        visits["encounter_count"].sum()
    )

    visits["pct_of_total"] = (
        visits["encounter_count"]
        / total_visits
        * 100
    )

    visits["ranking"] = (
        np.arange(len(visits))
        + 1
    )

    # ======================================================================
    # Load Geography
    # ======================================================================

    if not os.path.isabs(zcta_file):
        zcta_file = os.path.join(
            os.getcwd(),
            zcta_file
        )

    zcta = gpd.read_file(zcta_file)

    candidate_cols = [
        "ZCTA5CE20",
        "ZCTA5CE10",
        "GEOID20",
        "GEOID10"
    ]

    zip_col = None

    for c in candidate_cols:
        if c in zcta.columns:
            zip_col = c
            break

    if zip_col is None:
        raise ValueError(
            "Unable to identify ZCTA ZIP field"
        )

    zcta[zip_col] = (
        zcta[zip_col]
        .astype(str)
        .str.zfill(5)
    )

    geo = zcta.merge(
        visits,
        left_on=zip_col,
        right_on="patient_zipcode",
        how="left"
    )

    geo["encounter_count"] = (
        geo["encounter_count"]
        .fillna(0)
    )

    # ======================================================================
    # County Overlay
    # ======================================================================

    counties = None
    focus_counties = None
    zoom_bounds = None

    try:

        if county_file:

            counties = gpd.read_file(
                county_file
            )

            counties["GEOID"] = (
                counties["GEOID"]
                .astype(str)
            )

            if focus_county_geoids:

                focus_counties = counties[
                    counties["GEOID"].isin(
                        focus_county_geoids
                    )
                ]

                if not focus_counties.empty:
                    zoom_bounds = (
                        focus_counties.total_bounds
                    )

    except Exception as ex:
        logger.warning(
            f"[vis_16] County overlay unavailable: {ex}"
        )

    # ======================================================================
    # Map
    # ======================================================================

    plt.rcParams["font.family"] = font_family

    fig, ax = plt.subplots(
        figsize=(fig_width, fig_height),
        dpi=dpi
    )

    geo.plot(
        color="#EFEFEF",
        edgecolor="white",
        linewidth=0.25,
        ax=ax,
        zorder=1
    )

    active_geo = geo[
        geo["encounter_count"] > 0
    ].copy()

    scheme = (
        "Quantiles"
        if classification_method == "quantiles"
        else "NaturalBreaks"
    )

    if not active_geo.empty:

        active_geo.plot(
            column="encounter_count",
            cmap=cmap,
            scheme=scheme,
            k=num_classes,
            edgecolor="white",
            linewidth=0.25,
            ax=ax,
            zorder=10
        )

    # ------------------------------------------------------------------

    if focus_counties is not None and not focus_counties.empty:

        focus_counties.boundary.plot(
            ax=ax,
            color="grey",
            linewidth=0.4,
            zorder=40
        )

        for _, row in focus_counties.iterrows():

            point = row.geometry.representative_point()

            name = (
                row.get("NAME")
                or row.get("NAMELSAD")
                or ""
            )

            ax.text(
                point.x,
                point.y,
                name,
                fontsize=county_label_fontsize,
                color=county_label_color,
                fontweight=county_label_weight,
                fontfamily=font_family,
                ha="center",
                va="center",
                zorder=50
            )

    # ------------------------------------------------------------------
    # ZIP Labels
    # ------------------------------------------------------------------

    top_zips = visits.head(label_top_n_zips)

    for _, row in top_zips.iterrows():

        zipcode = row["patient_zipcode"]

        area = active_geo[
            active_geo[zip_col] == zipcode
        ]

        if area.empty:
            continue

        point = (
            area.geometry.iloc[0]
            .representative_point()
        )

        ax.text(
            point.x,
            point.y,
            f"{zipcode}\n({int(row['encounter_count']):,})",
            fontsize=zip_label_fontsize,
            fontfamily=font_family,
            ha="center",
            va="center",
            zorder=100
        )

    # ------------------------------------------------------------------

    if zoom_bounds is not None:

        minx, miny, maxx, maxy = zoom_bounds

        x_pad = (maxx - minx) * 0.05
        y_pad = (maxy - miny) * 0.05

        ax.set_xlim(
            minx - x_pad,
            maxx + x_pad
        )

        ax.set_ylim(
            miny - y_pad,
            maxy + y_pad
        )

    ax.set_axis_off()

    ax.set_title(
        "Low-Acuity Ambulatory Patient Origin Map\n"
        + format_date_range(
            start_date,
            end_date
        ),
        fontfamily=font_family
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

    # ======================================================================
    # Summary Table PNG
    # ======================================================================

    table_df = (
        top_zips[
            [
                "patient_zipcode",
                "encounter_count",
                "pct_of_total"
            ]
        ]
        .copy()
    )

    table_df.columns = [
        "ZIP",
        "Encounter Count",
        "Percent of Total"
    ]

    fig, ax = plt.subplots(
        figsize=(5, 3)
    )

    ax.axis("off")

    table = ax.table(
        cellText=table_df.values,
        colLabels=table_df.columns,
        loc="center"
    )

    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.2)
    for cell in table.get_celld().values():
        cell.get_text().set_fontfamily(font_family)
    table_file = output_file.replace(
        ".png",
        "_top_zips.png"
    )

    plt.savefig(
        table_file,
        dpi=dpi,
        bbox_inches="tight"
    )

    plt.close()

    # ======================================================================
    # Parameter PNG
    # ======================================================================

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
                ),
                font_family=font_family
            )

    except Exception as ex:

        logger.warning(
            f"[vis_16] Parameter export failed: {ex}"
        )

    # ======================================================================
    # RDB
    # ======================================================================

    rdb_rows = []

    if write_rdb == 1:

        rdb_rows.append({
            "run_id": params.get("run_id"),
            "client_name": params.get("client_name"),
            "domain": params.get("domain"),
            "cohort_id": params.get("cohort_id"),
            "visual_id": VISUAL_ID,
            "metric": "total_low_acuity_ambulatory_visits",
            "value": total_visits
        })

        rdb_rows.append({
            "run_id": params.get("run_id"),
            "client_name": params.get("client_name"),
            "domain": params.get("domain"),
            "cohort_id": params.get("cohort_id"),
            "visual_id": VISUAL_ID,
            "metric": "distinct_zip_count",
            "value": len(visits)
        })

        if not visits.empty:

            rdb_rows.append({
                "run_id": params.get("run_id"),
                "client_name": params.get("client_name"),
                "domain": params.get("domain"),
                "cohort_id": params.get("cohort_id"),
                "visual_id": VISUAL_ID,
                "metric": "top_zip",
                "value": visits.iloc[0][
                    "patient_zipcode"
                ]
            })

        for _, row in visits.iterrows():

            rdb_rows.append({

                "run_id": params.get("run_id"),
                "client_name": params.get("client_name"),
                "domain": params.get("domain"),
                "cohort_id": params.get("cohort_id"),
                "domain_cohort": params.get(
                    "domain_cohort"
                ),
                "start_date": start_date,
                "end_date": end_date,
                "report_title":
                    "Low-Acuity Ambulatory Patient Origin Map",
                "visual_id": VISUAL_ID,

                "dimension": "zipcode",
                "dimension_value":
                    row["patient_zipcode"],

                "ranking":
                    int(row["ranking"]),

                "encounter_count":
                    int(row["encounter_count"]),

                "pct_of_total":
                    round(
                        float(
                            row["pct_of_total"]
                        ),
                        2
                    )
            })

    logger.info("[vis_16] Complete")

    return {
        "output_path": output_file,
        "rdb": rdb_rows
    }