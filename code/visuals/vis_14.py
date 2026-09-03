import os
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from utils.vis_helpers import (
    normalize_params,
    format_date_range,
    save_legend_png,
    save_parameter_table_png,
    save_title_png,
    get_display_parameters,
    format_display_value
)

from utils.date_helpers import df_date_splitter

logger = logging.getLogger(__name__)

VISUAL_ID = "vis_14"


def run(
    df,
    params,
    start_date,
    end_date,
    output_dir,
    generate_output_name
):
    logger.info(
        f"[{VISUAL_ID}] Starting LOS by Arrival Date visualization"
    )

    params = normalize_params(params)

    try:

        # ==================================================
        # DEFAULT PARAMETERS
        # ==================================================
        defaults = {
            "fig_width": 10,
            "fig_height": 4,
            "dpi": 300,

            "title_fontsize": 10,
            "axis_fontsize": 9,
            "label_fontsize": 8,
            "tick_fontsize": 8,

            "label_decimals": 1,
            "label_threshold": 0,

            "time_bucket": "month",
            "los_type": "hours",

            "line_color": "#1f77b4",
            "marker_style": "o",

            "title_width": 6.4,
            "title_height": 0.25,
            "legend_width": 4,
            "legend_height": 1,
            "enable_iqr_filter": 1,
            "iqr_filter_multiplier": 0.50,
            "show_trendline": 1,
            "trendline_color": "#1f77b4",
            "trendline_linestyle": "--",
            "trendline_linewidth": 2,
        }

        p = {**defaults, **(params or {})}

        font_family = str(
            p.get("font_family", "Segoe UI")
        ).strip()

        # ==================================================
        # SAFE PARAMETER HANDLING
        # ==================================================
        try:
            p["fig_width"] = float(p["fig_width"])
            p["fig_height"] = float(p["fig_height"])
            p["dpi"] = int(float(p["dpi"]))
            p["label_decimals"] = int(float(p["label_decimals"]))
            p["tick_fontsize"] = int(float(p["tick_fontsize"]))
        except Exception:
            logger.warning(
                f"[{VISUAL_ID}] Invalid numeric parameters detected"
            )

        bucket = str(
            p.get("time_bucket", "month")
        ).lower()

        if bucket not in {
            "month",
            "quarter",
            "year"
        }:
            logger.warning(
                f"[{VISUAL_ID}] Invalid time_bucket={bucket}. Using month."
            )
            bucket = "month"

        los_type = str(
            p.get("los_type", "hours")
        ).lower()

        if los_type not in {"hours", "days"}:
            logger.warning(
                f"[{VISUAL_ID}] Invalid los_type={los_type}. Using hours."
            )
            los_type = "hours"

        los_col = (
            "los_days"
            if los_type == "days"
            else "los_hours"
        )

        cohort_desc = (
            params.get("cohort_desc")
            or params.get("cohort_id")
            or "All Records"
        )

        bucket_display = bucket.title()

        los_display = (
            "Days"
            if los_type == "days"
            else "Hours"
        )

        report_title = (
            f"{cohort_desc} | "
            f"Average Length of Stay by Arrival "
            f"{bucket_display} "
            f"({los_display})"
        )

        # ==================================================
        # DATE FILTER
        # ==================================================
        _, df = df_date_splitter(
            df,
            start_date,
            end_date
        )

        if df.empty:
            logger.warning(
                f"[{VISUAL_ID}] No data after date filtering"
            )
            return

        # ==================================================
        # REQUIRED COLUMNS
        # ==================================================
        required_cols = [
            "arrival_dtm",
            los_col,
            "valid_los"
        ]

        for col in required_cols:
            if col not in df.columns:
                logger.error(
                    f"[{VISUAL_ID}] Missing required column: {col}"
                )
                return

        # ==================================================
        # DATETIME SAFETY
        # ==================================================
        df = df.copy()

        df["arrival_dtm"] = pd.to_datetime(
            df["arrival_dtm"],
            errors="coerce"
        )

        df = df.dropna(
            subset=[
                "arrival_dtm",
                los_col
            ]
        )

        df = df[
            df["valid_los"] == True
        ].copy()

        if df.empty:
            logger.warning(
                f"[{VISUAL_ID}] No valid LOS records"
            )
            return

        # ==================================================
        # DYNAMIC LOWER-BOUND LOS FILTER (IQR BASED)
        # ==================================================

        df["included_in_aggregation"] = True
        df["aggregation_cutoff"] = 0.0

        enable_iqr_filter = int(
            float(
                p.get(
                    "enable_iqr_filter",
                    1
                )
            )
        )

        if enable_iqr_filter == 1:

            multiplier = float(
                p.get(
                    "iqr_filter_multiplier",
                    0.50
                )
            )

            q1 = float(
                np.nanpercentile(
                    df[los_col],
                    25
                )
            )

            median = float(
                np.nanpercentile(
                    df[los_col],
                    50
                )
            )

            cutoff_value = (
                q1 +
                (
                    (median - q1)
                    * multiplier
                )
            )

            df["aggregation_cutoff"] = cutoff_value

            df["included_in_aggregation"] = (
                df[los_col] >= cutoff_value
            )

            included_count = int(
                df["included_in_aggregation"].sum()
            )

            excluded_count = int(
                (~df["included_in_aggregation"]).sum()
            )

            logger.info(
                f"[{VISUAL_ID}] Dynamic LOS cutoff enabled | "
                f"LOS={los_col} | "
                f"Q1={q1:.2f} | "
                f"Median={median:.2f} | "
                f"Multiplier={multiplier:.2f} | "
                f"Cutoff={cutoff_value:.2f} | "
                f"Included={included_count:,} | "
                f"Excluded={excluded_count:,}"
            )

        else:

            df["aggregation_cutoff"] = 0

            logger.info(
                f"[{VISUAL_ID}] Dynamic LOS cutoff disabled"
            )

        aggregation_df = df[
            df["included_in_aggregation"]
        ].copy()

        if aggregation_df.empty:
            logger.warning(
                f"[{VISUAL_ID}] No rows remain after "
                f"dynamic LOS filtering"
            )
            return

        # ==================================================
        # TIME BUCKETS
        # ==================================================
        if bucket == "month":

            df["bucket_dt"] = (
                df["arrival_dtm"]
                .dt.to_period("M")
                .dt.to_timestamp()
            )

            df["bucket_label"] = (
                df["bucket_dt"]
                .dt.strftime("%Y-%m")
            )

        elif bucket == "quarter":

            df["bucket_dt"] = (
                df["arrival_dtm"]
                .dt.to_period("Q")
                .dt.start_time
            )

            df["bucket_label"] = (
                df["bucket_dt"]
                .dt.to_period("Q")
                .astype(str)
            )

        else:

            df["bucket_dt"] = (
                df["arrival_dtm"]
                .dt.to_period("Y")
                .dt.to_timestamp()
            )

            df["bucket_label"] = (
                df["bucket_dt"]
                .dt.strftime("%Y")
            )

        # Rebuild aggregation dataframe AFTER bucket assignment
        aggregation_df = df[
            df["included_in_aggregation"]
        ].copy()

        # ==================================================
        # AGGREGATION
        # ==================================================
        grouped = (
            aggregation_df.groupby(
                ["bucket_dt", "bucket_label"],
                observed=False
            )[los_col]
            .mean()
            .reset_index()
            .sort_values("bucket_dt")
        )

        if grouped.empty:
            logger.warning(
                f"[{VISUAL_ID}] Aggregation produced no rows"
            )
            return

        # ==================================================
        # SUMMARY METRICS
        # ==================================================
        overall_mean = float(aggregation_df[los_col].mean())
        overall_median = float(aggregation_df[los_col].median())

        # ==================================================
        # RDB OUTPUT
        # ==================================================
        rdb_rows = []

        write_rdb = int(
            float(params.get("write_rdb", 0) or 0)
        )

        if write_rdb == 1:

            for _, row in grouped.iterrows():

                rdb_rows.append({
                    "run_id": params.get("run_id"),
                    "visual_id": VISUAL_ID,
                    "client_name": params.get("client_name"),
                    "domain": params.get("domain"),
                    "cohort_id": params.get("cohort_id"),

                    "domain_cohort":
                        f"{params.get('domain')}.{params.get('cohort_id')}",

                    "dimension": bucket,
                    "dimension_value": row["bucket_label"],
                    "dimension_value_label": row["bucket_label"],

                    "secondary_dimension": None,
                    "secondary_dimension_value": None,

                    "metric": f"avg_{los_col}",
                    "metric_type": "value",

                    "value": row[los_col],

                    "start_date": start_date,
                    "end_date": end_date,

                    "report_title": report_title
                })

            rdb_rows.append({
                "run_id": params.get("run_id"),
                "visual_id": VISUAL_ID,
                "client_name": params.get("client_name"),
                "domain": params.get("domain"),
                "cohort_id": params.get("cohort_id"),

                "domain_cohort":
                    f"{params.get('domain')}.{params.get('cohort_id')}",

                "dimension": "summary",
                "dimension_value": None,
                "dimension_value_label": "overall_mean",

                "secondary_dimension": None,
                "secondary_dimension_value": None,

                "metric": f"avg_{los_col}",
                "metric_type": "summary",

                "value": overall_mean,

                "start_date": start_date,
                "end_date": end_date,

                "report_title": report_title
            })

        slope = np.nan
        intercept = np.nan
        annual_trend = np.nan
        trend_units = None
        trend_display = None

        # ==================================================
        # CHART
        # ==================================================
        plt.rcParams["font.family"] = font_family

        fig, ax = plt.subplots(
            figsize=(
                p["fig_width"],
                p["fig_height"]
            )
        )

        # x = range(len(grouped))

        x = np.arange(len(grouped))

        show_trendline = int(
            float(
                p.get(
                    "show_trendline",
                    1
                )
            )
        )

        trendline_handle = None

        if (
            show_trendline == 1
            and len(grouped) >= 2
        ):

            slope, intercept = np.polyfit(
                x,
                grouped[los_col],
                1
            )

            # ==========================================
            # ANNUALIZED OLS TREND
            # ==========================================
            if bucket == "month":
                yoy_multiplier = 12

            elif bucket == "quarter":
                yoy_multiplier = 4

            else:
                yoy_multiplier = 1

            annual_trend = (
                slope *
                yoy_multiplier
            )

            trend_units = (
                "days"
                if los_type == "days"
                else "hours"
            )

            trend_display = (
                f"{annual_trend:+.1f} "
                f"{trend_units} per year"
            )

            logger.info(
                f"[{VISUAL_ID}] "
                f"OLS Annual Trend: "
                f"{annual_trend:+.2f} "
                f"{trend_units}/year"
            )

            grouped["trendline"] = (
                slope * x
                + intercept
            )

            ax.plot(
                x,
                grouped["trendline"],
                color=p["trendline_color"],
                linestyle=p["trendline_linestyle"],
                linewidth=float(
                    p.get(
                        "trendline_linewidth",
                        2
                    )
                )
            )

            trendline_handle = Line2D(
                [0],
                [0],
                color=p["trendline_color"],
                linestyle=p["trendline_linestyle"],
                linewidth=float(
                    p.get(
                        "trendline_linewidth",
                        2
                    )
                ),
                label="OLS Trend"
            )

            logger.info(
                f"[{VISUAL_ID}] OLS trendline "
                f"slope={slope:.6f}"
            )

        ax.plot(
            x,
            grouped[los_col],
            color=p["line_color"],
            marker=p["marker_style"],
            linewidth=2
        )

        for i, row in grouped.iterrows():

            val = row[los_col]

            if pd.notna(val):

                ax.text(
                    i,
                    val,
                    f"{val:.{p['label_decimals']}f}",
                    ha="center",
                    va="bottom",
                    fontsize=p["label_fontsize"]
                )

        ylabel = (
            "Average LOS (Days)"
            if los_type == "days"
            else "Average LOS (Hours)"
        )

        ax.set_ylabel(
            ylabel,
            fontsize=p["axis_fontsize"]
        )

        ax.set_xlabel(
            bucket.title(),
            fontsize=p["axis_fontsize"]
        )

        ax.set_xticks(list(x))
        ax.set_xticklabels(
            grouped["bucket_label"],
            rotation=45,
            ha="right"
        )

        ax.grid(
            axis="y",
            linestyle="--",
            alpha=0.3
        )

        plt.tight_layout()

        # ==================================================
        # DETAIL AUDIT OUTPUT
        # ==================================================

        write_detail = int(
            float(params.get("write_detail", 1) or 1)
        )

        if write_detail == 1:

            detail_file = os.path.join(
                output_dir,
                generate_output_name(
                    visual_id=f"{VISUAL_ID}_detail",
                    start_date=start_date,
                    end_date=end_date,
                    cohort_id=params.get("cohort_id"),
                    ext="csv"
                )
            )

            detail_cols = []

            preferred_cols = [
                "BookNumber",
                "arrival_dtm",
                "tmt_stop_dtm",
                "los_hours",
                "los_days",
                "valid_los",
                "included_in_aggregation",
                "aggregation_cutoff",
                "bucket_dt",
                "bucket_label",
                "sex",
                "housing",
                "custody_class"
            ]

            for col in preferred_cols:
                if col in df.columns:
                    detail_cols.append(col)

            # Build detail dataset
            detail_df = (
                df[detail_cols]
                .sort_values(
                    ["bucket_dt", "arrival_dtm"],
                    ascending=True
                )
                .copy()
            )

            bucket_means = (
                grouped[
                    [
                        "bucket_dt",
                        "bucket_label",
                        los_col
                    ]
                ]
                .rename(
                    columns={
                        los_col: "bucket_average_los"
                    }
                )
            )

            detail_df = detail_df.merge(
                bucket_means,
                on=[
                    "bucket_dt",
                    "bucket_label"
                ],
                how="left"
            )

            # Audit metadata
            detail_df["visual_id"] = VISUAL_ID
            detail_df["cohort_id"] = params.get("cohort_id")
            detail_df["start_date"] = start_date
            detail_df["end_date"] = end_date
            detail_df["los_measure"] = los_col
            detail_df["time_bucket"] = bucket
            detail_df["q1_los"] = q1
            detail_df["median_los"] = median
            detail_df["iqr_multiplier"] = multiplier
            detail_df["ols_slope"] = slope
            detail_df["ols_intercept"] = intercept
            detail_df["annualized_trend"] = annual_trend
            detail_df["trend_units"] = trend_units
            detail_df["annualized_trend_display"] = trend_display

            detail_df.to_csv(
                detail_file,
                index=False
            )

            logger.info(
                f"[{VISUAL_ID}] Detail file written: "
                f"{detail_file}"
            )

        # ==================================================
        # MAIN PNG
        # ==================================================
        output_path = os.path.join(
            output_dir,
            generate_output_name(
                visual_id=VISUAL_ID,
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        plt.savefig(
            output_path,
            dpi=p["dpi"]
        )

        plt.close(fig)

        logger.info(
            f"[{VISUAL_ID}] saved {output_path}"
        )

        # ==================================================
        # LEGEND PNG
        # ==================================================
        legend_handles = [
            Line2D(
                [0],
                [0],
                color=p["line_color"],
                marker=p["marker_style"],
                linewidth=2,
                label="Average LOS"
            )
        ]

        if trendline_handle is not None:
            legend_handles.append(
                trendline_handle
            )

        legend_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id=f"{VISUAL_ID}_legend",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        legend_labels = [
            h.get_label()
            for h in legend_handles
        ]

        save_legend_png(
            handles=legend_handles,
            labels=legend_labels,
            output_file=legend_file,
            ncol=1,
            font_family=font_family,
            font_size=p["axis_fontsize"],
            width=float(p["legend_width"]),
            height=float(p["legend_height"])
        )



        # ==================================================
        # TITLE PNG
        # ==================================================
        title_file = os.path.join(
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
            title=report_title,
            subtitle=format_date_range(
                start_date,
                end_date
            ),
            output_file=title_file,
            width=float(p["title_width"]),
            height=float(p["title_height"]),
            dpi=p["dpi"],
            font_family=font_family,
            title_fontsize=int(float(p["title_fontsize"])),
            subtitle_fontsize=int(
                float(
                    p.get("subtitle_fontsize", 8)
                )
            ),
            background_color=p.get(
                "title_background_color",
                "#d9d9d9"
            ),
            title_weight=p.get(
                "title_weight",
                "bold"
            )
        )

        # ==================================================
        # ANNUALIZED TREND PNG
        # ==================================================

        if (
            show_trendline == 1
            and len(grouped) >= 2
        ):

            trend_output_file = os.path.join(
                output_dir,
                generate_output_name(
                    visual_id=f"{VISUAL_ID}_trend",
                    start_date=start_date,
                    end_date=end_date,
                    cohort_id=params.get("cohort_id"),
                    ext="png"
                )
            )

            trend_display = (
                f"{annual_trend:+.1f} "
                f"{trend_units.title()} Per Year"
            )

            fig, ax = plt.subplots(
                figsize=(2.4, 0.8)
            )

            ax.axis("off")

            table = ax.table(
                cellText=[[trend_display]],
                colLabels=["Annualized LOS Trend"],
                cellLoc="center",
                colLoc="center",
                loc="center"
            )

            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1.2, 2.0)

            for (row, col), cell in table.get_celld().items():

                cell.set_edgecolor("black")
                cell.set_linewidth(1.5)

                if row == 0:
                    cell.set_facecolor("#d9d9d9")
                    cell.set_text_props(
                        weight="bold",
                        color="black",
                        fontfamily=font_family
                    )
                else:
                    cell.set_facecolor("white")
                    cell.set_text_props(
                        color="black",
                        fontfamily=font_family
                    )

            plt.tight_layout()

            plt.savefig(
                trend_output_file,
                dpi=int(p["dpi"]),
                bbox_inches="tight"
            )

            plt.close(fig)

            logger.info(
                f"[{VISUAL_ID}] trend table written: "
                f"{trend_output_file}"
            )

        logger.info(
            f"[{VISUAL_ID}] Completed successfully"
        )

        return {
            "output_path": output_path,
            "rdb": rdb_rows
        }

    except Exception as exc:
        logger.error(
            f"[{VISUAL_ID}] failed: {str(exc)}"
        )