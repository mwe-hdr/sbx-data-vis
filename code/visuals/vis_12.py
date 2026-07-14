# =============================================================================
# Domain      : ED (Emergency Department)
# Report Name : ED Geographic Catchment
#
# Description :
# Visualizes the geographic distribution of Emergency Department utilization
# by mapping patient residence ZIP codes to corresponding ZIP Code Tabulation
# Areas (ZCTAs). Patient encounter volumes are aggregated by ZIP code and
# displayed as a thematic catchment map to illustrate the geographic service
# area and demand concentration across the market region.
#
# Encounter volumes are summarized at the ZIP code level and joined to
# geographic boundary files to generate a choropleth visualization. Areas
# with higher patient volumes are displayed using graduated color intensity,
# allowing users to identify primary service regions, referral patterns,
# and areas of concentrated utilization.
#
# Optional county overlays may be applied to highlight focus markets,
# service territories, planning regions, or study areas. County labels
# and boundaries provide additional geographic context for market analysis
# and strategic planning discussions.
#
# Key planning metrics include:
#   - Patient volume by ZIP code
#   - Geographic distribution of ED utilization
#   - Primary service area identification
#   - Secondary service area identification
#   - Regional demand concentration patterns
#
# This report supports:
#   - Market share analysis
#   - Service area planning
#   - Geographic demand assessment
#   - Community access evaluation
#   - Strategic growth planning
#   - Outreach and referral planning
#   - Network and facility planning
#
# Inputs :
#   - patient_zipcode         : Patient residential ZIP code
#   - start_date              : Reporting period start date/time
#   - end_date                : Reporting period end date/time
#   - zcta_file               : ZIP Code Tabulation Area boundary file
#   - county_file             : County boundary file (optional)
#   - focus_county_geoids     : Counties to highlight on the map
#
# Outputs :
#   - PNG map displaying:
#       * ED patient volume by ZIP code geography
#       * Graduated utilization intensity by ZIP code
#       * Geographic service area distribution
#       * Optional county boundaries and labels
#       * Focus market visualization
#
#   - RDB records containing:
#       * None currently generated
#
# Key Metrics :
#   - ED visits by ZIP code
#   - Geographic catchment distribution
#   - Service area concentration
#   - Primary market utilization
#   - Secondary market utilization
#   - Regional patient origin patterns
# =============================================================================

import os
import logging
import mapclassify
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as cx

from utils.vis_helpers import (
    normalize_params,
    format_date_range,
    apply_axis_range,
    apply_yaxis_format,
    save_legend_png,
    format_display_value,
    get_display_parameters,
    save_parameter_table_png
)

def run(
    df,
    params,
    start_date,
    end_date,
    output_dir,
    generate_output_name
):

    logging.info("Running vis_12_ed_geo_catchment")

    # ============================================================
    # REQUIRED COLUMNS
    # ============================================================

    required_cols = [
        "patient_zipcode"
    ]

    for col in required_cols:

        if col not in df.columns:

            logging.error(
                f"vis_12: missing required column '{col}'"
            )

            return

    # ============================================================
    # PARAMS
    # ============================================================

    params = params or {}

    params = {
        k: (None if pd.isna(v) else v)
        for k, v in params.items()
    }

    zcta_file = params.get("zcta_file")

    if not os.path.isabs(zcta_file):

        zcta_file = os.path.join(
            os.getcwd(),
            zcta_file
        )

    if not zcta_file:

        logging.error(
            "vis_12: zcta_file parameter required"
        )

        return

    fig_width = float(
        params.get("fig_width", 12) or 12
    )

    fig_height = float(
        params.get("fig_height", 8) or 8
    )

    dpi = int(
        params.get("dpi", 100) or 100
    )

    title_fs = int(
        params.get("title_fontsize", 14) or 14
    )

    county_file = params.get("county_file")

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

    county_label_fontsize = int(
        params.get("county_label_fontsize", 8) or 8
    )

    county_label_color = (
        params.get("county_label_color", "#444444")
        or "#444444"
    )

    county_label_weight = (
        params.get("county_label_weight", "bold")
        or "bold"
    )

    # ============================================================
    # FILTER
    # ============================================================

    subset = df.copy()

    subset["patient_zipcode"] = (
        subset["patient_zipcode"]
        .astype(str)
        .str.strip()
        .str.zfill(5)
    )

    subset = subset[
        subset["patient_zipcode"].notna()
    ]

    if subset.empty:

        logging.warning(
            "vis_12: no zipcode data available"
        )

        return

    # ============================================================
    # GEO LOAD
    # ============================================================

    try:

        zcta = gpd.read_file(
            zcta_file
        )

    except Exception as ex:

        logging.error(
            f"vis_12: unable to read zcta file: {ex}"
        )

        return

    # ============================================================
    # IDENTIFY ZIP COLUMN
    # ============================================================

    candidate_cols = [
        "ZCTA5CE20",
        "ZCTA5CE10",
        "GEOID20",
        "GEOID10"
    ]

    zip_col = None

    for col in candidate_cols:

        if col in zcta.columns:

            zip_col = col
            break

    if zip_col is None:

        logging.error(
            "vis_12: unable to identify zip field"
        )

        return

    # ============================================================
    # AGGREGATE
    # ============================================================

    visits = (
        subset
        .groupby("patient_zipcode")
        .size()
        .reset_index(name="visits")
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

    geo["visits"] = (
        geo["visits"]
        .fillna(0)
    )

    zoom_bounds = None

    if county_file and focus_county_geoids:

        try:

            counties = gpd.read_file(
                county_file
            )

            counties["GEOID"] = (
                counties["GEOID"]
                .astype(str)
            )

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

            logging.warning(
                f"County zoom unavailable: {ex}"
            )

    # ============================================================
    # PLOT
    # ============================================================

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

    geo_active = geo[
        geo["visits"] > 0
    ].copy()

    geo_active.plot(
        column="visits",
        cmap="Blues",
        scheme="NaturalBreaks",
        k=5,
        # legend=True,
        edgecolor="white",
        linewidth=0.25,
        ax=ax,
        zorder=10
    )

    if zoom_bounds is not None:

        minx, miny, maxx, maxy = zoom_bounds

        x_pad = (
            maxx - minx
        ) * 0.05

        y_pad = (
            maxy - miny
        ) * 0.05

        ax.set_xlim(
            minx - x_pad,
            maxx + x_pad
        )

        ax.set_ylim(
            miny - y_pad,
            maxy + y_pad
        )

    date_range = format_date_range(
        start_date,
        end_date
    )

    focus_counties.boundary.plot(
        ax=ax,
        color="grey",
        linewidth=0.25,
        zorder=50
    )

    for _, row in focus_counties.iterrows():

        point = row.geometry.representative_point()

        county_name = (
            row.get("NAME")
            or row.get("NAMELSAD")
            or ""
        )

        ax.text(
            point.x,
            point.y,
            county_name,
            fontsize=county_label_fontsize,
            color=county_label_color,
            fontweight=county_label_weight,
            ha="center",
            va="center",
            zorder=100
        )

    ax.set_title(
        f"ED Geographic Catchment\n{date_range}",
        fontsize=title_fs
    )

    ax.set_axis_off()

    plt.tight_layout()

    # ============================================================
    # SAVE
    # ============================================================

    output_file = os.path.join(
        output_dir,
        generate_output_name(
            visual_id="vis_12",
            start_date=start_date,
            end_date=end_date,
            cohort_id=params.get("cohort_id"),
            ext="png"
        )
    )

    plt.savefig(
        output_file,
        bbox_inches="tight"
    )

    plt.close()

    logging.info(
        f"vis_12 output written: {output_file}"
    )

    # ============================================================
    # RDB
    # ============================================================

    rdb_rows = []

    return {
        "output_path": output_file,
        "rdb": rdb_rows
    }