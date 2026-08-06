# =============================================================================
# Report Name : Facility Census Trend
#
# Description :
# Calculates and visualizes Facility census levels over time
# using patient arrival and departure timestamps. The program constructs a
# minute-by-minute census timeline by identifying all encounters active
# during each reporting interval and computing the concurrent patient
# count within the Facility.
#
# Results are produced as both a detailed census dataset and a trend
# visualization. The report optionally highlights periods where census
# exceeds a configurable percentage of department capacity and can display
# reference lines for average census and operational capacity.
#
# This report supports:
#   - Facility census monitoring
#   - Capacity management
#   - Throughput analysis
#   - Overcrowding assessment
#   - Staffing and resource planning
#   - Operational performance review
#
# Inputs :
#   - arrival_dtm : Facility arrival/start datetime
#   - tmt_stop_dtm  : Facility departure/stop datetime
#   - start_date   : Reporting period start date/time
#   - end_date     : Reporting period end date/time
#
# Outputs :
#   - PNG line chart displaying Facility census over time
#       * Census trend by minute
#       * Optional capacity threshold line
#       * Optional average census line
#   - CSV file containing:
#       * Interval timestamp
#       * Census count
#   - RDB records containing:
#       * Census count by reporting interval
#       * Time-based census metrics for downstream reporting
#
# Key Metrics :
#   - Concurrent Facility census
#   - Average census
#   - Peak census periods
#   - Capacity utilization
#   - Census trend across the reporting period
# =============================================================================

import os
import logging
import pandas as pd
import matplotlib.pyplot as plt
from utils.vis_helpers import (
    normalize_params,
    format_date_range,
    apply_axis_range,
    apply_yaxis_format,
    save_legend_png,
    format_display_value,
    get_display_parameters,
    save_parameter_table_png,
    save_title_png,
    generate_census
)
from utils.date_helpers import prepare_dates
from utils.col_helpers import add_common_helper_columns

logger = logging.getLogger(__name__)

VISUAL_ID = "vis_08"

def run(df, params, start_date, end_date, output_dir, generate_output_name):
    logger.info(f"[{VISUAL_ID}] Starting census generation")
    params = normalize_params(params)

    try:

        # --------------------------------------------------
        # HELP MY DATAFRAME
        # --------------------------------------------------
        _, df = prepare_dates(df, start_date, end_date)
        df = add_common_helper_columns(df)

        logger.info(
            f"[{VISUAL_ID}] Dataset received after helper preparation. "
            f"Rows available for census generation: {len(df):,}"
        )

        logger.info(
            f"[{VISUAL_ID}] Building census timeline from "
            f"{len(df):,} encounters."
        )

        ts, census_df = generate_census(
            df,
            start_date,
            end_date
        )

        logger.info(
            f"[{VISUAL_ID}] Census dataset generated. "
            f"Intervals: {len(ts):,}"
        )

        enable_rdb = int(params.get("rdb_write", 0))
        rdb_rows = []

        # =========================================================
        # OUTPUT CSV
        # =========================================================
        filename = generate_output_name(
            visual_id=VISUAL_ID,
            start_date=start_date,
            end_date=end_date,
            cohort_id=params.get("cohort_id"),
            ext="csv"
        )
        output_path = os.path.join(output_dir, filename)

        ts[["interval", "census"]].to_csv(output_path, index=False)

        # =========================================================
        # VISUALIZATION
        # =========================================================
        def _get_float(params, key, default=None):
            try:
                val = params.get(key, default)
                return float(val) if val not in [None, "", "None"] else None
            except:
                return default


        def _get_bool(params, key, default=False):
            val = str(params.get(key, default)).strip().lower()
            if val in ["true", "1", "yes"]:
                return True
            if val in ["false", "0", "no"]:
                return False
            return default


        def _get_str(params, key, default=""):
            val = params.get(key, default)
            return str(val) if val is not None else default


        capacity_value = _get_float(params, "capacity_value", None)
        include_avg_line = _get_bool(params, "include_avg_line", True)
        chart_title = _get_str(params, "chart_title", "Facility Census Trend")
        capacity_threshold_pct = _get_float(params, "capacity_threshold_pct", 0.8)
        below_color = params.get("below_color", "black")
        above_color = params.get("above_color", "red")
        font_family = _get_str(
            params,
            "font_family",
            "Segoe UI"
        )
        plt.rcParams["font.family"] = font_family

        figure_width = _get_float(
            params,
            "figure_width",
            14
        )

        figure_height = _get_float(
            params,
            "figure_height",
            6
        )

        plt.figure(
            figsize=(figure_width, figure_height)
        )

        title_height = float(
            params.get("title_height", 0.6) or 0.6
        )

        title_width = float(
            params.get("title_width", 6.25) or 6.25
        )

        subtitle_fontsize = int(
            params.get("subtitle_fontsize", 12) or 12
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

        tick_fontsize = _get_float(
            params,
            "tick_fontsize",
            10
        )

        legend_fontsize = _get_float(
            params,
            "legend_fontsize",
            10
        )

        dpi = _get_float(
            params,
            "dpi",
            300
        )

        legend_width = _get_float(
            params,
            "legend_width",
            10
        )

        legend_height = _get_float(
            params,
            "legend_height",
            10
        )

        line_width = _get_float(
        params,
        "line_width",
        0.8
        )

        capacity_linestyle = _get_str(
            params,
            "capacity_linestyle",
            "--"
        )

        capacity_linewidth = _get_float(
            params,
            "capacity_linewidth",
            1.5
        )

        avg_linestyle = _get_str(
            params,
            "avg_linestyle",
            ":"
        )

        avg_linewidth = _get_float(
            params,
            "avg_linewidth",
            1.5
        )

        avg_line_color = _get_str(
            params,
            "avg_line_color",
            "black"
        )

        y_axis_mode = _get_str(
            params,
            "y_axis_mode",
            "count"
        )

        y_axis_decimals = int(
            _get_float(
                params,
                "y_axis_decimals",
                0
            )
        )

        y_axis_multiplier = _get_float(
            params,
            "y_axis_multiplier",
            1
        )

        y_axis_suffix = _get_str(
            params,
            "y_axis_suffix",
            ""
        )

        # -----------------------------------------------------
        # THRESHOLD LOGIC 
        # -----------------------------------------------------
        if capacity_value is not None:
            threshold = capacity_value * capacity_threshold_pct

            below = ts["census"] <= threshold
            above = ts["census"] > threshold
        else:
            below = pd.Series(True, index=ts.index)
            above = pd.Series(False, index=ts.index)

        # -----------------------------------------------------
        # MAIN LINE 
        # -----------------------------------------------------
        below_line, = plt.plot(
            ts["interval"],
            ts["census"],
            color=below_color,
            linewidth=line_width,
            label="Census",
            zorder=2
        )

        above_line = None

        # -----------------------------------------------------
        # ABOVE-THRESHOLD OVERLAY
        # -----------------------------------------------------
        if capacity_value is not None:

            above_line, = plt.plot(
                ts["interval"],
                ts["census"].where(above),
                color=above_color,
                linewidth=line_width + 0.3,
                label=f"Census (>{int(capacity_threshold_pct*100)}%)",
                zorder=3
            )

        # -----------------------------------------------------
        # CAPACITY LINE
        # -----------------------------------------------------
        if capacity_value is not None:
            capacity_line = None

            if capacity_value is not None:

                capacity_line = plt.axhline(
                    y=capacity_value,
                    linestyle=capacity_linestyle,
                    linewidth=capacity_linewidth,
                    color="dodgerblue",
                    label=f"Capacity ({capacity_value})",
                    zorder=10
                )

        # -----------------------------------------------------
        # AVERAGE LINE
        # -----------------------------------------------------
        avg_line = None

        if include_avg_line:

            avg_census = ts["census"].mean()

            avg_line = plt.axhline(
                y=avg_census,
                color=avg_line_color,
                linestyle=avg_linestyle,
                linewidth=avg_linewidth,
                label=f"Average ({round(avg_census,1)})",
                zorder=11
            )

        # Labels
        title_fontsize = _get_float(
            params,
            "title_fontsize",
            16
        )

        label_fontsize = _get_float(
            params,
            "label_fontsize",
            12
        )

        x_label = _get_str(
            params,
            "x_label",
            "Time"
        )

        plt.xlabel(
            x_label,
            fontsize=label_fontsize,
            fontfamily=font_family
        )
        y_label = _get_str(
            params,
            "y_label",
            "Facility Census"
        )

        plt.ylabel(
            y_label,
            fontsize=label_fontsize,
            fontfamily=font_family
        )

        # Improve x-axis readability
        plt.gcf().autofmt_xdate()

        ax = plt.gca()

        apply_yaxis_format(
            ax,
            mode=y_axis_mode,
            decimals=y_axis_decimals,
            multiplier=y_axis_multiplier,
            suffix=y_axis_suffix
        )

        for tick in ax.get_xticklabels():
            tick.set_fontfamily(font_family)
            tick.set_fontsize(tick_fontsize)

        for tick in ax.get_yticklabels():
            tick.set_fontfamily(font_family)
            tick.set_fontsize(tick_fontsize)

        plt.tight_layout()

        # Save PNG
        png_filename = generate_output_name(
            visual_id=VISUAL_ID,
            start_date=start_date,
            end_date=end_date,
            cohort_id=params.get("cohort_id"),
            ext="png"
        )
        png_path = os.path.join(output_dir, png_filename)

        plt.savefig(
            png_path,
            dpi=int(dpi)
        )

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
            title=chart_title,
            subtitle=date_range,
            output_file=title_output_file,
            width=title_width,
            height=title_height,
            dpi=int(dpi),
            font_family=font_family,
            title_fontsize=int(title_fontsize),
            subtitle_fontsize=subtitle_fontsize,
            background_color=title_background_color,
            title_weight=title_weight
        )

        legend_handles = [
            below_line
        ]

        legend_labels = [
            below_line.get_label()
        ]

        if above_line is not None:

            legend_handles.append(
                above_line
            )

            legend_labels.append(
                above_line.get_label()
            )

        if capacity_line is not None:

            legend_handles.append(
                capacity_line
            )

            legend_labels.append(
                capacity_line.get_label()
            )

        if avg_line is not None:

            legend_handles.append(
                avg_line
            )

            legend_labels.append(
                avg_line.get_label()
            )

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
            ncol=1,
            font_family=font_family,
            font_size=legend_fontsize,
            width=legend_width,
            height=legend_height
        )

        plt.close()

        write_rdb = int(params.get("write_rdb", 0))

        if write_rdb == 1:
            for _, row in ts.iterrows():

                census_value = row["census"]

                if pd.isna(census_value):
                    continue

                rdb_rows.append({
                    "run_id": params.get("run_id"),
                    "visual_id": VISUAL_ID,
                    "client_name": params.get("client_name"),

                    "domain": params.get("domain"),
                    "cohort_id": params.get("cohort_id"),

                    "domain_cohort":
                        f"{params.get('domain')}.{params.get('cohort_id')}",

                    "dimension": "interval",
                    "dimension_value": row["interval"],
                    "dimension_value_label":
                        row["interval"].strftime("%Y-%m-%d %H:%M"),

                    "secondary_dimension": None,
                    "secondary_dimension_value": None,

                    "metric": "ed_census",
                    "metric_type": "count",
                    "value": int(census_value),

                    "start_date": start_date,
                    "end_date": end_date,

                    "report_title": chart_title
                })        

        logger.info(f"[{VISUAL_ID}] Outputs saved: CSV and PNG")

        return {
            "output_path": png_path,
            "rdb": rdb_rows
        }

    except Exception as e:
        logger.error(f"[{VISUAL_ID}] Failed: {str(e)}")