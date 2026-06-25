import os
import logging
import pandas as pd
import numpy as np

import plotly.graph_objects as go
from utils.vis_helpers import format_date_range

logger = logging.getLogger(__name__)


def run(df, params, start_date, end_date, output_dir, generate_output_name):
    visual_id = "vis_09"
    logger.info(f"[{visual_id}] Starting execution")

    # -----------------------------
    # DEFAULT PARAMETERS
    # -----------------------------
    default_params = {
        "fig_width": 1200,
        "fig_height": 600,
        "title": "ED Patient Flow Sankey",
        "color_arrival": "#1f77b4",
        "color_triage": "#2ca02c",
        "color_no_triage": "#d62728",
        "color_ed": "#9467bd",
        "color_left_before_ed": "#ff7f0e",
        "color_discharge": "#8dd3c7",
        "color_inpatient": "#fb8072",
        "color_observation": "#80b1d3",
        "color_transfer": "#fdb462",
        "color_exit_without_care": "#b3de69",
        "color_expired": "#fccde5",
        "font_family": "Arial",
        "node_font_size": 10,
        "title_font_size": 16,
        "title_x": 0.01,   # left-align tweak
    }

    # Merge params
    p = {**default_params, **(params or {})}

    # -----------------------------
    # VALIDATION
    # -----------------------------
    required_cols = [
        "visit_dtm",
        "triage_start_dtm",
        "ed_start_dtm",
        "disch_disp_desc"
    ]

    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        logger.error(f"[{visual_id}] Missing required columns: {missing_cols}")
        return

    if df.empty:
        logger.warning(f"[{visual_id}] Input dataframe is empty")
        return

    df = df.copy()

    # -----------------------------
    # DATA PREPARATION
    # -----------------------------
    try:
        df["visit_dtm"] = pd.to_datetime(df["visit_dtm"], errors="coerce")
        df["triage_start_dtm"] = pd.to_datetime(df["triage_start_dtm"], errors="coerce")
        df["ed_start_dtm"] = pd.to_datetime(df["ed_start_dtm"], errors="coerce")
    except Exception as e:
        logger.error(f"[{visual_id}] Datetime conversion failed: {e}")
        return

    df = df.dropna(subset=["visit_dtm"])

    # Date filtering
    try:
        df = df[(df["visit_dtm"] >= pd.to_datetime(start_date)) &
                (df["visit_dtm"] <= pd.to_datetime(end_date))]
    except Exception:
        logger.warning(f"[{visual_id}] Date filtering skipped due to bad inputs")

    if df.empty:
        logger.warning(f"[{visual_id}] No data after filtering")
        return

    total_arrivals = len(df)

    # -----------------------------
    # STAGE CALCULATIONS
    # -----------------------------
    df["has_triage"] = df["triage_start_dtm"].notna()
    df["has_ed"] = df["ed_start_dtm"].notna()

    # Arrival → Triage
    triage_count = df["has_triage"].sum()
    no_triage_count = total_arrivals - triage_count

    # Triage → ED
    triage_df = df[df["has_triage"]]
    ed_from_triage = triage_df["has_ed"].sum()
    left_before_ed = len(triage_df) - ed_from_triage

    # -----------------------------
    # DISPOSITION MAPPING
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
        elif any(x in val for x in ["left", "ama", "lwbs"]):
            return "Exit Without Care"
        elif "expired" in val or "death" in val:
            return "Expired"
        else:
            return "Exit Without Care"

    ed_df = df[df["has_ed"]].copy()

    if ed_df.empty:
        logger.warning(f"[{visual_id}] No ED treatment encounters found")

    ed_df["disposition"] = ed_df["disch_disp_desc"].apply(map_disposition)

    disp_counts = ed_df["disposition"].value_counts().to_dict()

    # Ensure all categories exist
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

    # -----------------------------
    # NODE LABELS
    # -----------------------------
    def label(name, count):
        pct = count / total_arrivals if total_arrivals > 0 else 0

        if pct < float(p.get("label_min_pct", 0.02)):
            return f"<b>{name}</b>"

        return f"<b>{name}</b><br><span style='color:#333'>{count:,} ({pct*100:.1f}%)</span>"

    # Sort outcomes by size
    categories = sorted(categories, key=lambda x: -disp_counts[x])

    nodes = [
        label("Arrival", total_arrivals),
        label("Triage", triage_count),
        label("No Triage", no_triage_count),
        label("ED Treatment", ed_from_triage),
        label("Left Before ED", left_before_ed),
    ]

    # Add disposition nodes
    for c in categories:
        nodes.append(label(c, disp_counts[c]))

    # Node indices
    idx = {name: i for i, name in enumerate([
        "Arrival", "Triage", "No Triage",
        "ED Treatment", "Left Before ED",
        *categories
    ])}

    # -----------------------------
    # LINKS
    # -----------------------------
    sources = []
    targets = []
    values = []

    # Arrival flows
    sources += [idx["Arrival"], idx["Arrival"]]
    targets += [idx["Triage"], idx["No Triage"]]
    values += [triage_count, no_triage_count]

    # Triage flows
    sources += [idx["Triage"], idx["Triage"]]
    targets += [idx["ED Treatment"], idx["Left Before ED"]]
    values += [ed_from_triage, left_before_ed]

    # ED → Disposition
    for c in categories:
        sources.append(idx["ED Treatment"])
        targets.append(idx[c])
        values.append(disp_counts[c])

    # -----------------------------
    # COLORS
    # -----------------------------
    node_colors = [
        p["color_arrival"],
        p["color_triage"],
        p["color_no_triage"],
        p["color_ed"],
        p["color_left_before_ed"],
        p["color_discharge"],
        p["color_inpatient"],
        p["color_observation"],
        p["color_transfer"],
        p["color_exit_without_care"],
        p["color_expired"],
    ]

    link_colors = ["rgba(160,160,160,0.4)"] * len(values)

    node_x_positions = {
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

    node_x = [node_x_positions.get(n, 0.5) for n in idx.keys()]

    # -----------------------------
    # SANKEY PLOT
    # -----------------------------
    date_str = format_date_range(start_date, end_date)
    try:

        n_nodes = len(nodes)
        # Dynamic height
        base_height = int(p.get("fig_height", 600))
        dynamic_height = int(90 * len(categories))

        fig_height = max(base_height, dynamic_height)

        OPACITY = float(p.get("flow_opacity", 0.25))
        THICKNESS = int(p.get("node_thickness", 28))

        TOP_Y = float(p.get("top_anchor_y", 0.12))
        STEP = float(p.get("cascade_step", 0.10))

        node_y = [0.5] * n_nodes

        # ---------------------------------
        # LEFT + MIDDLE COLUMN STRUCTURE
        # ---------------------------------

        # ---------------------------------
        # SPINE ALIGNMENT (VISUAL CORRECTION)
        # ---------------------------------

        top_outcome = categories[0]
        node_y[idx[top_outcome]] = TOP_Y

        # Apply small upward correction for upstream nodes
        upstream_offset = float(p.get("spine_alignment_offset", 0.015))

        node_y[idx["ED Treatment"]] = TOP_Y + upstream_offset
        node_y[idx["Triage"]] = TOP_Y + upstream_offset
        node_y[idx["Arrival"]] = TOP_Y + upstream_offset

        # Secondary branches (must be BELOW their parents)
        node_y[idx["No Triage"]] = TOP_Y + 0.55
        node_y[idx["Left Before ED"]] = TOP_Y + 0.55

        # ---------------------------------
        # RIGHT-SIDE CASCADE (CONTINUOUS)
        # ---------------------------------

        top_outcome = categories[0]
        node_y[idx[top_outcome]] = TOP_Y

        remaining = categories[1:]

        if remaining:
            # ✅ Step 1: small controlled gap for first non-spinal node
            # ---------------------------------
            # CONTROLLED OFFSET FROM SPINE (FIX OVERLAP)
            # ---------------------------------

            # This offset approximates "bottom of Discharge + gap"
            # Ensures first node clears bottom of Discharge reliably
            level1_offset = float(p.get("cascade_level1_offset", 0.24))

            current_y = TOP_Y + level1_offset

            for i, c in enumerate(remaining):
                node_y[idx[c]] = min(current_y, 0.98)

                # ✅ Step 2: use consistent step for ALL remaining nodes
                current_y += float(p.get("cascade_step", 0.10))

        fig = go.Figure(data=[go.Sankey(
            arrangement="fixed",
            node=dict(
                pad=35,
                thickness=THICKNESS,
                label=nodes,
                color=node_colors,
                y=node_y,
                x=node_x   
            ),
            link=dict(
                source=sources,
                target=targets,
                value=values,
                color=["rgba(160,160,160,0.25)"] * len(values)
            )
        )])
        node_font_size = int(float(p["node_font_size"]) * 1.3)

        fig.update_layout(
            title=dict(
                text=f"{p['title']} {date_str}",
                font=dict(
                    size=int(p["title_font_size"]),
                    family=p["font_family"]
                ),
                x=float(p["title_x"])
            ),
            width=int(p["fig_width"]),
            height=fig_height,
            font=dict(
                size=node_font_size,
                family=p["font_family"],
                color=p.get("node_font_color", "#1a1a1a")
            )
        )

    except Exception as e:
        logger.error(f"[{visual_id}] Failed to construct Sankey: {e}")
        return

    # -----------------------------
    # SAVE OUTPUT
    # -----------------------------
    try:
        filename = generate_output_name(visual_id, start_date, end_date)
        filepath = os.path.join(output_dir, filename)

        fig.write_image(filepath)

        logger.info(f"[{visual_id}] Output saved to {filepath}")

    except Exception as e:
        logger.error(f"[{visual_id}] Failed to save image: {e}")
        return

    logger.info(f"[{visual_id}] Completed successfully")