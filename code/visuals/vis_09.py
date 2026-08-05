# =============================================================================
# Domain      : ED (Emergency Department)
# Report Name : ED Patient Flow Sankey
#
# Description :
# Generates a patient flow visualization that traces Emergency Department
# encounters from arrival through triage, treatment, and final disposition.
# The report uses a Sankey diagram to illustrate patient movement between
# major stages of the ED care process and quantify the volume of patients
# progressing through each path.
#
# Patient flow is analyzed across the following stages:
#   - Arrival
#   - Triage
#   - No Triage
#   - Treatment
#   - Left Before Treatment 
#   - Final Disposition
#
# ED treatment encounters are further categorized by disposition:
#   - Discharge
#   - Inpatient Admission
#   - Observation
#   - Transfer
#   - Expired
#   - Exit Without Care
#
# The report provides a visual representation of patient progression,
# attrition points, and disposition outcomes, supporting workflow
# analysis, throughput assessment, process improvement initiatives,
# and operational planning.
#
# Inputs :
#   - arrival_dtm         : Facility arrival/visit datetime
#   - triage_start_dtm  : Triage start datetime
#   - tmt_start_dtm      : Facility treatment start datetime
#   - disch_disp_desc   : Facility discharge/disposition description
#   - start_date        : Reporting period start date
#   - end_date          : Reporting period end date
#
# Outputs :
#   - PNG Sankey diagram illustrating patient flow through the Facility
#   - RDB records containing:
#       * Arrival-to-triage flow counts
#       * Triage-to-treatment flow counts
#       * Left-before-treatment counts
#       * Facility disposition counts
#       * Patient flow stage transitions
#
# Key Metrics :
#   - Total arrivals
#   - Patients triaged
#   - Patients not triaged
#   - Patients reaching Facility treatment
#   - Patients leaving before treatment
#   - Discharge outcomes
#   - Inpatient admissions
#   - Observation placements
#   - Transfers
#   - Expired encounters
#   - Exit-without-care encounters
# =============================================================================

import os
import logging
import pandas as pd
import numpy as np

import plotly.graph_objects as go
from matplotlib.patches import Patch
from utils.vis_helpers import (
    crop_image,
    normalize_params,
    format_date_range,
    apply_axis_range,
    apply_yaxis_format,
    save_legend_png,
    format_display_value,
    get_display_parameters,
    save_parameter_table_png,
    save_title_png,
    map_disposition
)
from utils.date_helpers import prepare_dates
from utils.col_helpers import add_common_helper_columns

logger = logging.getLogger(__name__)

VISUAL_ID = "vis_09"

def run(df, params, start_date, end_date, output_dir, generate_output_name):
    logger.info(f"[{VISUAL_ID}] Starting execution")
    params = normalize_params(params)

    # -----------------------------
    # DEFAULT PARAMETERS
    # -----------------------------
    default_params = {
        "fig_width": 1200,
        "fig_height": 900,

        "title": "Facility Patient Flow Sankey",

        "font_family": "Arial",
        "node_font_size": 16,
        "title_font_size": 24,
        "title_x": 0.01,

        "top_anchor_y": 0.02,
        "cascade_start_offset": 0.12,
        "cascade_step": 0.08,

        # title image
        "title_width": 6.40,
        "title_height": 0.25,
        "subtitle_fontsize": 8,
        "title_background_color": "#d9d9d9",
        "title_weight": "bold",

        # legend image
        "legend_width": 6,
        "legend_height": 2,
        "legend_fontsize": 10,

        # output
        "dpi": 300
    }

    p = {**default_params, **(params or {})}

    # --------------------------------------------------
    # HELP MY DATAFRAME
    # --------------------------------------------------
    df = prepare_dates(df, start_date, end_date)
    df = add_common_helper_columns(df)

    required_cols = {
        "arrival_dtm",
        "has_triage",
        "has_ed",
        "disposition"
    }

    if df is None:
        logger.warning(f"[{VISUAL_ID}] Input dataframe is None. Skipping.")
        return

    missing = required_cols - set(df.columns)

    if missing:
        logger.warning(
            f"[{VISUAL_ID}] Missing required columns: {sorted(missing)}. Skipping."
        )
        return

    if df.empty:
        logger.warning(f"[{VISUAL_ID}] Input dataframe is empty. Skipping.")
        return

    df = df.copy()

    total_arrivals = len(df)

    triage_count = df["has_triage"].sum()
    no_triage_count = total_arrivals - triage_count

    triage_df = df[df["has_triage"]]
    ed_from_triage = triage_df["has_ed"].sum()
    left_before_ed = len(triage_df) - ed_from_triage

    ed_df = df[df["has_ed"]].copy()

    disp_counts = ed_df["disposition"].value_counts().to_dict()

    DISPOSITIONS = [
        "Discharge",
        "Inpatient",
        "Observation",
        "Transfer",
        "Exit w/o Care",
        "Expired",
        "Unknown"
    ]

    categories = DISPOSITIONS.copy()

    for c in categories:
        disp_counts.setdefault(c, 0)

    # -----------------------------
    # LABELS
    # -----------------------------
    def label(name, count):
        pct = count / total_arrivals if total_arrivals > 0 else 0

        if pct < float(p.get("label_min_pct", 0.0)):
            return f"<b>{name}</b>"

        return (
            f"<b>{name}</b><br>"
            f"<span style='color:#333'>"
            f"{count:,} (<b>{pct:.1%}</b>)"
            f"</span>"
        )

    node_counts = {
        "Arrival": total_arrivals,
        "Triage": triage_count,
        "No Triage": no_triage_count,
        "Treatment": ed_from_triage,
        "Left Before Treatment": left_before_ed,
        **disp_counts
    }

    FLOW_NODES = [
        "Arrival",
        "Triage",
        "No Triage",
        "Treatment",
        "Left Before Treatment",
        *DISPOSITIONS
    ]

    nodes = [
        label(node, node_counts.get(node, 0))
        for node in FLOW_NODES
    ]

    idx = {
        name: i
        for i, name in enumerate(FLOW_NODES)
    }

    # -----------------------------
    # COLOR SCALE (FIXED ORDERED FLOW)
    # -----------------------------

    blue_scale = [
        "#0B3C5D",
        "#0E4E73",
        "#145DA0",
        "#1B6FAF",
        "#1E81B0",
        "#2E8BC0",
        "#4BA3C7",
        "#76B5C5",
        "#9DCBE0",
        "#C3DDF0",
        "#E3F2FA",
        "#F2F8FC"
    ]

    # Define logical flow order (NOT tied to rendering order)
    ordered_flow = FLOW_NODES

    # Assign scale progressively
    color_map = {
        name: blue_scale[i]
        for i, name in enumerate(ordered_flow)
    }

    # Apply colors in ACTUAL node order (preserves layout)
    node_colors = [
        color_map.get(name, blue_scale[-1])
        for name in idx.keys()
    ]

    # -----------------------------
    # LINKS
    # -----------------------------
    sources, targets, values = [], [], []

    sources += [idx["Arrival"], idx["Arrival"]]
    targets += [idx["Triage"], idx["No Triage"]]
    values += [triage_count, no_triage_count]

    sources += [idx["Triage"], idx["Triage"]]
    targets += [idx["Treatment"], idx["Left Before Treatment"]]
    values += [ed_from_triage, left_before_ed]

    for c in categories:
        sources.append(idx["Treatment"])
        targets.append(idx[c])
        values.append(disp_counts[c])

    # -----------------------------
    # FIXED X POSITIONS
    # -----------------------------
    node_x_map = {
        "Arrival": 0.05,
        "Triage": 0.30,
        "No Triage": 0.30,
        "Treatment": 0.55,
        "Left Before Treatment": 0.45,
        "Discharge": 0.92,
        "Inpatient": 0.85,
        "Observation": 0.85,
        "Transfer": 0.85,
        "Exit w/o Care": 0.85,
        "Expired": 0.85,
        "Unknown": 0.85
    }

    node_x = [node_x_map.get(n, 0.5) for n in idx.keys()]

    # -----------------------------
    # Y POSITIONS (SIMPLIFIED)
    # -----------------------------
    TOP_Y = float(p["top_anchor_y"])

    n_nodes = len(nodes)
    node_y = [0.5] * n_nodes

    for node in ["Arrival", "Triage", "Treatment"]:
        node_y[idx[node]] = TOP_Y

    # Middle nodes
    node_y[idx["No Triage"]] = TOP_Y + 0.45
    node_y[idx["Left Before Treatment"]] = TOP_Y + 0.40

    disposition_y = {
        "Discharge": 0.01,
        "Inpatient": 0.75,
        "Observation": 0.82,
        "Transfer": 0.87,
        "Exit w/o Care": 0.91,
        "Expired": 0.95,
        "Unknown": 0.98
    }

    for disp, y in disposition_y.items():
        if disp in idx:
            node_y[idx[disp]] = y

    # -----------------------------
    # BUILD FIGURE
    # -----------------------------
    fig = go.Figure(data=[go.Sankey(
        arrangement="fixed",
        node=dict(
            pad=25,
            thickness=28,
            label=nodes,
            color=node_colors,   
            y=node_y,
            x=node_x
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color=["rgba(160,160,160,0.3)"] * len(values)
        )
    )])

    fig.update_layout(
        title=dict(
            text="",
            font=dict(
                size=int(p["title_font_size"]),
                family=p["font_family"],
                color=p.get("node_font_color", "#1a1a1a")
            ),
            x=float(p["title_x"]),
            y=0.02,          # ✅ push to bottom
            xanchor="left",
            yanchor="bottom"
        ),
        width=int(p["fig_width"]),
        height=int(p["fig_height"]),
        font=dict(
            size=int(p["node_font_size"]),
            family=p["font_family"]
        )
    )

    # -----------------------------
    # SAVE
    # -----------------------------
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

    crop_top_pct = float(
        p.get(
            "crop_top_pct",
            0
        )
    )

    crop_bottom_pct = float(
        p.get(
            "crop_bottom_pct",
            0
        )
    )

    crop_left_pct = float(
        p.get(
            "crop_left_pct",
            0
        )
    )

    crop_right_pct = float(
        p.get(
            "crop_right_pct",
            0
        )
    )

    if any(
        [
            crop_top_pct,
            crop_bottom_pct,
            crop_left_pct,
            crop_right_pct
        ]
    ):

        crop_image(output_file, crop_top=crop_top_pct, crop_bottom=crop_bottom_pct, crop_left=crop_left_pct, crop_right=crop_right_pct)

    logger.info(f"[{VISUAL_ID}] Output saved to {output_file}")

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
        title=p["title"],
        subtitle=date_range,
        output_file=title_output_file,
        width=float(p["title_width"]),
        height=float(p["title_height"]),
        dpi=int(p["dpi"]),
        font_family=p["font_family"],
        title_fontsize=int(p["title_font_size"]),
        subtitle_fontsize=int(p["subtitle_fontsize"]),
        background_color=p["title_background_color"],
        title_weight=p["title_weight"]
    )

    logger.info(
        f"[{VISUAL_ID}] Title written: "
        f"{title_output_file}"
    )

    legend_handles = []

    legend_labels = []

    legend_nodes = FLOW_NODES

    for node_name in legend_nodes:

        legend_handles.append(
            Patch(
                facecolor=color_map[node_name],
                edgecolor="black"
            )
        )

        legend_labels.append(node_name)

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
        ncol=2,
        font_family=p["font_family"],
        font_size=int(p["legend_fontsize"]),
        width=float(p["legend_width"]),
        height=float(p["legend_height"])
    )

    logger.info(
        f"[{VISUAL_ID}] Legend written: "
        f"{legend_output_file}"
    )

    # -----------------------------
    # RDB OUTPUT
    # -----------------------------
    write_rdb = int(params.get("write_rdb", 0))
    rdb_rows = []

    if write_rdb == 1:

        report_title = p["title"]

        flow_rows = [
            ("Arrival", "Triage", triage_count),
            ("Arrival", "No Triage", no_triage_count),
            ("Triage", "Treatment", ed_from_triage),
            ("Triage", "Left Before Treatment", left_before_ed)
        ]

        for source_node, target_node, value in flow_rows:

            rdb_rows.append({
                "run_id": params.get("run_id"),
                "visual_id": VISUAL_ID,
                "client_name": params.get("client_name"),

                "domain": params.get("domain"),
                "cohort_id": params.get("cohort_id"),

                "domain_cohort":
                    f"{params.get('domain')}.{params.get('cohort_id')}",

                "dimension": "flow_stage",
                "dimension_value": source_node,
                "dimension_value_label": source_node,

                "secondary_dimension": "next_stage",
                "secondary_dimension_value": target_node,

                "metric": "patients",
                "metric_type": "count",
                "value": int(value),

                "start_date": start_date,
                "end_date": end_date,

                "report_title": report_title
            })

        for disposition, count in disp_counts.items():

            rdb_rows.append({
                "run_id": params.get("run_id"),
                "visual_id": VISUAL_ID,
                "client_name": params.get("client_name"),

                "domain": params.get("domain"),
                "cohort_id": params.get("cohort_id"),

                "domain_cohort":
                    f"{params.get('domain')}.{params.get('cohort_id')}",

                "dimension": "flow_stage",
                "dimension_value": "Treatment",
                "dimension_value_label": "Treatment",

                "secondary_dimension": "disposition",
                "secondary_dimension_value": disposition,

                "metric": "patients",
                "metric_type": "count",
                "value": int(count),

                "start_date": start_date,
                "end_date": end_date,

                "report_title": report_title
            })

    return {
        "output_path": output_file,
        "rdb": rdb_rows
    }