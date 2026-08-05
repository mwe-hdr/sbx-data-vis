# =============================================================================
# Report Name : EMS Arrival Funnel by ESI
#
# Description :
#
# Extends the Facility Patient Flow Sankey by focusing on ambulatory arrivals and
# stratifying patient progression by ESI level.
#
# Flow:
#
#     EMT Arrival
#         ->
#     Triage
#         ->
#     Facility Evaluation
#         ->
#     Disposition
#
# Dispositions:
#
#     Discharge
#     Inpatient
#     Observation
#     Transfer
#     Exit Without Care
#     Expired
#
# Ambulatory arrivals are defined using the arrival-method grouping logic
# established in vis_19:
#
#     EMT Arrival
#
# Outputs:
#
#     Main Sankey PNG
#     Parameter PNG
#     RDB Output
#
# =============================================================================

import os
import logging
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from matplotlib.patches import Patch


from utils.vis_helpers import (
    normalize_params,
    format_date_range,
    save_parameter_table_png,
    get_display_parameters,
    save_title_png,
    save_legend_png,
    map_arrival_method
)

logger = logging.getLogger(__name__)

VISUAL_ID = "vis_20"

def _map_disposition(val):

    if pd.isna(val):
        return "Exit Without Care"

    val = str(val).lower()

    if "discharge" in val:
        return "Discharge"

    if "admit" in val:
        return "Inpatient"

    if "observation" in val:
        return "Observation"

    if "transfer" in val:
        return "Transfer"

    if "expired" in val:
        return "Expired"

    return "Exit Without Care"

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

    defaults = {
        "title": "EMT Arrival Funnel by ESI",

        "fig_width": 1400,
        "fig_height": 900,

        "font_family": "Segoe UI",
        "node_font_size": 14,

        "title_font_size": 22,
        "title_x": 0.01,

        "flow_opacity": 0.30,

        # ==================================================
        # TITLE IMAGE
        # ==================================================

        "title_width": 6.40,
        "title_height": 0.25,
        "subtitle_fontsize": 8,
        "title_background_color": "#d9d9d9",
        "title_weight": "bold",

        # ==================================================
        # LEGEND IMAGE
        # ==================================================

        "legend_width": 6,
        "legend_height": 1,
        "legend_fontsize": 8
    }

    p = {**defaults, **(params or {})}

    required_cols = {
        "arrival_dtm",
        "arrival_method",
        "esi",
        "triage_start_dtm",
        "tmt_start_dtm",
        "disch_disp_desc"
    }

    if df is None:
        logger.warning(f"[{VISUAL_ID}] dataframe is None")
        return

    missing = required_cols - set(df.columns)

    if missing:
        logger.warning(
            f"[{VISUAL_ID}] Missing columns: {sorted(missing)}"
        )
        return

    df = df.copy()

    df["arrival_dtm"] = pd.to_datetime(
        df["arrival_dtm"],
        errors="coerce"
    )

    df["triage_start_dtm"] = pd.to_datetime(
        df["triage_start_dtm"],
        errors="coerce"
    )

    df["tmt_start_dtm"] = pd.to_datetime(
        df["tmt_start_dtm"],
        errors="coerce"
    )

    df["esi"] = pd.to_numeric(
        df["esi"],
        errors="coerce"
    )

    df = df.dropna(df=["arrival_dtm"])

    # =========================
    # DATE WINDOW FILTER
    # =========================
    if "tmt_stop_dtm" in df.columns:
        # Include any record whose interval overlaps the requested window
        df = df[
            (df["arrival_dtm"] <= end_date) &
            (df["tmt_stop_dtm"] >= start_date)
        ].copy()
    else:
        # Fallback for datasets without tmt_stop_dtm:
        # arrival_dtm must fall within the requested window
        df = df[
            (df["arrival_dtm"] >= start_date) &
            (df["arrival_dtm"] <= end_date)
        ].copy()

    if df.empty:
        logging.warning(f"{VISUAL_ID}: no data after date window filtering")
        return

    df["arrival_type"] = (
        df["arrival_method"]
        .apply(map_arrival_method)
    )

    df = df[
        df["arrival_type"] == "EMT"
    ]

    df = df[
        df["esi"].isin([1, 2, 3, 4, 5])
    ]

    df["has_triage"] = (
        df["triage_start_dtm"].notna()
    )

    df["has_ed"] = (
        df["tmt_start_dtm"].notna()
    )

    df["disposition"] = (
        df["disch_disp_desc"]
        .apply(_map_disposition)
    )

    esi_min = int(
        params.get(
            "esi_focused_min",
            3
        )
    )

    esi_max = int(
        params.get(
            "esi_focused_max",
            5
        )
    )

    focused_df = df[
        (
            df["esi"] >= esi_min
        )
        &
        (
            df["esi"] <= esi_max
        )
    ].copy()

    dispositions = [
        "Discharge",
        "Inpatient",
        "Observation",
        "Transfer",
        "Exit Without Care",
        "Expired"
    ]

    esi_levels = [1, 2, 3, 4, 5]

    node_labels = []
    node_names = []

    node_names.append("EMT Arrival")

    for esi in esi_levels:
        node_names.append(f"ESI {esi}")

    for esi in esi_levels:
        node_names.append(f"ESI {esi} Triage")

    for esi in esi_levels:
        node_names.append(f"ESI {esi} Treatment")

    for esi in esi_levels:
        for disp in dispositions:
            node_names.append(
                f"ESI {esi} {disp}"
            )

    totals = {}

    totals["EMT Arrival"] = len(df)

    parent_totals = {}
    
    for esi in esi_levels:

        subset = df[
            df["esi"] == esi
        ]

        triage_df = subset[
            subset["has_triage"]
        ]

        ed_df = triage_df[
            triage_df["has_ed"]
        ]

        esi_count = len(subset)
        triage_count = len(triage_df)
        ed_count = len(ed_df)

        totals[f"ESI {esi}"] = esi_count

        totals[f"ESI {esi} Triage"] = triage_count

        totals[f"ESI {esi} Treatment"] = ed_count

        parent_totals[f"ESI {esi}"] = totals["EMT Arrival"]

        parent_totals[f"ESI {esi} Triage"] = totals[f"ESI {esi}"]

        parent_totals[f"ESI {esi} Treatment"] = totals[f"ESI {esi} Triage"]

        for disp in dispositions:
            parent_totals[f"ESI {esi} {disp}"] = totals[f"ESI {esi} Treatment"]
        
        for disp in dispositions:

            count = len(
                ed_df[
                    ed_df["disposition"] == disp
                ]
            )

            totals[f"ESI {esi} {disp}"] = int(count)

    for name in node_names:

        count = totals.get(name, 0)

        if name == "EMT Arrival":

            pct = 1.0

        elif name in {
            "ESI 1",
            "ESI 2",
            "ESI 3",
            "ESI 4",
            "ESI 5"
        }:

            pct = count / totals["EMT Arrival"]

        else:

            parent = parent_totals.get(name, 0)

            pct = count / parent if parent > 0 else 0

        node_labels.append(
            (
                f"<b>{name}</b><br>"
                f"{count:,} ({pct:.1%})"
            )
        )

    idx = {
        name: pos
        for pos, name in enumerate(node_names)
    }

    sources = []
    targets = []
    values = []

    for esi in esi_levels:

        esi_df = df[
            df["esi"] == esi
        ]

        esi_count = len(esi_df)

        triage_df = esi_df[
            esi_df["has_triage"]
        ]

        ed_df = triage_df[
            triage_df["has_ed"]
        ]

        esi_count = len(esi_df)
        triage_count = len(triage_df)
        ed_count = len(ed_df)

        if esi_count > 0:
            sources.append(idx["EMT Arrival"])
            targets.append(idx[f"ESI {esi}"])
            values.append(int(esi_count))

        if triage_count > 0:
            sources.append(idx[f"ESI {esi}"])
            targets.append(idx[f"ESI {esi} Triage"])
            values.append(int(triage_count))

        if ed_count > 0:
            sources.append(idx[f"ESI {esi} Triage"])
            targets.append(idx[f"ESI {esi} Treatment"])
            values.append(int(ed_count))

        for disp in dispositions:

            disp_count = totals[
                f"ESI {esi} {disp}"
            ]

            if disp_count > 0:

                sources.append(
                    idx[f"ESI {esi} Treatment"]
                )

                targets.append(
                    idx[f"ESI {esi} {disp}"]
                )

                values.append(
                    int(disp_count)
                )

    color_scale = [
        "#08306B",
        "#2171B5",
        "#4292C6",
        "#6BAED6",
        "#9ECAE1",
        "#C6DBEF"
    ]

    node_colors = []

    for name in node_names:

        if name == "EMT Arrival":
            node_colors.append(color_scale[0])

        elif name.startswith("ESI 1"):
            node_colors.append(color_scale[0])

        elif name.startswith("ESI 2"):
            node_colors.append(color_scale[1])

        elif name.startswith("ESI 3"):
            node_colors.append(color_scale[2])

        elif name.startswith("ESI 4"):
            node_colors.append(color_scale[3])

        else:
            node_colors.append(color_scale[4])

    fig = go.Figure(
        data=[
            go.Sankey(
                arrangement="snap",
                node=dict(
                    pad=80,
                    thickness=20,
                    label=node_labels,
                    color=node_colors
                ),
                link=dict(
                    source=sources,
                    target=targets,
                    value=values,
                    color=[
                        f"rgba(120,120,120,{float(p['flow_opacity'])})"
                    ] * len(values)
                )
            )
        ]
    )

    fig.update_layout(
        width=int(p["fig_width"]),
        height=int(p["fig_height"]),
        font=dict(
            family=p["font_family"],
            size=int(p["node_font_size"])
        ),
        margin=dict(
            t=10,
            l=10,
            r=10,
            b=10
        )
    )

    output_file = os.path.join(
        output_dir,
        generate_output_name(
            visual_id=VISUAL_ID,
            start_date=start_date,
            end_date=end_date,
            cohort_id=params.get("cohort_id"),
            ext="png"
        )
    )

    fig.write_image(output_file)

    # ==========================================================
    # TITLE IMAGE
    # ==========================================================

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
        title=p["title"],
        subtitle=format_date_range(
            start_date,
            end_date
        ),
        output_file=title_output_file,
        width=float(p["title_width"]),
        height=float(p["title_height"]),
        dpi=300,
        font_family=p["font_family"],
        title_fontsize=int(p["title_font_size"]),
        subtitle_fontsize=int(
            p["subtitle_fontsize"]
        ),
        background_color=
            p["title_background_color"],
        title_weight=p["title_weight"]
    )

    logger.info(
        f"[{VISUAL_ID}] Title written: "
        f"{title_output_file}"
    )

    # ==========================================================
    # ESI 3-5 COMPANION FUNNEL
    # ==========================================================

    esifocused_output_file = output_file.replace(
        ".png",
        f"_esi{esi_min}{esi_max}.png"
    )

    low_df = focused_df.copy()

    triage_df = low_df[
        low_df["has_triage"]
    ]

    ed_df = triage_df[
        triage_df["has_ed"]
    ]

    total_count = len(low_df)
    triage_count = len(triage_df)
    ed_count = len(ed_df)

    node_names_focused = [
        f"EMT ESI {esi_min}-{esi_max}",
        "Triage",
        "Treatment",
        "Discharge",
        "Inpatient",
        "Observation",
        "Transfer",
        "Exit Without Care",
        "Expired"
    ]

    disp_counts = {}

    for disp in dispositions:

        disp_counts[disp] = len(
            ed_df[
                ed_df["disposition"] == disp
            ]
        )

    node_labels_focused = [
        (
            f"<b>EMT ESI {esi_min}-{esi_max}</b><br>"
            f"{total_count:,} (100.0%)"
        ),
        (
            f"<b>Triage</b><br>"
            f"{triage_count:,} "
            f"({triage_count/total_count:.1%})"
            if total_count > 0
            else "<b>Triage</b><br>0"
        ),
        (
            f"<b>Treatment</b><br>"
            f"{ed_count:,} "
            f"({ed_count/triage_count:.1%})"
            if triage_count > 0
            else "<b>Treatment</b><br>0"
        )
    ]

    for disp in dispositions:

        count = disp_counts[disp]

        pct = (
            count / ed_count
            if ed_count > 0
            else 0
        )

        node_labels_focused.append(
            (
                f"<b>{disp}</b><br>"
                f"{count:,} ({pct:.1%})"
            )
        )

    idxfocused = {
        n: i
        for i, n in enumerate(node_names_focused)
    }

    sourcesfocused = [
        idxfocused[
            f"EMT ESI {esi_min}-{esi_max}"
        ],
        idxfocused["Triage"]
    ]

    targetsfocused = [
        idxfocused["Triage"],
        idxfocused["Treatment"]
    ]

    valuesfocused = [
        total_count,
        triage_count
    ]

    for disp in dispositions:

        count = disp_counts[disp]

        if count > 0:

            sourcesfocused.append(
                idxfocused["Treatment"]
            )

            targetsfocused.append(
                idxfocused[disp]
            )

            valuesfocused.append(
                count
            )

    colorsfocused = [
        "#4292C6",
        "#4292C6",
        "#4292C6",
        "#6BAED6",
        "#6BAED6",
        "#6BAED6",
        "#6BAED6",
        "#6BAED6",
        "#6BAED6"
    ]

    figfocused = go.Figure(
        data=[
            go.Sankey(
                arrangement="snap",
                node=dict(
                    pad=80,
                    thickness=20,
                    label=node_labels_focused,
                    color=colorsfocused
                ),
                link=dict(
                    source=sourcesfocused,
                    target=targetsfocused,
                    value=valuesfocused,
                    color=[
                        f"rgba(120,120,120,{float(p['flow_opacity'])})"
                    ] * len(valuesfocused)
                )
            )
        ]
    )

    figfocused.update_layout(
        width=int(p["fig_width"]),
        height=int(p["fig_height"]),
        font=dict(
            family=p["font_family"],
            size=int(p["node_font_size"])
        ),
        margin=dict(
            t=10,
            l=10,
            r=10,
            b=10
        )
    )

    figfocused.write_image(
        esifocused_output_file
    )

    # ==========================================================
    # LEGEND PNG
    # ==========================================================

    legend_handles = [
        Patch(
            facecolor="#08306B",
            label="ESI 1"
        ),
        Patch(
            facecolor="#2171B5",
            label="ESI 2"
        ),
        Patch(
            facecolor="#4292C6",
            label="ESI 3"
        ),
        Patch(
            facecolor="#6BAED6",
            label="ESI 4"
        ),
        Patch(
            facecolor="#9ECAE1",
            label="ESI 5"
        )
    ]

    legend_labels = [
        "ESI 1",
        "ESI 2",
        "ESI 3",
        "ESI 4",
        "ESI 5"
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
        ncol=5,
        font_family=p["font_family"],
        font_size=int(
            p["legend_fontsize"]
        ),
        width=float(
            p["legend_width"]
        ),
        height=float(
            p["legend_height"]
        )
    )

    logger.info(
        f"[{VISUAL_ID}] Legend written: "
        f"{legend_output_file}"
    )

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
                font_family=p["font_family"]
            )

    except Exception as ex:

        logger.warning(
            f"[{VISUAL_ID}] parameter export failed: {ex}"
        )

    write_rdb = int(
        params.get(
            "write_rdb",
            0
        )
    )

    rdb_rows = []

    if write_rdb == 1:

        report_title = p["title"]

        for s, t, v in zip(
            sources,
            targets,
            values
        ):

            rdb_rows.append({
                "run_id": params.get("run_id"),
                "visual_id": VISUAL_ID,
                "client_name": params.get("client_name"),
                "domain": params.get("domain"),
                "cohort_id": params.get("cohort_id"),
                "domain_cohort":
                    f"{params.get('domain')}.{params.get('cohort_id')}",
                "dimension": "flow_stage",
                "dimension_value": node_names[s],
                "dimension_value_label": node_names[s],
                "secondary_dimension": "next_stage",
                "secondary_dimension_value": node_names[t],
                "metric": "patients",
                "metric_type": "count",
                "value": int(v),
                "start_date": start_date,
                "end_date": end_date,
                "report_title": report_title
            })

    logger.info(f"[{VISUAL_ID}] Complete")

    return {
        "output_path": output_file,
        "rdb": rdb_rows
    }