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
#   - ED Treatment
#   - Left Before ED Evaluation
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
#   - visit_dtm         : ED arrival/visit datetime
#   - triage_start_dtm  : Triage start datetime
#   - ed_start_dtm      : ED treatment start datetime
#   - disch_disp_desc   : ED discharge/disposition description
#   - start_date        : Reporting period start date
#   - end_date          : Reporting period end date
#
# Outputs :
#   - PNG Sankey diagram illustrating patient flow through the ED
#   - RDB records containing:
#       * Arrival-to-triage flow counts
#       * Triage-to-treatment flow counts
#       * Left-before-treatment counts
#       * ED disposition counts
#       * Patient flow stage transitions
#
# Key Metrics :
#   - Total arrivals
#   - Patients triaged
#   - Patients not triaged
#   - Patients reaching ED treatment
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
logger = logging.getLogger(__name__)


def run(df, params, start_date, end_date, output_dir, generate_output_name):
    visual_id = "vis_09"
    logger.info(f"[{visual_id}] Starting execution")
    params = normalize_params(params)

    # -----------------------------
    # DEFAULT PARAMETERS
    # -----------------------------
    default_params = {
        "fig_width": 1200,
        "fig_height": 900,
        "title": "ED Patient Flow Sankey",
        "font_family": "Arial",
        "node_font_size": 16,
        "title_font_size": 24,
        "title_x": 0.01,
        "top_anchor_y": 0.02,
        "cascade_start_offset": 0.12,
        "cascade_step": 0.08
    }

    p = {**default_params, **(params or {})}

    required_cols = {
        "visit_dtm",
        "triage_start_dtm",
        "ed_start_dtm",
        "disch_disp_desc"
    }

    if df is None:
        logger.warning(f"[{visual_id}] Input dataframe is None. Skipping.")
        return

    missing = required_cols - set(df.columns)

    if missing:
        logger.warning(
            f"[{visual_id}] Missing required columns: {sorted(missing)}. Skipping."
        )
        return

    if df.empty:
        logger.warning(f"[{visual_id}] Input dataframe is empty. Skipping.")
        return

    # -----------------------------
    # BASIC PREP
    # -----------------------------
    df = df.copy()
    df["visit_dtm"] = pd.to_datetime(df["visit_dtm"], errors="coerce")
    df["triage_start_dtm"] = pd.to_datetime(df["triage_start_dtm"], errors="coerce")
    df["ed_start_dtm"] = pd.to_datetime(df["ed_start_dtm"], errors="coerce")

    df = df.dropna(subset=["visit_dtm"])

    df = df[
        (df["visit_dtm"] >= pd.to_datetime(start_date)) &
        (df["visit_dtm"] <= pd.to_datetime(end_date))
    ]

    total_arrivals = len(df)

    df["has_triage"] = df["triage_start_dtm"].notna()
    df["has_ed"] = df["ed_start_dtm"].notna()

    triage_count = df["has_triage"].sum()
    no_triage_count = total_arrivals - triage_count

    triage_df = df[df["has_triage"]]
    ed_from_triage = triage_df["has_ed"].sum()
    left_before_ed = len(triage_df) - ed_from_triage

    # -----------------------------
    # DISPOSITION
    # -----------------------------
    def map_disposition(val):
        if pd.isna(val):
            return "Exit Without Care"
        val = str(val).lower()
        if "discharge" in val:
            return "Discharge"
        elif "admit" in val:
            return "Inpatient"
        elif "observation" in val:
            return "Observation"
        elif "transfer" in val:
            return "Transfer"
        elif "expired" in val:
            return "Expired"
        else:
            return "Exit Without Care"

    ed_df = df[df["has_ed"]].copy()
    ed_df["disposition"] = ed_df["disch_disp_desc"].apply(map_disposition)

    disp_counts = ed_df["disposition"].value_counts().to_dict()

    categories = [
        "Discharge",
        "Inpatient",
        "Observation",
        "Transfer",
        "Exit Without Care",
        "Expired"
    ]

    for c in categories:
        disp_counts.setdefault(c, 0)

    categories = sorted(categories, key=lambda x: -disp_counts[x])

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

    nodes = [
        label("Arrival", total_arrivals),
        label("Triage", triage_count),
        label("No Triage", no_triage_count),
        label("ED Treatment", ed_from_triage),
        label("Left Before ED", left_before_ed),
    ]

    for c in categories:
        nodes.append(label(c, disp_counts[c]))

    idx = {name: i for i, name in enumerate([
        "Arrival", "Triage", "No Triage",
        "ED Treatment", "Left Before ED",
        *categories
    ])}

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
        "#E3F2FA"   
    ]

    # Define logical flow order (NOT tied to rendering order)
    ordered_flow = [
        "Arrival",
        "Triage",
        "ED Treatment",
        "Discharge",
        "Inpatient",
        "Observation",
        "Transfer",
        "Exit Without Care",
        "Expired",
        "Left Before ED",
        "No Triage"
    ]

    # Assign scale progressively
    color_map = {}
    for i, name in enumerate(ordered_flow):
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
    targets += [idx["ED Treatment"], idx["Left Before ED"]]
    values += [ed_from_triage, left_before_ed]

    for c in categories:
        sources.append(idx["ED Treatment"])
        targets.append(idx[c])
        values.append(disp_counts[c])

    # -----------------------------
    # FIXED X POSITIONS
    # -----------------------------
    node_x_map = {
        "Arrival": 0.05,
        "Triage": 0.30,
        "No Triage": 0.30,
        "ED Treatment": 0.55,
        "Left Before ED": 0.45,
        "Discharge": 0.85,
        "Inpatient": 0.85,
        "Observation": 0.85,
        "Transfer": 0.85,
        "Exit Without Care": 0.85,
        "Expired": 0.85
    }

    node_x = [node_x_map.get(n, 0.5) for n in idx.keys()]

    # -----------------------------
    # Y POSITIONS (SIMPLIFIED)
    # -----------------------------
    TOP_Y = float(p["top_anchor_y"])

    n_nodes = len(nodes)
    node_y = [0.5] * n_nodes

    # Top spine (HARD LOCK)
    for node in ["Arrival", "Triage", "ED Treatment", categories[0]]:
        node_y[idx[node]] = TOP_Y

    # Middle nodes
    node_y[idx["No Triage"]] = TOP_Y + 0.45
    node_y[idx["Left Before ED"]] = TOP_Y + 0.40

    # ---------------------------------
    # RIGHT-SIDE CASCADE (EVEN SPACING)
    # ---------------------------------

    remaining = categories[1:]

    if remaining:
        start_y = TOP_Y + float(p["cascade_start_offset"])
        end_y = 0.90  # leave bottom margin for title

        positions = np.linspace(start_y, end_y, len(remaining))

        for c, y in zip(remaining, positions):
            node_y[idx[c]] = y

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
            text=f"{p['title']} {format_date_range(start_date, end_date)}",
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
            visual_id=visual_id,
            start_date=start_date,
            end_date=end_date,
            cohort_id=params.get("cohort_id"),
            ext="png"
        )
    )

    fig.write_image(output_file)

    logger.info(f"[{visual_id}] Output saved to {output_file}")

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
            ("Triage", "ED Treatment", ed_from_triage),
            ("Triage", "Left Before ED", left_before_ed)
        ]

        for source_node, target_node, value in flow_rows:

            rdb_rows.append({
                "run_id": params.get("run_id"),
                "visual_id": visual_id,
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
                "visual_id": visual_id,
                "client_name": params.get("client_name"),

                "domain": params.get("domain"),
                "cohort_id": params.get("cohort_id"),

                "domain_cohort":
                    f"{params.get('domain')}.{params.get('cohort_id')}",

                "dimension": "flow_stage",
                "dimension_value": "ED Treatment",
                "dimension_value_label": "ED Treatment",

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