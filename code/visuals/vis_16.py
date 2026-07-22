# =============================================================================
# Domain      : ED (Emergency Department)
#
# Report Name : Low-Acuity Ambulance Patient Origin Map
#
# Description :
#
# Identifies geographic origin patterns for ambulatory low-acuity ED visits.
#
# Population:
#   - Ambulance Arrivals
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
import mapclassify
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib_scalebar.scalebar import ScaleBar
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
from matplotlib.colors import to_hex
from shapely.geometry import Point
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

VISUAL_ID = "vis_16"

logger = logging.getLogger(__name__)

from utils.vis_helpers import (
    normalize_params,
    format_date_range,
    apply_axis_range,
    apply_yaxis_format,
    save_legend_png,
    format_display_value,
    get_display_parameters,
    save_parameter_table_png,
    save_title_png
)

def _load_cohort_location(
    cohort_locations_file,
    cohort_id
):

    try:

        locations = pd.read_csv(
            cohort_locations_file
        )

        cohort_rows = locations[
            locations["cohort"]
            .astype(str)
            .str.strip()
            == str(cohort_id).strip()
        ]

        if cohort_rows.empty:
            return None, None

        lat = cohort_rows.loc[
            cohort_rows["param"] == "lat",
            "value"
        ]

        lng = cohort_rows.loc[
            cohort_rows["param"] == "lng",
            "value"
        ]

        if lat.empty or lng.empty:
            return None, None

        return (
            float(lat.iloc[0]),
            float(lng.iloc[0])
        )

    except Exception as ex:

        logging.warning(
            f"Unable to load cohort location: {ex}"
        )

        return None, None

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

def _build_dynamic_legend(
    values,
    cmap_name,
    classification_method,
    num_classes,
    value_suffix=""
):

    values = pd.Series(values)
    values = values.dropna()

    if values.empty:

        return [], []

    if classification_method.lower() == "quantiles":

        classifier = (
            mapclassify.Quantiles(
                values,
                k=num_classes
            )
        )

    else:

        classifier = (
            mapclassify.NaturalBreaks(
                values,
                k=num_classes
            )
        )

    bins = classifier.bins

    cmap_obj = plt.get_cmap(
        cmap_name,
        num_classes
    )
    colors = [
        to_hex(
            cmap_obj(i)
        )
        for i in range(num_classes)
    ]

    handles = []

    labels = []

    lower = (
        int(values.min())
    )

    for i, upper in enumerate(bins):

        upper = int(round(upper))

        label = (
            f"{lower:,} - {upper:,}"
        )

        if value_suffix:

            label = (
                f"{label} "
                f"{value_suffix}"
            )

        labels.append(label)

        handles.append(
            Patch(
                facecolor=colors[i],
                edgecolor="none",
                label=labels[-1]
            )
        )

        lower = upper + 1

    handles.reverse()
    labels.reverse()

    return handles, labels

def _parse_county_label_offsets(
    offset_string
):

    results = {}

    if not offset_string:
        return results

    for item in str(offset_string).split(";"):

        item = item.strip()

        if not item:
            continue

        try:

            geoid, direction, distance = (
                item.split(":")
            )

            results[
                geoid.strip()
            ] = (
                direction.strip().upper(),
                float(distance)
            )

        except Exception:

            logging.warning(
                f"Invalid county label offset: {item}"
            )

    return results

def _apply_county_label_offset(
    point,
    geoid,
    county_label_offsets
):
    """
    Apply optional label offset.
    """

    if geoid not in county_label_offsets:

        return point

    direction, distance = (
        county_label_offsets[geoid]
    )

    x = point.x
    y = point.y

    if direction == "N":
        y += distance

    elif direction == "S":
        y -= distance

    elif direction == "E":
        x += distance

    elif direction == "W":
        x -= distance

    elif direction == "NE":
        x += distance
        y += distance

    elif direction == "NW":
        x -= distance
        y += distance

    elif direction == "SE":
        x += distance
        y -= distance

    elif direction == "SW":
        x -= distance
        y -= distance

    return x, y

def run(
    df,
    params,
    start_date,
    end_date,
    output_dir,
    generate_output_name
):

    logging.info("Running vis_16_ed_geo_catchment")

    # ============================================================
    # REQUIRED COLUMNS
    # ============================================================

    required_cols = [
        "patient_zipcode",
        "arrival_method",
        "esi",
        "ed_start_dtm"
    ]

    for col in required_cols:

        if col not in df.columns:

            logging.error(
                f"vis_16: missing required column '{col}'"
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
            "vis_16: zcta_file parameter required"
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

    cohort_locations_file = (
        params.get(
            "cohort_locations_file"
        )
    )

    facility_marker_size = float(
        params.get(
            "facility_marker_size",
            150
        )
    )

    facility_marker_color = params.get(
        "facility_marker_color",
        "#FF0000"
    )

    facility_marker_edgecolor = params.get(
        "facility_marker_edgecolor",
        "white"
    )

    facility_label = params.get(
        "facility_label",
        "Facility"
    )

    zoom_radius_miles = float(
        params.get(
            "zoom_radius_miles",
            25
        )
    )

    title_fs = int(
        params.get("title_fontsize", 14) or 14
    )
    font_family = str(
        params.get("font_family", "Segoe UI")
    ).strip()
    county_file = params.get("county_file")

    county_label_offsets = (
        _parse_county_label_offsets(
            params.get(
                "county_label_offsets",
                ""
            )
        )
    )

    low_acuity_esi_values = (
        params.get(
            "low_acuity_esi_values",
            "4;5"
        )
    )

    write_rdb = int(
        float(
            params.get(
                "write_rdb",
                0
            )
        )
    )

    low_acuity_esi_values = [
        int(x.strip())
        for x in str(
            low_acuity_esi_values
        ).split(";")
        if str(x).strip()
    ]

    show_water = int(
        float(params.get("show_water", 1))
    )

    legend_value_suffix = str(
        params.get(
            "legend_value_suffix",
            ""
        ) or ""
    ).strip()

    water_directory = params.get(
        "water_directory",
        "data/input/geo/tl_2025_water"
    )

    water_color = params.get(
        "water_color",
        "#BFDFFF"
    )

    water_alpha = float(
        params.get("water_alpha", 1.0)
    )

    water_contiguity_order = int(
        float(
            params.get(
                "water_contiguity_order",
                2
            )
        )
    )

    water_area_threshold = float(
        params.get(
            "water_area_threshold",
            250000
        )
    )

    # -------------------------------------
    # TITLE IMAGE
    # -------------------------------------

    title_width = float(
        params.get("title_width", 6.40) or 6.40
    )

    title_height = float(
        params.get("title_height", 0.25) or 0.25
    )

    subtitle_fontsize = int(
        params.get("subtitle_fontsize", 8) or 8
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

    # -------------------------------------
    # LEGEND IMAGE
    # -------------------------------------

    legend_width = float(
        params.get("legend_width", 4) or 4
    )

    legend_height = float(
        params.get("legend_height", 1) or 1
    )

    legend_fontsize = int(
        params.get("legend_fontsize", 8) or 8
    )

    tick_fontsize = int(
        params.get("tick_fontsize", 8) or 8
    )

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

    label_top_n_zips = int(
        float(
            params.get(
                "label_top_n_zips",
                10
            )
        )
    )

    zip_label_fontsize = int(
        float(
            params.get(
                "zip_label_fontsize",
                6
            )
        )
    )

    zip_label_weight = str(
        params.get(
            "zip_label_weight",
            "bold"
        )
    )

    zip_label_halo_width = float(
        params.get(
            "zip_label_halo_width",
            1.5
        )
    )

    # ============================================================
    # FILTER
    # ============================================================

    subset = df.copy()

    # ============================================================
    # DATE FILTER
    # ============================================================

    if "ed_start_dtm" in subset.columns:

        subset["ed_start_dtm"] = pd.to_datetime(
            subset["ed_start_dtm"],
            errors="coerce"
        )

        report_start = pd.to_datetime(start_date)
        report_end = pd.to_datetime(end_date)

        if (
            report_end.hour == 0
            and report_end.minute == 0
            and report_end.second == 0
        ):
            report_end = (
                report_end
                + pd.Timedelta(days=1)
                - pd.Timedelta(minutes=1)
            )

        subset = subset[
            (subset["ed_start_dtm"] >= report_start)
            &
            (subset["ed_start_dtm"] <= report_end)
        ].copy()

        logging.info(
            f"vis_16 rows after date filter: "
            f"{len(subset):,}"
        )

        if subset.empty:
            logging.warning(
                "vis_16: no visits after date filtering"
            )
            return

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
            "vis_16: no zipcode data available"
        )

        return

    subset["arrival_group"] = (
        subset["arrival_method"]
        .apply(_map_arrival_method)
    )

    subset["esi"] = pd.to_numeric(
        subset["esi"],
        errors="coerce"
    )

    subset = subset[
        subset["arrival_group"]
        == "Ambulance"
    ]

    subset = subset[
        subset["esi"].isin(
            low_acuity_esi_values
        )
    ]

    # ============================================================
    # GEO LOAD
    # ============================================================

    try:

        zcta = gpd.read_file(
            zcta_file
        )
        zcta = zcta.to_crs(3857)

    except Exception as ex:

        logging.error(
            f"vis_16: unable to read zcta file: {ex}"
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
            "vis_16: unable to identify zip field"
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
        .sort_values(
            "visits",
            ascending=False
        )
    )

    total_visits = int(
        visits["visits"].sum()
    )

    visits["pct_of_total"] = (
        visits["visits"]
        / total_visits
        * 100
    )

    visits["ranking"] = (
        range(
            1,
            len(visits) + 1
        )
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

    facility_lat, facility_lng = (
        _load_cohort_location(
            cohort_locations_file,
            params.get("cohort_id")
        )
    )

    facility_point = None

    if (
        facility_lat is not None
        and facility_lng is not None
    ):

        facility_point = (
            gpd.GeoSeries(
                [
                    Point(
                        facility_lng,
                        facility_lat
                    )
                ],
                crs=4326
            )
            .to_crs(3857)
            .iloc[0]
        )

    if county_file and focus_county_geoids:

        try:

            counties = gpd.read_file(
                county_file
            )
            counties = counties.to_crs(3857)

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

                water_geoids = set(
                    focus_county_geoids
                )

                current_geoids = set(
                    focus_county_geoids
                )

                for _ in range(
                    water_contiguity_order
                ):

                    current_counties = counties[
                        counties["GEOID"].isin(
                            current_geoids
                        )
                    ]

                    neighbors = gpd.sjoin(
                        counties[
                            ["GEOID", "geometry"]
                        ],
                        current_counties[
                            ["geometry"]
                        ],
                        how="inner",
                        predicate="touches"
                    )

                    new_geoids = (
                        set(neighbors["GEOID"])
                        - water_geoids
                    )

                    water_geoids.update(
                        new_geoids
                    )

                    current_geoids = new_geoids

                zoom_bounds = (
                    focus_counties.total_bounds
                )

        except Exception as ex:

            logging.warning(
                f"County zoom unavailable: {ex}"
            )

    # ============================================================
    # WATER
    # ============================================================

    water_gdf = None

    try:

        if (
            show_water == 1
            and focus_county_geoids
        ):

            water_layers = []

            for geoid in water_geoids:

                water_file = os.path.join(
                    water_directory,
                    f"tl_2025_{geoid}_areawater.shp"
                )

                if os.path.exists(
                    water_file
                ):

                    water = gpd.read_file(
                        water_file
                    )

                    if water.crs is not None:

                        water = water.to_crs(
                            3857
                        )

                    water_layers.append(
                        water
                    )

            if water_layers:

                water_gdf = pd.concat(
                    water_layers,
                    ignore_index=True
                )

                water_gdf = gpd.GeoDataFrame(
                    water_gdf,
                    geometry="geometry",
                    crs=3857
                )

                water_gdf[
                    "water_area"
                ] = (
                    water_gdf.geometry.area
                )

                water_gdf = water_gdf[
                    water_gdf["water_area"]
                    >= water_area_threshold
                ].copy()

                logging.info(
                    f"vis_16 loaded "
                    f"{len(water_gdf)} "
                    f"water polygons"
                )

    except Exception as ex:

        logging.warning(
            f"vis_16 water unavailable: {ex}"
        )

    # ============================================================
    # PLOT
    # ============================================================

    if not focus_counties.empty:
        focus_counties = focus_counties.to_crs(3857)

    plt.rcParams["font.family"] = font_family

    fig, ax = plt.subplots(
        figsize=(fig_width, fig_height),
        dpi=dpi
    )

    ax.set_facecolor(
        water_color
    )

    if water_gdf is not None:

        water_gdf.plot(
            ax=ax,
            color=water_color,
            edgecolor="none",
            alpha=water_alpha,
            zorder=0
        )

    geo.plot(
        color="none",
        edgecolor="#D0D0D0",
        linewidth=0.25,
        ax=ax,
        zorder=1
    )

    geo_active = geo[
        geo["visits"] > 0
    ].copy()

    if water_gdf is not None:

        try:

            water_union = (
                water_gdf.union_all()
            )

            geo_active[
                "geometry"
            ] = (
                geo_active.geometry
                .difference(
                    water_union
                )
            )

            geo_active = (
                geo_active[
                    ~geo_active
                    .geometry
                    .is_empty
                ]
                .copy()
            )

            logging.info(
                "vis_16 water cutout applied"
            )

        except Exception as ex:

            logging.warning(
                f"vis_16 water cutout failed: {ex}"
            )

    classification_method = str(
        params.get(
            "classification_method",
            "naturalbreaks"
        )
    ).lower()

    num_classes = int(
        float(
            params.get(
                "num_classes",
                5
            )
        )
    )

    cmap = params.get(
        "cmap",
        "Blues"
    )

    geo_active.plot(
        column="visits",
        cmap=cmap,
        scheme=(
            "Quantiles"
            if classification_method == "quantiles"
            else "NaturalBreaks"
        ),
        k=num_classes,
        # legend=True,
        edgecolor="white",
        linewidth=0.25,
        ax=ax,
        zorder=10
    )

    # ============================================================
    # TOP ZIP LABELS
    # ============================================================

    zip_label_artists = []

    top_zips = visits.head(
        label_top_n_zips
    )

    for _, row in top_zips.iterrows():

        zipcode = row[
            "patient_zipcode"
        ]

        area = geo_active[
            geo_active[zip_col]
            == zipcode
        ]

        if area.empty:
            continue

        point = (
            area.geometry.iloc[0]
            .representative_point()
        )

        txt = ax.text(
            point.x,
            point.y,
            (
                f"{zipcode}\n"
                f"({int(row['visits']):,})"
            ),
            fontsize=zip_label_fontsize,
            fontweight=zip_label_weight,
            fontfamily=font_family,
            ha="center",
            va="center",
            zorder=150
        )
        zip_label_artists.append(txt)

        txt.set_path_effects([
            pe.withStroke(
                linewidth=zip_label_halo_width,
                foreground="white"
            )
        ])

    if zoom_bounds is not None:

        minx, miny, maxx, maxy = zoom_bounds

        map_center_x = (minx + maxx) / 2
        map_center_y = (miny + maxy) / 2

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

    if facility_point is not None:

        ax.scatter(
            facility_point.x,
            facility_point.y,
            s=facility_marker_size,
            c=facility_marker_color,
            edgecolors=facility_marker_edgecolor,
            linewidths=1.5,
            zorder=500
        )

        ax.text(
            facility_point.x,
            facility_point.y,
            facility_label,
            fontsize=8,
            fontweight="bold",
            ha="left",
            va="bottom",
            zorder=501
        )

    radius_meters = (
        zoom_radius_miles
        * 1609.344
    )

    orig_xlim = ax.get_xlim()
    orig_ylim = ax.get_ylim()

    if facility_point is not None:

        minx = (
            facility_point.x
            - radius_meters
        )

        maxx = (
            facility_point.x
            + radius_meters
        )

        miny = (
            facility_point.y
            - radius_meters
        )

        maxy = (
            facility_point.y
            + radius_meters
        )

        ax.set_xlim(
            minx,
            maxx
        )

        ax.set_ylim(
            miny,
            maxy
        )

        if facility_point is not None:

            center_x = facility_point.x
            center_y = facility_point.y

            ax.xaxis.set_major_formatter(
                FuncFormatter(
                    lambda val, pos:
                    f"{(val-center_x)/1609.344:.0f}"
                )
            )

            ax.yaxis.set_major_formatter(
                FuncFormatter(
                    lambda val, pos:
                    f"{(val-center_y)/1609.344:.0f}"
                )
            )

            ax.set_xlabel("Miles East / West from Facility")
            ax.set_ylabel("Miles North / South from Facility")

        zoom_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id=f"vis_16_zoom",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get(
                    "cohort_id"
                ),
                ext="png"
            )
        )

        plt.savefig(
            zoom_output_file,
            dpi=dpi,
            bbox_inches="tight"
        )

        logging.info(
            f"Zoom map written: "
            f"{zoom_output_file}"
        )

        for artist in zip_label_artists:
            artist.remove()

    # ax.xaxis.set_major_formatter(
    #     FuncFormatter(
    #         lambda val, pos:
    #         f"{(val - map_center_x) / 1609.344:.0f}"
    #     )
    # )

    # ax.yaxis.set_major_formatter(
    #     FuncFormatter(
    #         lambda val, pos:
    #         f"{(val - map_center_y) / 1609.344:.0f}"
    #     )
    # )

    # ax.set_xlabel("Miles")
    # ax.set_ylabel("Miles")

    for _, row in focus_counties.iterrows():

        point = (
            row.geometry
            .representative_point()
        )

        label_x = point.x
        label_y = point.y

        geoid = str(
            row.get("GEOID")
        )

        if geoid in county_label_offsets:

            label_x, label_y = (
                _apply_county_label_offset(
                    point,
                    geoid,
                    county_label_offsets
                )
            )

        county_name = (
            row.get("NAME")
            or row.get("NAMELSAD")
            or ""
        )

        txt = ax.text(
            label_x,
            label_y,
            county_name,
            fontsize=county_label_fontsize,
            color="#333333",
            fontweight="semibold",
            fontfamily=font_family,
            ha="center",
            va="center",
            zorder=100
        )

        txt.set_path_effects([
            pe.withStroke(
                linewidth=2,
                foreground="white"
            )
        ])

    for tick in ax.get_xticklabels():
        tick.set_fontfamily(font_family)
        tick.set_fontsize(tick_fontsize)

    for tick in ax.get_yticklabels():
        tick.set_fontfamily(font_family)
        tick.set_fontsize(tick_fontsize)

    logging.info(f"vis_16 CRS: {geo.crs}")

    ax.set_aspect("equal")

    # ax.annotate(
    #     "N",
    #     xy=(0.99, 0.99),
    #     xytext=(0.99, 0.95),
    #     xycoords="axes fraction",
    #     textcoords="axes fraction",
    #     fontsize=8,
    #     fontweight="bold",
    #     ha="center",
    #     va="center",
    #     arrowprops=dict(
    #         facecolor="black",
    #         width=1,
    #         headwidth=8,
    #         headlength=8
    #     ),
    #     zorder=200
    # )

    # ax.add_artist(scalebar)

    ax.set_axis_off()

    plt.tight_layout()


    # ============================================================
    # SAVE
    # ============================================================

    ax.set_xlim(orig_xlim)
    ax.set_ylim(orig_ylim)

    output_file = os.path.join(
        output_dir,
        generate_output_name(
            visual_id="vis_16",
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
        f"vis_16 output written: {output_file}"
    )


    # ============================================================
    # TOP ZIP SUMMARY PNG
    # ============================================================

    table_df = (
        top_zips[
            [
                "patient_zipcode",
                "visits",
                "pct_of_total"
            ]
        ]
        .copy()
    )

    table_df.columns = [
        "ZIP",
        "Visits",
        "Percent of Total"
    ]

    table_df["Visits"] = (
        table_df["Visits"]
        .apply(
            lambda x:
            f"{int(x):,}"
        )
    )

    table_df["Percent of Total"] = (
        table_df["Percent of Total"]
        .round(1)
        .astype(str)
        + "%"
    )

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

    table.scale(
        1,
        1.2
    )

    for cell in table.get_celld().values():

        cell.get_text().set_fontfamily(
            font_family
        )

    for col in range(
        len(table_df.columns)
    ):

        header_cell = table[(0, col)]

        header_cell.set_facecolor(
            "#e8e8e8"
        )

        header_cell.get_text().set_weight(
            "bold"
        )

    for row in range(
        1,
        len(table_df) + 1
    ):

        if row % 2 == 1:

            for col in range(
                len(table_df.columns)
            ):

                table[
                    (row, col)
                ].set_facecolor(
                    "#f2f2f2"
                )

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

    logging.info(
        f"vis_16 top zip table written: "
        f"{table_file}"
    )

    # ============================================================
    # LEGEND PNG
    # ============================================================

    legend_handles, legend_labels = (
        _build_dynamic_legend(
            values=geo_active["visits"],
            cmap_name=cmap,
            classification_method=classification_method,
            num_classes=num_classes,
            value_suffix=legend_value_suffix
        )
    )

    facility_handle = Line2D(
        [0],
        [0],
        marker="o",
        color="w",
        label="Facility",
        markerfacecolor=facility_marker_color,
        markersize=8
    )

    legend_handles.append(
        facility_handle
    )

    legend_labels.append(
        "Facility"
    )

    legend_output_file = os.path.join(
        output_dir,
        generate_output_name(
            visual_id="vis_16_legend",
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

    logging.info(
        f"vis_16 legend written: "
        f"{legend_output_file}"
    )

    # ============================================================
    # TITLE PNG
    # ============================================================

    title_output_file = os.path.join(
        output_dir,
        generate_output_name(
            visual_id="vis_16_title",
            start_date=start_date,
            end_date=end_date,
            cohort_id=params.get("cohort_id"),
            ext="png"
        )
    )

    save_title_png(
        title="Low-Acuity EMT Patient Origin Map",
        subtitle=date_range,
        output_file=title_output_file,
        width=title_width,
        height=title_height,
        dpi=dpi,
        font_family=font_family,
        title_fontsize=title_fs,
        subtitle_fontsize=subtitle_fontsize,
        background_color=title_background_color,
        title_weight=title_weight
    )

    logging.info(
        f"vis_16 title written: "
        f"{title_output_file}"
    )

    # ============================================================
    # RDB
    # ============================================================

    rdb_rows = []

    return {
        "output_path": output_file,
        "rdb": rdb_rows
    }