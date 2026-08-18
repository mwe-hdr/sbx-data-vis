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
import numpy as np
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
from utils.date_helpers import df_date_splitter

logger = logging.getLogger(__name__)

VISUAL_ID = "vis_08"

def run(df, params, start_date, end_date, output_dir, generate_output_name):

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

    def save_projection_table_png(
        df,
        output_file,
        font_family="Segoe UI",
        font_size=10
    ):

        if df.empty:
            return None

        plt.rcParams["font.family"] = font_family

        fig_height = max(
            1.5,
            len(df) * 0.45
        )

        fig, ax = plt.subplots(
            figsize=(3.25, fig_height)
        )

        ax.axis("off")

        table = ax.table(
            cellText=df.values,
            colLabels=df.columns,
            loc="center",
            cellLoc="center"
        )

        table.auto_set_font_size(False)
        table.set_fontsize(font_size)
        table.scale(1.2, 1.5)

        for col in range(len(df.columns)):

            header = table[(0, col)]

            header.set_facecolor("#d9d9d9")
            header.get_text().set_weight("bold")
            header.get_text().set_multialignment("center")

            # increase header row height
            header.set_height(
                header.get_height() * 1.8
            )

        plt.tight_layout()

        plt.savefig(
            output_file,
            bbox_inches="tight"
        )

        plt.close()

        return output_file

    def format_projection_period(months):

        years = months // 12
        remaining = months % 12

        if years > 0 and remaining > 0:
            return f"{years}y {remaining}m"

        if years > 0:
            return f"{years} Years"

        return f"{months} Months"

    logger.info(f"[{VISUAL_ID}] Starting Facility Census Trend visualization")
    params = normalize_params(params)

    try:

        # --------------------------------------------------
        # HELP MY DATAFRAME
        # --------------------------------------------------
        df, _ = df_date_splitter(df, start_date, end_date)

        bypass_census_csv = _get_str(
            params,
            "bypass_census_csv",
            ""
        ).strip()

        if bypass_census_csv:

            logger.info(
                f"[{VISUAL_ID}] Using bypass census file: "
                f"{bypass_census_csv}"
            )

            ts = pd.read_csv(
                bypass_census_csv,
                parse_dates=["interval"]
            )

            required_columns = [
                "interval",
                "census"
            ]

            missing = [
                c
                for c in required_columns
                if c not in ts.columns
            ]

            if missing:
                raise ValueError(
                    "Bypass census file missing required columns: "
                    f"{missing}"
                )

            ts["interval"] = pd.to_datetime(
                ts["interval"],
                errors="raise"
            )

            ts["census"] = pd.to_numeric(
                ts["census"],
                errors="raise"
            )

            ts = ts[
                (ts["interval"] >= start_date)
                &
                (ts["interval"] <= end_date)
            ]

            census_df = ts.copy()

            logger.info(
                f"[{VISUAL_ID}] Loaded bypass census file. "
                f"Intervals: {len(ts):,}"
            )

        else:

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
                f"Intervals: {len(ts):,} "
                f"Census df: {len(census_df):,}"
            )

        enable_rdb = int(params.get("rdb_write", 0))
        rdb_rows = []

        # =========================================================
        # VISUALIZATION
        # =========================================================

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
        # TREND / PROJECTION PARAMETERS
        # -----------------------------------------------------
        enable_trend_projection = _get_bool(
            params,
            "enable_trend_projection",
            False
        )

        trend_input_months = int(
            _get_float(
                params,
                "trend_input_months",
                12
            ) or 12
        )

        trend_start_month = _get_str(
            params,
            "trend_start_month",
            ""
        ).strip()

        projection_months = int(
            _get_float(
                params,
                "projection_months",
                3
            ) or 3
        )

        trend_line_color = _get_str(
            params,
            "trend_line_color",
            "#1f77b4"
        )

        trend_linewidth = _get_float(
            params,
            "trend_linewidth",
            2.0
        )

        trend_linestyle = _get_str(
            params,
            "trend_linestyle",
            "-"
        )

        projection_line_color = _get_str(
            params,
            "projection_line_color",
            "#ff7f0e"
        )

        projection_linewidth = _get_float(
            params,
            "projection_linewidth",
            2.0
        )

        projection_linestyle = _get_str(
            params,
            "projection_linestyle",
            "--"
        )

        show_confidence_band = _get_bool(
            params,
            "show_confidence_band",
            False
        )

        confidence_level = _get_float(
            params,
            "confidence_level",
            0.95
        )

        confidence_fill_color = _get_str(
            params,
            "confidence_fill_color",
            "#1f77b4"
        )

        confidence_alpha = _get_float(
            params,
            "confidence_alpha",
            0.15
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

        # -----------------------------------------------------
        # OLS TREND / PROJECTION
        # -----------------------------------------------------
        trend_line = None
        projection_line = None
        confidence_band = None
        projection_df = pd.DataFrame()

        projection_df = pd.DataFrame()

        projection_table_df = pd.DataFrame(
            columns=[
                "Period",
                "Projected Facility Room Need"
            ]
        )

        projection_table_start_month = int(
            _get_float(
                params,
                "projection_table_start_month",
                180
            ) or 180
        )

        projection_table_interval_months = int(
            _get_float(
                params,
                "projection_table_interval_months",
                60
            ) or 60
        )

        projection_table_rows = int(
            _get_float(
                params,
                "projection_table_rows",
                3
            ) or 3
        )

        projection_plot_months = _get_float(
            params,
            "projection_plot_months",
            projection_months
        )

        if projection_plot_months is None:
            projection_plot_months = projection_months

        projection_plot_months = int(
            projection_plot_months
        )  

        if enable_trend_projection:

            logger.info(
                f"[{VISUAL_ID}] Building OLS trend projection"
            )

            if trend_start_month:

                training_start = pd.to_datetime(
                    trend_start_month
                )

            else:

                training_start = ts[
                    "interval"
                ].min()

            training_end = (
                training_start
                + pd.DateOffset(
                    months=trend_input_months
                )
            )

            logger.info(
                f"[{VISUAL_ID}] Trend model window: "
                f"{training_start:%Y-%m-%d} "
                f"through "
                f"{training_end:%Y-%m-%d}"
            )

            training_df = ts[
                (
                    ts["interval"]
                    >= training_start
                )
                &
                (
                    ts["interval"]
                    < training_end
                )
            ].copy()

            if training_df.empty:

                logger.warning(
                    f"[{VISUAL_ID}] No data in "
                    "specified trend window."
                )

                enable_trend_projection = False

            if len(training_df) >= 5:

                base_date = training_df[
                    "interval"
                ].min()

                x_train = (
                    training_df["interval"]
                    - base_date
                ).dt.total_seconds() / 86400.0

                y_train = training_df["census"]

                slope, intercept = np.polyfit(
                    x_train,
                    y_train,
                    1
                )

                training_df["trend"] = (
                    intercept
                    + slope * x_train
                )

                # ------------------------------------------
                # CONFIDENCE INTERVALS
                # ------------------------------------------
                n = len(x_train)

                residuals = (
                    y_train
                    - training_df["trend"]
                )

                mse = np.sum(
                    residuals ** 2
                ) / (n - 2)

                mean_x = np.mean(x_train)

                sxx = np.sum(
                    (x_train - mean_x) ** 2
                )

                standard_error = np.sqrt(
                    mse * (
                        (1 / n)
                        +
                        (
                            (x_train - mean_x) ** 2
                            / sxx
                        )
                    )
                )

                z_score = 1.96

                training_df["ci_upper"] = (
                    training_df["trend"]
                    + z_score * standard_error
                )

                training_df["ci_lower"] = (
                    training_df["trend"]
                    - z_score * standard_error
                )

                trend_line, = plt.plot(
                    training_df["interval"],
                    training_df["trend"],
                    color=trend_line_color,
                    linewidth=trend_linewidth,
                    linestyle=trend_linestyle,
                    label=(
                        f"Trend "
                        f"({training_start:%Y-%m}"
                        f" + {trend_input_months} mo)"
                    ),
                    zorder=12
                )

                if show_confidence_band:

                    confidence_band = plt.fill_between(
                        training_df["interval"],
                        training_df["ci_lower"],
                        training_df["ci_upper"],
                        color=confidence_fill_color,
                        alpha=confidence_alpha,
                        label="95% Confidence Band",
                        zorder=8
                    )

                projection_anchor = (
                    pd.Timestamp(
                        ts["interval"].max()
                    ).to_period("M")
                    .to_timestamp()
                )

                future_dates = pd.date_range(
                    start=projection_anchor,
                    periods=projection_months + 1,
                    freq="MS"
                )

                future_x = (
                    future_dates
                    - base_date
                ).total_seconds() / 86400.0

                future_census = (
                    intercept
                    + slope * future_x
                )

                projection_standard_error = np.sqrt(
                    mse * (
                        (1 / n)
                        +
                        (
                            (future_x - mean_x) ** 2
                            / sxx
                        )
                    )
                )

                future_upper = (
                    future_census
                    + z_score * projection_standard_error
                )

                future_lower = (
                    future_census
                    - z_score * projection_standard_error
                )

                projection_df = pd.DataFrame({
                    "interval": future_dates,
                    "census": future_census,
                    "ci_upper": future_upper,
                    "ci_lower": future_lower,
                    "record_type": "projection"
                })

                projection_df["month_offset"] = range(
                    len(projection_df)
                )

                table_rows = []

                for i in range(projection_table_rows):

                    month_offset = (
                        projection_table_start_month
                        + i * projection_table_interval_months
                    )

                    matching_row = projection_df[
                        projection_df["month_offset"]
                        == month_offset
                    ]

                    if matching_row.empty:
                        continue

                    projected_value = (
                        matching_row.iloc[0]["census"]
                    )

                    facility_room_need = (
                        projected_value / capacity_threshold_pct
                        if capacity_threshold_pct not in [None, 0]
                        else np.nan
                    )

                    table_rows.append({
                        "Period": format_projection_period(
                            month_offset
                        ),
                        "Projected Facility\nRoom Need": round(
                            facility_room_need,
                            1
                        )
                    })

                projection_table_df = pd.DataFrame(table_rows)

                plot_projection_df = projection_df[
                    projection_df["month_offset"]
                    <= projection_plot_months
                ]

                if not plot_projection_df.empty:
                    max_projection_date = (
                        plot_projection_df["interval"].max()
                    )

                    plt.xlim(
                        ts["interval"].min(),
                        max_projection_date
                    )

                projection_line, = plt.plot(
                    plot_projection_df["interval"],
                    plot_projection_df["census"],
                    color=projection_line_color,
                    linewidth=projection_linewidth,
                    linestyle=projection_linestyle,
                    label=(
                        f"Projection "
                        f"({projection_months} mo)"
                    ),
                    zorder=13
                )

                if show_confidence_band:

                    plt.fill_between(
                        plot_projection_df["interval"],
                        plot_projection_df["ci_lower"],
                        plot_projection_df["ci_upper"],
                        color=confidence_fill_color,
                        alpha=confidence_alpha,
                        zorder=7
                    )

                logger.info(
                    f"[{VISUAL_ID}] Projection records generated: "
                    f"{len(projection_df):,}"
                )

            else:

                logger.warning(
                    f"[{VISUAL_ID}] Not enough records "
                    f"for trend projection."
                )

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

        output_df = ts.copy()

        output_df["record_type"] = "actual"

        if (
            enable_trend_projection
            and not projection_df.empty
        ):

            output_df = pd.concat(
                [
                    output_df,
                    projection_df[
                        [
                            "interval",
                            "census",
                            "record_type"
                        ]
                    ]
                ],
                ignore_index=True
            )

        output_df.to_csv(
            output_path,
            index=False
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

        if trend_line is not None:

            legend_handles.append(
                trend_line
            )

            legend_labels.append(
                trend_line.get_label()
            )

        if projection_line is not None:

            legend_handles.append(
                projection_line
            )

            legend_labels.append(
                projection_line.get_label()
            )

        if confidence_band is not None:

            legend_handles.append(
                confidence_band
            )

            legend_labels.append(
                "95% Confidence Band"
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

        projection_table_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id=f"{VISUAL_ID}_projection_table",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        save_projection_table_png(
            df=projection_table_df,
            output_file=projection_table_output_file,
            font_family=font_family
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

            if (
                enable_trend_projection
                and not projection_df.empty
            ):

                for _, row in projection_df.iterrows():

                    rdb_rows.append({

                        "run_id": params.get("run_id"),
                        "visual_id": VISUAL_ID,

                        "client_name": params.get(
                            "client_name"
                        ),

                        "domain": params.get("domain"),
                        "cohort_id": params.get(
                            "cohort_id"
                        ),

                        "domain_cohort":
                            f"{params.get('domain')}."
                            f"{params.get('cohort_id')}",

                        "dimension": "interval",

                        "dimension_value":
                            row["interval"],

                        "dimension_value_label":
                            row["interval"].strftime(
                                "%Y-%m-%d"
                            ),

                        "secondary_dimension":
                            "record_type",

                        "secondary_dimension_value":
                            "projection",

                        "metric":
                            "ed_census_projection",

                        "metric_type":
                            "forecast",

                        "value":
                            float(row["census"]),

                        "start_date":
                            start_date,

                        "end_date":
                            end_date,

                        "report_title":
                            chart_title

                    })       

        logger.info(f"[{VISUAL_ID}] Outputs saved: CSV and PNG")

        return {
            "output_path": png_path,
            "rdb": rdb_rows
        }

    except Exception as e:
        logger.error(f"[{VISUAL_ID}] Failed: {str(e)}")