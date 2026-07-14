import os
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from utils.vis_helpers import (
    format_date_range,
    normalize_params,
    save_parameter_table_png,
    save_legend_png
)

VISUAL_ID = "vis_15"

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


def run(
    df,
    params,
    start_date,
    end_date,
    output_dir,
    generate_output_name
):
    logger.info(f"[{VISUAL_ID}] Starting run")

    params = normalize_params(params)

    try:

        if df is None or df.empty:
            logger.warning(f"[{VISUAL_ID}] Input dataframe is empty")
            return

        required_cols = [
            "esi",
            "ed_start_dtm",
            "ed_stop_dtm"
        ]

        missing = [
            c for c in required_cols
            if c not in df.columns
        ]

        if missing:
            logger.error(
                f"[{VISUAL_ID}] Missing required columns: {missing}"
            )
            return

        # =====================================================
        # PARAMETERS
        # =====================================================

        fig_width = _safe_param(
            params,
            "fig_width",
            12,
            float
        )

        fig_height = _safe_param(
            params,
            "fig_height",
            8,
            float
        )

        dpi = _safe_param(
            params,
            "dpi",
            300,
            int
        )

        positive_color = _safe_param(
            params,
            "positive_color",
            "#4E79A7"
        )

        total_color = _safe_param(
            params,
            "total_color",
            "#E15759"
        )

        label_fontsize = _safe_param(
            params,
            "label_fontsize",
            8,
            int
        )

        table_fontsize = _safe_param(
            params,
            "table_fontsize",
            8,
            int
        )

        volume_decimals = _safe_param(
            params,
            "volume_decimals",
            0,
            int
        )

        occupancy_decimals = _safe_param(
            params,
            "occupancy_decimals",
            1,
            int
        )

        volume_thousands_separator = _safe_param(
            params,
            "volume_thousands_separator",
            1,
            int
        )

        occupancy_thousands_separator = _safe_param(
            params,
            "occupancy_thousands_separator",
            1,
            int
        )

        # =====================================================
        # DATA PREP
        # =====================================================

        df = df.copy()

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

        df["esi"] = (
            pd.to_numeric(
                df["esi"],
                errors="coerce"
            )
            .fillna(0)
            .astype(int)
        )

        df = df[df["esi"].isin([1, 2, 3, 4, 5])]

        if df.empty:
            logger.warning(
                f"[{VISUAL_ID}] No valid ESI records"
            )
            return

        los_hours = (
            (
                df["ed_stop_dtm"] -
                df["ed_start_dtm"]
            )
            .dt.total_seconds()
            / 3600
        )

        los_hours = los_hours.clip(lower=0.0167)

        df["los_hours"] = los_hours

        # =====================================================
        # AGGREGATION
        # =====================================================

        rows = []

        for esi in [1, 2, 3, 4, 5]:

            subset = df[df["esi"] == esi]

            volume = len(subset)

            avg_los = (
                subset["los_hours"].mean()
                if volume > 0
                else 0
            )

            contribution = volume * avg_los

            rows.append(
                {
                    "esi": f"ESI {esi}",
                    "volume": volume,
                    "average_los": avg_los,
                    "occupancy_contribution": contribution
                }
            )

        table_df = pd.DataFrame(rows)

        total_volume = table_df["volume"].sum()

        total_occupancy = (
            table_df["occupancy_contribution"]
            .sum()
        )

        table_df["percent_volume"] = np.where(
            total_volume > 0,
            table_df["volume"] / total_volume * 100,
            0
        )

        table_df["percent_contribution"] = np.where(
            total_occupancy > 0,
            table_df["occupancy_contribution"]
            / total_occupancy
            * 100,
            0
        )

        table_df["cumulative"] = (
            table_df["occupancy_contribution"]
            .cumsum()
        )

        dominant_esi = (
            table_df.sort_values(
                "occupancy_contribution",
                ascending=False
            )
            .iloc[0]["esi"]
        )

        total_row = pd.DataFrame([
            {
                "esi": "Total",
                "volume": total_volume,
                "percent_volume": 100.0,
                "average_los": df["los_hours"].mean(),
                "occupancy_contribution": total_occupancy,
                "percent_contribution": 100.0
            }
        ])

        display_table = pd.concat(
            [table_df, total_row],
            ignore_index=True
        )

        # =====================================================
        # FIGURE
        # =====================================================

        fig = plt.figure(
            figsize=(fig_width, fig_height),
            dpi=dpi
        )

        gs = fig.add_gridspec(
            2,
            1,
            height_ratios=[2.2, 1.0]
        )

        ax = fig.add_subplot(gs[0])

        categories = list(table_df["esi"]) + ["Total"]

        starts = [0]

        running = 0

        for val in table_df["occupancy_contribution"]:
            starts.append(running)
            running += val

        starts = starts[:-1]

        for idx, row in table_df.iterrows():

            value = row["occupancy_contribution"]

            ax.bar(
                idx,
                value,
                bottom=starts[idx],
                color=positive_color
            )

            value_fmt = (
                f"{value:,.{occupancy_decimals}f}"
                if occupancy_thousands_separator
                else f"{value:.{occupancy_decimals}f}"
            )

            ax.text(
                idx,
                starts[idx] + value,
                (
                    f"{value_fmt}\n"
                    f"{row['percent_contribution']:.1f}%"
                ),
                ha="center",
                va="bottom",
                fontsize=label_fontsize
            )

        ax.bar(
            len(table_df),
            total_occupancy,
            color=total_color
        )

        total_fmt = (
            f"{total_occupancy:,.{occupancy_decimals}f}"
            if occupancy_thousands_separator
            else f"{total_occupancy:.{occupancy_decimals}f}"
        )

        ax.text(
            len(table_df),
            total_occupancy,
            total_fmt,
            ha="center",
            va="bottom",
            fontsize=label_fontsize,
            fontweight="bold"
        )

        ax.set_xticks(
            range(len(categories))
        )

        ax.set_xticklabels(
            categories
        )

        ax.set_ylabel(
            "Occupancy Contribution"
        )

        ax.set_title(
            "Occupancy Waterfall by Acuity",
            pad=25
        )

        subtitle = (
            f"{format_date_range(start_date, end_date)}"
            if callable(format_date_range)
            else f"{start_date} - {end_date}"
        )

        ax.text(
            0.5,
            1.01,
            subtitle,
            transform=ax.transAxes,
            ha="center",
            fontsize=10
        )

        ax.set_ylabel(
            "% Occupancy Contribution"
        )

        # =====================================================
        # TABLE
        # =====================================================

        table_ax = fig.add_subplot(gs[1])

        table_ax.axis("off")

        table_display = display_table.copy()

        if volume_thousands_separator:

            table_display["volume"] = (
                table_display["volume"]
                .apply(
                    lambda x:
                    f"{x:,.{volume_decimals}f}"
                )
            )

        else:

            table_display["volume"] = (
                table_display["volume"]
                .apply(
                    lambda x:
                    f"{x:.{volume_decimals}f}"
                )
            )

        table_display["percent_volume"] = (
            table_display["percent_volume"]
            .round(1)
            .astype(str)
            + "%"
        )

        table_display["average_los"] = (
            table_display["average_los"]
            .round(2)
        )

        if occupancy_thousands_separator:

            table_display["occupancy_contribution"] = (
                table_display["occupancy_contribution"]
                .apply(
                    lambda x:
                    f"{x:,.{occupancy_decimals}f}"
                )
            )

        else:

            table_display["occupancy_contribution"] = (
                table_display["occupancy_contribution"]
                .apply(
                    lambda x:
                    f"{x:.{occupancy_decimals}f}"
                )
            )

        table_display["percent_contribution"] = (
            table_display["percent_contribution"]
            .round(1)
            .astype(str)
            + "%"
        )

        tbl = table_ax.table(
            cellText=table_display[
                [
                    "esi",
                    "volume",
                    "percent_volume",
                    "average_los",
                    "occupancy_contribution",
                    "percent_contribution",

                ]
            ].values,
            colLabels=[
                "ESI",
                "Volume",
                "% Volume",
                "Average LOS",
                "Occupancy Contribution",
                "% Contribution"
            ],
            loc="center"
        )

        tbl.auto_set_font_size(False)
        tbl.set_fontsize(table_fontsize)
        tbl.scale(1.0, 1.35)

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
            bbox_inches="tight"
        )

        plt.close()

        # =====================================================
        # PARAMETER IMAGE
        # =====================================================

        try:
            save_parameter_table_png(
                params=params,
                visual_id=VISUAL_ID,
                output_dir=output_dir,
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                generate_output_name=generate_output_name
            )
        except Exception as e:
            logger.warning(
                f"Parameter image generation failed: {e}"
            )

        # =====================================================
        # LEGEND
        # =====================================================

        try:

            legend_items = [
                (
                    positive_color,
                    "ESI Occupancy Contribution"
                ),
                (
                    total_color,
                    "Total Occupancy"
                )
            ]

            save_legend_png(
                legend_items=legend_items,
                visual_id=VISUAL_ID,
                output_dir=output_dir,
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                generate_output_name=generate_output_name
            )

        except Exception as e:
            logger.warning(
                f"Legend generation failed: {e}"
            )

        # =====================================================
        # RDB
        # =====================================================

        write_rdb = int(
            params.get(
                "write_rdb",
                0
            )
        )

        rdb_rows = []

        if write_rdb == 1:

            report_title = (
                "Occupancy Waterfall by Acuity"
            )

            for _, row in table_df.iterrows():

                metrics = {
                    "encounter_volume": row["volume"],
                    "volume_percent": row["percent_volume"],
                    "average_los": row["average_los"],
                    "occupancy_contribution": row["occupancy_contribution"],
                    "occupancy_percent_contribution": row["percent_contribution"]
                }

                for metric_name, metric_value in metrics.items():

                    rdb_rows.append({

                        "run_id":
                            params.get("run_id"),

                        "visual_id":
                            VISUAL_ID,

                        "client_name":
                            params.get("client_name"),

                        "domain":
                            params.get("domain"),

                        "cohort_id":
                            params.get("cohort_id"),

                        "domain_cohort":
                            f"{params.get('domain')}.{params.get('cohort_id')}",

                        "dimension":
                            "esi",

                        "dimension_value":
                            row["esi"],

                        "dimension_value_label":
                            row["esi"],

                        "secondary_dimension":
                            None,

                        "secondary_dimension_value":
                            None,

                        "metric":
                            metric_name,

                        "metric_type":
                            "value",

                        "value":
                            float(metric_value),

                        "start_date":
                            start_date,

                        "end_date":
                            end_date,

                        "report_title":
                            report_title
                    })

            overall_metrics = {
                "total_encounters": total_volume,
                "total_occupancy": total_occupancy
            }

            for metric_name, metric_value in overall_metrics.items():

                rdb_rows.append({

                    "run_id":
                        params.get("run_id"),

                    "visual_id":
                        VISUAL_ID,

                    "client_name":
                        params.get("client_name"),

                    "domain":
                        params.get("domain"),

                    "cohort_id":
                        params.get("cohort_id"),

                    "domain_cohort":
                        f"{params.get('domain')}.{params.get('cohort_id')}",

                    "dimension":
                        "esi",

                    "dimension_value":
                        "Overall",

                    "dimension_value_label":
                        "Overall",

                    "secondary_dimension":
                        None,

                    "secondary_dimension_value":
                        None,

                    "metric":
                        metric_name,

                    "metric_type":
                        "value",

                    "value":
                        float(metric_value),

                    "start_date":
                        start_date,

                    "end_date":
                        end_date,

                    "report_title":
                        report_title
                })

            rdb_rows.append({

                "run_id": params.get("run_id"),
                "visual_id": VISUAL_ID,
                "client_name": params.get("client_name"),

                "domain": params.get("domain"),
                "cohort_id": params.get("cohort_id"),

                "domain_cohort":
                    f"{params.get('domain')}.{params.get('cohort_id')}",

                "dimension": "esi",
                "dimension_value": "Overall",
                "dimension_value_label": "Overall",

                "secondary_dimension": None,
                "secondary_dimension_value": None,

                "metric": "dominant_esi",
                "metric_type": "value",

                "value": dominant_esi,

                "start_date": start_date,
                "end_date": end_date,

                "report_title": report_title
            })

        logger.info(
            f"[{VISUAL_ID}] Output saved to {output_file}"
        )

        return {
            "output_path": output_file,
            "rdb": rdb_rows
        }

    except Exception as e:

        logger.error(
            f"[{VISUAL_ID}] Execution failed: {e}"
        )