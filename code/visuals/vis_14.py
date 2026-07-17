# =============================================================================
# Domain      : ED (Emergency Department)
# Report Name : ED ESI Mix Scenario Simulator
#
# Description :
# Scenario planning model that evaluates operational impacts of changes
# in Emergency Severity Index (ESI) distribution while preserving
# observed ED LOS characteristics.
#
# Generates:
#   1. Detailed ESI census comparison table
#   2. Scenario assumptions table
#   3. Executive summary table
#
# Outputs:
#   vis_14.png
#   vis_14_parameters.png
#   vis_14_summary.png
#
# =============================================================================

import os
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from utils.vis_helpers import normalize_params

VISUAL_ID = "vis_14"

logger = logging.getLogger(__name__)


def _safe_param(params, key, default, cast_type=None):
    try:
        val = params.get(key, default)
        return cast_type(val) if cast_type else val
    except Exception:
        logger.warning(
            f"Invalid param for {key}; using default {default}"
        )
        return default


def _generate_census(df, start_date, end_date):

    try:

        df = df.copy()

        if not all(
            c in df.columns
            for c in ["ed_start_dtm", "ed_stop_dtm"]
        ):
            return pd.DataFrame()

        df["ed_start_dtm"] = pd.to_datetime(
            df["ed_start_dtm"],
            errors="coerce"
        )

        df["ed_stop_dtm"] = pd.to_datetime(
            df["ed_stop_dtm"],
            errors="coerce"
        )

        df = df.dropna(
            subset=[
                "ed_start_dtm",
                "ed_stop_dtm"
            ]
        )

        invalid_mask = (
            df["ed_stop_dtm"]
            < df["ed_start_dtm"]
        )

        zero_mask = (
            df["ed_stop_dtm"]
            == df["ed_start_dtm"]
        )

        df.loc[invalid_mask, "ed_stop_dtm"] = (
            df.loc[invalid_mask, "ed_start_dtm"]
            + pd.Timedelta(minutes=1)
        )

        df.loc[zero_mask, "ed_stop_dtm"] = (
            df.loc[zero_mask, "ed_start_dtm"]
            + pd.Timedelta(minutes=1)
        )

        if "encounter_id" in df.columns:
            df = df.drop_duplicates(
                subset=["encounter_id"]
            )

        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        if (
            end_date.hour == 0
            and end_date.minute == 0
            and end_date.second == 0
        ):
            end_date = (
                end_date
                + pd.Timedelta(days=1)
                - pd.Timedelta(minutes=1)
            )

        df = df[
            (df["ed_start_dtm"] <= end_date)
            &
            (df["ed_stop_dtm"] >= start_date)
        ].copy()

        if df.empty:
            return pd.DataFrame()

        df["start"] = df["ed_start_dtm"]
        df["end"] = df["ed_stop_dtm"]

        df["end"] = df["end"].clip(
            lower=start_date,
            upper=end_date
        )

        df["end"] = (
            df["end"]
            + pd.Timedelta(minutes=1)
        )

        intervals = pd.date_range(
            start=start_date,
            end=end_date,
            freq="min"
        )

        base = pd.DataFrame(
            {"interval": intervals}
        )

        start_events = (
            df[["start"]]
            .rename(
                columns={"start": "interval"}
            )
        )

        start_events["delta"] = 1

        end_events = (
            df[["end"]]
            .rename(
                columns={"end": "interval"}
            )
        )

        end_events["delta"] = -1

        events = pd.concat(
            [start_events, end_events]
        )

        events = events.groupby(
            "interval",
            as_index=False
        )["delta"].sum()

        ts = base.merge(
            events,
            how="left",
            on="interval"
        )

        ts["delta"] = (
            ts["delta"]
            .fillna(0)
        )

        initial_count = df[
            (df["ed_start_dtm"] < start_date)
            &
            (df["ed_stop_dtm"] >= start_date)
        ].shape[0]

        ts["census"] = (
            ts["delta"].cumsum()
            + initial_count
        )

        return ts

    except Exception as e:

        logger.error(
            f"Census generation failed: {e}"
        )

        return pd.DataFrame()


def _build_table(
    dataframe,
    output_file,
    params,
    col_widths,
    fig_width=None,
    fig_height=None
):

    if fig_width is None:

        fig_width = _safe_param(
            params,
            "fig_width",
            14,
            float
        )

    if fig_height is None:

        fig_height = _safe_param(
            params,
            "fig_height",
            7,
            float
        )

    dpi = _safe_param(
        params,
        "dpi",
        100,
        int
    )

    font_family = params.get(
        "table_font_family",
        "Segoe UI"
    )

    plt.rcParams["font.family"] = font_family

    fig, ax = plt.subplots(
        figsize=(fig_width, fig_height),
        dpi=dpi
    )

    ax.axis("off")

    tbl = ax.table(
        cellText=dataframe.values,
        colLabels=list(dataframe.columns),
        colWidths=col_widths,
        loc="center"
    )

    tbl.auto_set_font_size(False)

    tbl.set_fontsize(
        int(
            params.get(
                "table_font_size",
                10
            )
        )
    )

    tbl.scale(
        float(
            params.get(
                "table_scale_x",
                1.2
            )
        ),
        float(
            params.get(
                "table_scale_y",
                1.5
            )
        )
    )

    for cell in tbl.get_celld().values():
        cell.get_text().set_fontfamily(
            font_family
        )

    header_color = params.get(
        "table_header_color",
        "#e8e8e8"
    )

    band_color = params.get(
        "table_band_color",
        "#f2f2f2"
    )

    grand_color = params.get(
        "table_grand_total_color",
        "#e6e6e6"
    )

    for col in range(len(dataframe.columns)):
        cell = tbl[(0, col)]
        cell.set_facecolor(header_color)
        cell.get_text().set_weight("bold")

    grand_row = len(dataframe)

    for row in range(1, grand_row):

        if row % 2 == 1:

            for col in range(len(dataframe.columns)):
                tbl[(row, col)].set_facecolor(
                    band_color
                )

    for col in range(len(dataframe.columns)):
        tbl[(grand_row, col)].set_facecolor(
            grand_color
        )

        tbl[(grand_row, col)].get_text().set_weight(
            "bold"
        )

    plt.tight_layout(pad=0.25)

    plt.savefig(
        output_file,
        bbox_inches="tight"
    )

    plt.close()


def run(
    df,
    params,
    start_date,
    end_date,
    output_dir,
    generate_output_name
):

    logger.info(
        f"[{VISUAL_ID}] Starting run"
    )

    params = normalize_params(params)

    try:

        if df is None or df.empty:
            return

        if "esi" not in df.columns:
            logger.error(
                f"[{VISUAL_ID}] Missing esi column"
            )
            return

        utilization = _safe_param(
            params,
            "utilization",
            0.85,
            float
        )

        growth = _safe_param(
            params,
            "variable_10_year_growth",
            0.0,
            float
        )

        factor_map = {
            1: _safe_param(params, "esi1_volume_factor", 1.0, float),
            2: _safe_param(params, "esi2_volume_factor", 1.0, float),
            3: _safe_param(params, "esi3_volume_factor", 1.0, float),
            4: _safe_param(params, "esi4_volume_factor", 1.0, float),
            5: _safe_param(params, "esi5_volume_factor", 1.0, float)
        }

        ESI_LABELS = {
            1: "1-Immediate",
            2: "2-Emergent",
            3: "3-Urgent",
            4: "4-Less Urgent",
            5: "5-Non-Urgent"
        }

        df["esi"] = pd.to_numeric(
            df["esi"],
            errors="coerce"
        )

        results = []

        current_total = 0
        scenario_total = 0

        scenario_frames = []

        for esi in [1, 2, 3, 4, 5]:

            group_df = df[
                df["esi"] == esi
            ].copy()

            if group_df.empty:

                current_avg = 0
                scenario_avg = 0
                scenario_df = pd.DataFrame()

            else:

                ts_current = _generate_census(
                    group_df,
                    start_date,
                    end_date
                )

                ts_current["adj_census"] = (
                    ts_current["census"]
                    * (1 + growth)
                )

                current_avg = (
                    ts_current["adj_census"]
                    .mean()
                )

                multiplier = factor_map[esi]

                if multiplier <= 1:

                    scenario_df = group_df.sample(
                        frac=multiplier,
                        replace=False,
                        random_state=42
                    )

                else:

                    extra = group_df.sample(
                        n=int(
                            len(group_df)
                            * (multiplier - 1)
                        ),
                        replace=True,
                        random_state=42
                    )

                    scenario_df = pd.concat(
                        [group_df, extra],
                        ignore_index=True
                    )

                scenario_ts = _generate_census(
                    scenario_df,
                    start_date,
                    end_date
                )

                scenario_ts["adj_census"] = (
                    scenario_ts["census"]
                    * (1 + growth)
                )

                scenario_avg = (
                    scenario_ts["adj_census"]
                    .mean()
                )

                logger.info(
                    f"ESI {esi} "
                    f"multiplier={multiplier:.2f} "
                    f"current_rows={len(group_df):,} "
                    f"scenario_rows={len(scenario_df):,}"
                )

                scenario_frames.append(
                    scenario_df
                )

            diff = (
                scenario_avg
                - current_avg
            )

            pct = (
                diff / current_avg * 100
                if current_avg > 0
                else 0
            )

            current_total += current_avg
            scenario_total += scenario_avg

            results.append({
                "ESI Category": ESI_LABELS[esi],
                "Current Census": round(current_avg, 1),
                "Scenario Census": round(scenario_avg, 1),
                "Δ Census": round(diff, 1),
                "Δ %": f"{pct:.1f}%"
            })

        total_diff = (
            scenario_total
            - current_total
        )

        total_pct = (
            total_diff
            / current_total
            * 100
            if current_total > 0
            else 0
        )

        logger.info(
            f"Census Totals | "
            f"Current={current_total:.2f} | "
            f"Scenario={scenario_total:.2f} | "
            f"Difference={total_diff:.2f}"
        )

        results.append({
            "ESI Category": "Grand Total",
            "Current Census": round(current_total, 1),
            "Scenario Census": round(scenario_total, 1),
            "Δ Census": round(total_diff, 1),
            "Δ %": f"{total_pct:.1f}%"
        })

        detail_df = pd.DataFrame(results)

        full_current_ts = _generate_census(
            df,
            start_date,
            end_date
        )

        current_peak = (
            full_current_ts["census"]
            * (1 + growth)
        ).max()

        scenario_all = pd.concat(
            scenario_frames,
            ignore_index=True
        )

        logger.info(
            f"Current encounters: {len(df):,}"
        )

        logger.info(
            f"Scenario encounters: {len(scenario_all):,}"
        )

        scenario_ts = _generate_census(
            scenario_all,
            start_date,
            end_date
        )

        scenario_peak = (
            scenario_ts["census"]
            * (1 + growth)
        ).max()

        logger.info(
            f"Peak Census | "
            f"Current={current_peak:.2f} | "
            f"Scenario={scenario_peak:.2f}"
        )

        current_room = (
            current_peak
            / utilization
        )

        scenario_room = (
            scenario_peak
            / utilization
        )

        logger.info(
            f"Room Need | "
            f"Current={current_room:.2f} | "
            f"Scenario={scenario_room:.2f} | "
            f"Utilization={utilization:.2%}"
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

        detail_col_widths = [
            float(params.get("table_col_width_acuity", 0.35)),
            float(params.get("table_col_width_current", 0.16)),
            float(params.get("table_col_width_scenario", 0.16)),
            float(params.get("table_col_width_difference", 0.16)),
            float(params.get("table_col_width_percent", 0.17))
        ]

        _build_table(
            detail_df,
            output_file,
            params,
            detail_col_widths,
            fig_width=float(
                params.get(
                    "detail_fig_width",
                    14
                )
            ),
            fig_height=float(
                params.get(
                    "detail_fig_height",
                    7
                )
            )
        )

        parameter_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id=f"{VISUAL_ID}_parameters",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        parameter_df = pd.DataFrame({
            "Scenario Parameter": [
                "ESI 1 Volume Multiplier",
                "ESI 2 Volume Multiplier",
                "ESI 3 Volume Multiplier",
                "ESI 4 Volume Multiplier",
                "ESI 5 Volume Multiplier",
                "Growth Factor",
                "Utilization Target"
            ],
            "Value": [
                f"{factor_map[1] * 100:.0f}%",
                f"{factor_map[2] * 100:.0f}%",
                f"{factor_map[3] * 100:.0f}%",
                f"{factor_map[4] * 100:.0f}%",
                f"{factor_map[5] * 100:.0f}%",
                f"{growth * 100:.0f}%",
                f"{utilization * 100:.0f}%"
            ]
        })

        parameter_col_widths = [
            float(params.get(
                "parameter_col_width_name",
                0.70
            )),
            float(params.get(
                "parameter_col_width_value",
                0.30
            ))
        ]

        _build_table(
            parameter_df,
            parameter_output_file,
            params,
            parameter_col_widths,
            fig_width=float(
                params.get(
                    "parameter_fig_width",
                    10
                )
            ),
            fig_height=float(
                params.get(
                    "parameter_fig_height",
                    5
                )
            )
        )

        logger.info(
            f"[{VISUAL_ID}] Parameter table saved to "
            f"{parameter_output_file}"
        )

        summary_df = pd.DataFrame({
            "Metric": [
                "Total Census",
                "Peak Census",
                "Room Need"
            ],
            "Current": [
                round(current_total, 1),
                round(current_peak, 1),
                round(current_room, 1)
            ],
            "Scenario": [
                round(scenario_total, 1),
                round(scenario_peak, 1),
                round(scenario_room, 1)
            ]
        })

        summary_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id=f"{VISUAL_ID}_summary",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        summary_col_widths = [
            float(params.get(
                "summary_col_width_metric",
                0.50
            )),
            float(params.get(
                "summary_col_width_current",
                0.25
            )),
            float(params.get(
                "summary_col_width_scenario",
                0.25
            ))
        ]

        _build_table(
            summary_df,
            summary_output_file,
            params,
            summary_col_widths,
            fig_width=float(
                params.get(
                    "summary_fig_width",
                    10
                )
            ),
            fig_height=float(
                params.get(
                    "summary_fig_height",
                    4
                )
            )
        )

        logger.info(
            f"[{VISUAL_ID}] Exec Summary Table saved to "
            f"{summary_output_file}"
        )

        rdb_rows = []

        if int(params.get("write_rdb", 0)) == 1:

            report_title = (
                "ED ESI Mix Scenario Simulator"
            )

            for esi, factor in factor_map.items():

                rdb_rows.append({
                    "run_id": params.get("run_id"),
                    "visual_id": VISUAL_ID,
                    "metric": "scenario_multiplier",
                    "dimension": "acuity",
                    "dimension_value":
                        ESI_LABELS[esi],
                    "value": factor,
                    "report_title":
                        report_title
                })

            for _, row in detail_df.iterrows():

                acuity = row["ESI Category"]

                rdb_rows.extend([
                    {
                        "metric": "current_census",
                        "dimension": "acuity",
                        "dimension_value": acuity,
                        "value": row["Current Census"]
                    },
                    {
                        "metric": "scenario_census",
                        "dimension": "acuity",
                        "dimension_value": acuity,
                        "value": row["Scenario Census"]
                    },
                    {
                        "metric": "census_difference",
                        "dimension": "acuity",
                        "dimension_value": acuity,
                        "value": row["Δ Census"]
                    }
                ])

            summary_metrics = {
                "total_census":
                    scenario_total,
                "peak_census":
                    scenario_peak,
                "room_need":
                    scenario_room,
                "utilization":
                    utilization,
                "growth_factor":
                    growth
            }

            for metric, value in summary_metrics.items():

                rdb_rows.append({
                    "metric": metric,
                    "value": float(value)
                })

        logger.info(
            f"[{VISUAL_ID}] Scenario table saved to "
            f"{output_file}"
        )

        return {
            "output_path": output_file,
            "rdb": rdb_rows
        }

    except Exception as e:

        logger.error(
            f"[{VISUAL_ID}] Execution failed: {e}"
        )