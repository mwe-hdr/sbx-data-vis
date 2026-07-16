# =============================================================================
# Domain      : ED (Emergency Department)
# Report Name : ED Peak Census and Room Need by Acuity
#
# Description :
# Calculates Emergency Department peak census levels and estimated room
# requirements by Emergency Severity Index (ESI) acuity category.
# Patient census is derived from ED arrival and departure timestamps and
# grouped according to ESI classification levels to evaluate capacity
# requirements for distinct patient acuity populations.
#
# Census profiles are generated independently for each acuity category
# using a minute-level occupancy model. Average census by hour is calculated
# for each group and the highest hourly census value is identified as the
# peak operating census. Optional growth assumptions may be applied to
# projected demand volumes before capacity calculations are performed.
#
# Estimated room requirements are calculated by adjusting peak census
# values according to a user-defined target utilization rate, providing
# a planning benchmark for treatment space allocation across acuity levels.
#
# Key planning metrics include:
#   - Peak census by acuity
#   - Growth-adjusted peak census
#   - Estimated room need by acuity
#   - Total ED peak census
#   - Total ED room requirement
#
# This report supports:
#   - ED capacity planning
#   - Treatment room allocation analysis
#   - Acuity-specific demand assessment
#   - Space programming and facility planning
#   - Operational capacity benchmarking
#   - Growth forecasting and scenario planning
#
# Inputs :
#   - ed_start_dtm            : ED arrival/start datetime
#   - ed_stop_dtm             : ED departure/stop datetime
#   - esi                     : Emergency Severity Index acuity level
#   - start_date              : Reporting period start date/time
#   - end_date                : Reporting period end date/time
#   - variable_10_year_growth : Projected growth adjustment factor
#   - utilization             : Target operational utilization rate
#
# Outputs :
#   - PNG table displaying:
#       * Acuity category
#       * Peak census by acuity
#       * Estimated room need by acuity
#       * Grand total peak census
#       * Grand total room need
#
#   - RDB records containing:
#       * Peak census values by acuity
#       * Room need values by acuity
#       * Total ED benchmarks
#
# Key Metrics :
#   - Peak census by ESI level
#   - Growth-adjusted peak census
#   - Room need by acuity
#   - Total ED peak census
#   - Total ED room requirement
#   - Capacity utilization benchmark
# =============================================================================

import os
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from utils.vis_helpers import format_date_range, normalize_params

VISUAL_ID = "vis_11"
logger = logging.getLogger(__name__)


def _safe_param(params, key, default, cast_type=None):
    try:
        val = params.get(key, default)
        return cast_type(val) if cast_type else val
    except Exception:
        logger.warning(f"Invalid param for {key}; using default {default}")
        return default


def _generate_census(df, start_date, end_date):
    """
    Minimal vis_08-equivalent census generation.
    Builds hourly time-series census from encounter windows.
    """
    try:
        df = df.copy()

        # =========================================================
        # VALIDATION
        # =========================================================
        if not all(col in df.columns for col in ["ed_start_dtm", "ed_stop_dtm"]):
            logging.error(f"[{VISUAL_ID}] Missing required columns")
            return pd.DataFrame()

        # =========================================================
        # DATETIME PREP
        # =========================================================
        df["ed_start_dtm"] = pd.to_datetime(df["ed_start_dtm"], errors="coerce")
        df["ed_stop_dtm"] = pd.to_datetime(df["ed_stop_dtm"], errors="coerce")

        df = df.dropna(subset=["ed_start_dtm", "ed_stop_dtm"])

        invalid_mask = df["ed_stop_dtm"] < df["ed_start_dtm"]
        zero_mask = df["ed_stop_dtm"] == df["ed_start_dtm"]

        df.loc[invalid_mask, "ed_stop_dtm"] = (
            df.loc[invalid_mask, "ed_start_dtm"] + pd.Timedelta(minutes=1)
        )
        df.loc[zero_mask, "ed_stop_dtm"] = (
            df.loc[zero_mask, "ed_start_dtm"] + pd.Timedelta(minutes=1)
        )

        if "encounter_id" in df.columns:
            df = df.drop_duplicates(subset=["encounter_id"])

        # =========================================================
        # DATE RANGE
        # =========================================================
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        if end_date.hour == 0 and end_date.minute == 0 and end_date.second == 0:
            end_date = end_date + pd.Timedelta(days=1) - pd.Timedelta(minutes=1)

        # =========================================================
        # FILTER
        # =========================================================
        df = df[
            (df["ed_start_dtm"] <= end_date) &
            (df["ed_stop_dtm"] >= start_date)
        ].copy()

        if df.empty:
            logging.warning(f"[{VISUAL_ID}] No data after filtering")
            return

        # =========================================================
        # VISIT WINDOWS
        # =========================================================
        df["start"] = df["ed_start_dtm"]
        df["end"] = df["ed_stop_dtm"]

        df["end"] = df["end"].clip(lower=start_date, upper=end_date)
        df["end"] = df["end"] + pd.Timedelta(minutes=1)

        # =========================================================
        # TIME GRID
        # =========================================================
        intervals = pd.date_range(start=start_date, end=end_date, freq="min")
        base = pd.DataFrame({"interval": intervals})

        # =========================================================
        # EVENTS
        # =========================================================
        start_events = df[["start"]].rename(columns={"start": "interval"})
        start_events["delta"] = 1

        end_events = df[["end"]].rename(columns={"end": "interval"})
        end_events["delta"] = -1

        events = pd.concat([start_events, end_events])

        events = events[
            (events["interval"] >= start_date) &
            (events["interval"] <= end_date)
        ]

        events = (
            events.groupby("interval", as_index=False)["delta"]
            .sum()
            .sort_values("interval")
        )

        # =========================================================
        # MERGE + CENSUS
        # =========================================================
        ts = base.merge(events, on="interval", how="left")
        ts["delta"] = ts["delta"].fillna(0)

        initial_count = df[
            (df["ed_start_dtm"] < start_date) &
            (df["ed_stop_dtm"] >= start_date)
        ].shape[0]

        ts["census"] = ts["delta"].cumsum()
        ts["census"] += initial_count

        ts["census"] = (
            pd.to_numeric(ts["census"], errors="coerce")
            .round()
            .astype("Int64")
        )

        return ts

    except Exception as e:
        logger.error(f"Census generation failed: {e}")
        return pd.DataFrame()
    
def run(df, params, start_date, end_date, output_dir, generate_output_name):
    logger.info(f"[{VISUAL_ID}] Starting run")
    params = normalize_params(params)

    try:
        if df is None or df.empty:
            logger.warning("Input dataframe is empty")
            return
        
        ESI_LABELS = {
            0: "0-Unknown",
            1: "1-Immediate",
            2: "2-Emergent",
            3: "3-Urgent",
            4: "4-Less Urgent",
            5: "5-Non-Urgent"
        }

        # =========================
        # PARAMETERS
        # =========================
        utilization = _safe_param(params, "utilization", 0.85, float)
        growth = _safe_param(params, "variable_10_year_growth", 0.0, float)
        fig_width = _safe_param(params, "fig_width", 14, float)
        fig_height = _safe_param(params, "fig_height", 7, float)
        dpi = _safe_param(params, "dpi", 100, int)

        if "esi" not in df.columns:
            logger.error(f"[{VISUAL_ID}] Missing required column: esi")
            return

        df["esi"] = pd.to_numeric(df["esi"], errors="coerce")
        df["esi"] = df["esi"].fillna(0).astype(int)
        df["acuity_name"] = df["esi"].map(ESI_LABELS).fillna("0-Unknown")

        results = []

        for esi_value, group_df in df.groupby("acuity_name"):

            ts = _generate_census(
                group_df,
                start_date,
                end_date
            )

            if ts is None or ts.empty:
                continue

            ts["interval"] = pd.to_datetime(ts["interval"])

            ts["adj_census"] = ts["census"] * (1 + growth)

            ts["hour"] = ts["interval"].dt.hour

            hourly = (
                ts.groupby("hour")["adj_census"]
                .mean()
                .reindex(range(24), fill_value=0)
                .reset_index()
            )

            peak_census = hourly["adj_census"].max()

            room_need = (
                peak_census / utilization
                if utilization > 0
                else peak_census
            )

            results.append({
                "acuity_name": esi_value,
                "peak_census": peak_census,
                "room_need": room_need
            })

        ts_total = _generate_census(
            df,
            start_date,
            end_date
        )

        ts_total["adj_census"] = (
            ts_total["census"] * (1 + growth)
        )

        ts_total["hour"] = ts_total["interval"].dt.hour

        hourly_total = (
            ts_total.groupby("hour")["adj_census"]
            .mean()
            .reset_index()
        )

        grand_peak = hourly_total["adj_census"].max()

        grand_room_need = (
            grand_peak / utilization
            if utilization > 0
            else grand_peak
        )

        results.append({
            "acuity_name": "Grand Total",
            "peak_census": grand_peak,
            "room_need": grand_room_need
        })

        table_df = pd.DataFrame(results)

        sort_order = {
            "0-Unknown": 0,
            "1-Immediate": 1,
            "2-Emergent": 2,
            "3-Urgent": 3,
            "4-Less Urgent": 4,
            "5-Non-Urgent": 5,
            "Grand Total": 99
        }

        table_df["sort"] = table_df["acuity_name"].map(sort_order)

        table_df = (
            table_df
            .sort_values("sort")
            .drop(columns="sort")
        )

        fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)

        ax.axis("off")

        display_df = table_df.copy()

        display_df["peak_census"] = (
            display_df["peak_census"]
            .round(1)
        )

        display_df["room_need"] = (
            display_df["room_need"]
            .round(1)
        )

        col_widths = [
            float(params.get("table_col_width_acuity", 0.40)),
            float(params.get("table_col_width_peak", 0.25)),
            float(params.get("table_col_width_room", 0.25))
        ]

        tbl = ax.table(
            cellText=display_df.values,
            colLabels=[
                "Acuity Name",
                "ED Peak Census",
                "ED Room Need"
            ],
            colWidths=col_widths,
            loc="center"
        )

        tbl.auto_set_font_size(False)
        tbl.set_fontsize(
            _safe_param(
                params,
                "table_font_size",
                10,
                int
            )
        )

        tbl.scale(
            float(params.get("table_scale_x", 1.2)),
            float(params.get("table_scale_y", 1.5))
        )

        font_family = params.get(
            "table_font_family",
            "Arial"
        )

        for cell in tbl.get_celld().values():
            cell.get_text().set_fontfamily(font_family)

        header_color = params.get(
            "table_header_color",
            "#e8e8e8"
        )
        header_font_size = _safe_param(
            params,
            "table_header_font_size",
            12,
            int
        )
        for col in range(len(display_df.columns)):

            cell = tbl[(0, col)]

            cell.set_facecolor(header_color)

            cell.get_text().set_weight("bold")

            cell.get_text().set_fontsize(
                header_font_size
            )

        band_color = params.get(
            "table_band_color",
            "#f2f2f2"
        )

        grand_total_row = len(display_df)

        for row in range(1, grand_total_row):

            if row % 2 == 1:

                for col in range(len(display_df.columns)):

                    tbl[(row, col)].set_facecolor(
                        band_color
                    )

        grand_total_color = params.get(
            "table_grand_total_color",
            "#e6e6e6"
        )

        grand_total_row = len(display_df)

        for col in range(len(display_df.columns)):

            cell = tbl[(grand_total_row, col)]

            cell.set_facecolor(grand_total_color)

            cell.set_linewidth(1.0)

            cell.get_text().set_weight("bold")

        tbl[(0, 0)].get_text().set_ha("left")

        tbl[(0, 1)].get_text().set_ha("right")

        tbl[(0, 2)].get_text().set_ha("right")

        for row in range(1, len(display_df) + 1):

            tbl[(row, 0)].get_text().set_ha("left")

            tbl[(row, 1)].get_text().set_ha("right")

            tbl[(row, 2)].get_text().set_ha("right")

        border_color = params.get(
            "table_border_color",
            "#cccccc"
        )

        border_width = float(
            params.get(
                "table_border_width",
                0.4
            )
        )

        grand_total_border_width = float(
            params.get(
                "table_grand_total_border_width",
                1.0
            )
        )

        for cell in tbl.get_celld().values():

            cell.set_edgecolor(border_color)

            cell.set_linewidth(border_width)

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

        plt.tight_layout(pad=0.25)
        plt.savefig(output_file, bbox_inches="tight")
        plt.close()

        # =========================
        # RDB OUTPUT
        # =========================
        write_rdb = int(params.get("write_rdb", 0))
        rdb_rows = []

        if write_rdb == 1:

            report_title = "ED Peak Census and Room Need by Acuity"

            for _, row in table_df.iterrows():

                # Peak Census
                rdb_rows.append({
                    "run_id": params.get("run_id"),
                    "visual_id": VISUAL_ID,
                    "client_name": params.get("client_name"),

                    "domain": params.get("domain"),
                    "cohort_id": params.get("cohort_id"),

                    "domain_cohort":
                        f"{params.get('domain')}.{params.get('cohort_id')}",

                    "dimension": "acuity",
                    "dimension_value": row["acuity_name"],
                    "dimension_value_label": row["acuity_name"],

                    "secondary_dimension": None,
                    "secondary_dimension_value": None,

                    "metric": "peak_census",
                    "metric_type": "value",
                    "value": float(row["peak_census"]),

                    "start_date": start_date,
                    "end_date": end_date,

                    "report_title": report_title
                })

                # Room Need
                rdb_rows.append({
                    "run_id": params.get("run_id"),
                    "visual_id": VISUAL_ID,
                    "client_name": params.get("client_name"),

                    "domain": params.get("domain"),
                    "cohort_id": params.get("cohort_id"),

                    "domain_cohort":
                        f"{params.get('domain')}.{params.get('cohort_id')}",

                    "dimension": "acuity",
                    "dimension_value": row["acuity_name"],
                    "dimension_value_label": row["acuity_name"],

                    "secondary_dimension": None,
                    "secondary_dimension_value": None,

                    "metric": "room_need",
                    "metric_type": "value",
                    "value": float(row["room_need"]),

                    "start_date": start_date,
                    "end_date": end_date,

                    "report_title": report_title
                })

        logger.info(f"[{VISUAL_ID}] Output saved to {output_file}")

        return {
            "output_path": output_file,
            "rdb": rdb_rows
        }

    except Exception as e:
            logger.error(f"[{VISUAL_ID}] Execution failed: {e}")

