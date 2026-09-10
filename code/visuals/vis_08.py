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
from statsmodels.tsa.arima.model import ARIMA
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
    title=None,
    font_family="Segoe UI",
    font_size=9
):

    if df.empty:
        return None

    plt.rcParams["font.family"] = font_family

    fig_height = max(
        1.2,
        len(df) * 0.45
    )

    fig, ax = plt.subplots(
        figsize=(2.75, fig_height)
    )

    ax.axis("off")

    if title:
        ax.set_title(
            title,
            fontsize=11,
            fontweight="bold",
            pad=10
        )

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
        bbox_inches="tight",
        dpi=300
    )

    plt.close(fig)

    return output_file

def format_projection_period(months):

    years = months // 12
    remaining = months % 12

    if years > 0 and remaining > 0:
        return f"{years}y {remaining}m"

    if years > 0:
        return f"{years} Years"

    return f"{months} Months"

def build_projection_table(
    projection_df,
    projection_table_rows,
    projection_table_start_month,
    projection_table_interval_months,
    capacity_threshold_pct
):

    rows = []

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
            projected_value
            / capacity_threshold_pct
        )

        rows.append({
            "Period":
                format_projection_period(
                    month_offset
                ),
            "Projected Facility\nADP":
                round(
                    facility_room_need,
                    1
                )
        })

    return pd.DataFrame(rows)

def build_ols_projection(
    training_df,
    ts,
    projection_months,
    projection_table_rows,
    projection_table_start_month,
    projection_table_interval_months,
    capacity_threshold_pct
):

    base_date = training_df["interval"].min()

    x_train = (
        training_df["interval"] - base_date
    ).dt.total_seconds() / 86400.0

    y_train = training_df["census"]

    slope, intercept = np.polyfit(
        x_train,
        y_train,
        1
    )

    peak_observed_census = float(
        training_df["census"].max()
    )

    peak_anchor_date = training_df.loc[
        training_df["census"].idxmax(),
        "interval"
    ]

    trend_df = training_df.copy()

    trend_df["trend"] = (
        intercept + slope * x_train
    )

    projection_anchor = (
        pd.Timestamp(
            ts["interval"].max()
        )
        .to_period("M")
        .to_timestamp()
    )

    future_dates = pd.date_range(
        start=projection_anchor,
        periods=projection_months + 1,
        freq="MS"
    )

    future_x = (
        future_dates - base_date
    ).total_seconds() / 86400.0

    future_census = (
        intercept + slope * future_x
    )

    projection_df = pd.DataFrame({
        "interval": future_dates,
        "census": future_census,
        "record_type": "projection"
    })

    projection_df["month_offset"] = range(
        len(projection_df)
    )

    peak_future_x = (
        future_dates - peak_anchor_date
    ).total_seconds() / 86400.0

    peak_projection_df = pd.DataFrame({
        "interval": future_dates,
        "census": (
            peak_observed_census
            + slope * peak_future_x
        ),
        "record_type": "peak_projection"
    })

    peak_projection_df["month_offset"] = range(
        len(peak_projection_df)
    )

    projection_table_df = build_projection_table(
        projection_df,
        projection_table_rows,
        projection_table_start_month,
        projection_table_interval_months,
        capacity_threshold_pct
    )

    peak_projection_table_df = build_projection_table(
        peak_projection_df,
        projection_table_rows,
        projection_table_start_month,
        projection_table_interval_months,
        capacity_threshold_pct
    )

    return {
        "trend_df": trend_df,
        "projection_df": projection_df,
        "projection_table_df": projection_table_df,
        "peak_projection_df": peak_projection_df,
        "peak_projection_table_df": peak_projection_table_df,
        "peak_observed_census": peak_observed_census,
        "peak_anchor_date": peak_anchor_date
    }

def build_arima_projection(
    training_df,
    ts,
    projection_months,
    projection_table_rows,
    projection_table_start_month,
    projection_table_interval_months,
    capacity_threshold_pct,
    arima_p,
    arima_d,
    arima_q
):

    forecast_series = (
    ts
    .set_index("interval")
    .resample("MS")
    .mean()
    ["census"]
    )

    model = ARIMA(
        forecast_series,
        order=(
            arima_p,
            arima_d,
            arima_q
        )
    )

    fitted = model.fit()

    trend_df = training_df.copy()

    trend_df["trend"] = fitted.fittedvalues

    future_dates = pd.date_range(
        start=(
            pd.Timestamp(
                ts["interval"].max()
            )
            .to_period("M")
            .to_timestamp()
        ),
        periods=projection_months + 1,
        freq="MS"
    )

    forecast = fitted.forecast(
        steps=len(future_dates)
    )

    projection_df = pd.DataFrame({
        "interval": future_dates,
        "census": forecast.values,
        "record_type": "projection"
    })

    projection_df["month_offset"] = range(
        len(projection_df)
    )

    peak_observed_census = float(
        training_df["census"].max()
    )

    peak_anchor_date = training_df.loc[
        training_df["census"].idxmax(),
        "interval"
    ]

    forecast_peak_delta = (
        peak_observed_census
        - projection_df["census"].iloc[0]
    )

    peak_projection_df = projection_df.copy()

    peak_projection_df["census"] = (
        peak_projection_df["census"]
        + forecast_peak_delta
    )

    peak_projection_df["record_type"] = (
        "peak_projection"
    )

    projection_table_df = build_projection_table(
        projection_df,
        projection_table_rows,
        projection_table_start_month,
        projection_table_interval_months,
        capacity_threshold_pct
    )

    peak_projection_table_df = build_projection_table(
        peak_projection_df,
        projection_table_rows,
        projection_table_start_month,
        projection_table_interval_months,
        capacity_threshold_pct
    )

    return {
        "trend_df": trend_df,
        "projection_df": projection_df,
        "projection_table_df": projection_table_df,
        "peak_projection_df": peak_projection_df,
        "peak_projection_table_df": peak_projection_table_df,
        "peak_observed_census": peak_observed_census,
        "peak_anchor_date": peak_anchor_date
    }

def run(df, params, start_date, end_date, output_dir, generate_output_name):

    logger.info(f"[{VISUAL_ID}] Starting Facility Census Trend visualization")
    params = normalize_params(params)

    output_visual_id = VISUAL_ID

    try:

        # --------------------------------------------------
        # HELP MY DATAFRAME
        # --------------------------------------------------
        # --------------------------------------------------
        # TEMP DEBUG - CENSUS HELPER PARAMETERS
        # --------------------------------------------------
        logger.info(
            f"[{VISUAL_ID}] census_helper_csv="
            f"{params.get('census_helper_csv')}"
        )

        logger.info(
            f"[{VISUAL_ID}] census_helper_type="
            f"{params.get('census_helper_type')}"
        )

        logger.info(
            f"[{VISUAL_ID}] census_helper_operation="
            f"{params.get('census_helper_operation')}"
        )  
        
        ts, census_df = generate_census(
            df,
            start_date,
            end_date,
            census_helper_csv=params.get(
                "census_helper_csv"
            ),
            census_helper_type=params.get(
                "census_helper_type"
            ),
            census_helper_operation=params.get(
                "census_helper_operation"
            ),
            max_census_delta=None
        )

        logger.info(
            f"[{VISUAL_ID}] Building census timeline from "
            f"{len(df):,} encounters."
        )

        logger.info(
            f"[{VISUAL_ID}] Census dataset generated. "
            f"Intervals: {len(ts):,} "
            f"Census df: {len(census_df):,}"
        )

        enable_rdb = int(params.get("rdb_write", 0))
        rdb_rows = []

        above_line = None
        capacity_line = None
        avg_line = None
        trend_line = None
        projection_line = None

        # =========================================================
        # VISUALIZATION
        # =========================================================

        capacity_value = _get_float(params, "capacity_value", None)
        include_avg_line = _get_bool(params, "include_avg_line", True)
        capacity_threshold_pct = _get_float(params, "capacity_threshold_pct", 0.8)
        below_color = params.get("below_color", "black")
        above_color = params.get("above_color", "red")
        font_family = _get_str(
            params,
            "font_family",
            "Segoe UI"
        )
        plt.rcParams["font.family"] = font_family
        cohort_desc = params.get("cohort_desc", "")

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
            params.get("title_height", 0.4) or 0.6
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

        forecast_method = _get_str(
            params,
            "forecast_method",
            "ols"
        ).strip().lower()

        if enable_trend_projection:
            output_visual_id = (
                f"{VISUAL_ID}_{forecast_method}"
            )

        arima_p = int(
            _get_float(
                params,
                "arima_p",
                1
            ) or 1
        )

        arima_d = int(
            _get_float(
                params,
                "arima_d",
                1
            ) or 1
        )

        arima_q = int(
            _get_float(
                params,
                "arima_q",
                1
            ) or 1
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
        peak_marker = None

        trend_df = pd.DataFrame()
        projection_df = pd.DataFrame()
        projection_table_df = pd.DataFrame()

        peak_projection_df = pd.DataFrame()
        peak_projection_table_df = pd.DataFrame()

        peak_observed_census = None
        peak_anchor_date = None

        projection_table_df = pd.DataFrame(
            columns=[
                "Period",
                "Projected Facility ADP"
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

        #NEW DISPATCHER
        if enable_trend_projection:

            if trend_start_month:

                training_start = pd.to_datetime(
                    trend_start_month
                )

            else:

                training_start = (
                    ts["interval"].min()
                )

            training_end = (
                training_start
                + pd.DateOffset(
                    months=trend_input_months
                )
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

            if len(training_df) >= 5:

                if forecast_method == "ols":

                    forecast_results = (
                        build_ols_projection(
                            training_df=training_df,
                            ts=ts,
                            projection_months=projection_months,
                            projection_table_rows=projection_table_rows,
                            projection_table_start_month=projection_table_start_month,
                            projection_table_interval_months=projection_table_interval_months,
                            capacity_threshold_pct=capacity_threshold_pct
                        )
                    )

                elif forecast_method == "arima":

                    forecast_results = (
                        build_arima_projection(
                            training_df=training_df,
                            ts=ts,
                            projection_months=projection_months,
                            projection_table_rows=projection_table_rows,
                            projection_table_start_month=projection_table_start_month,
                            projection_table_interval_months=projection_table_interval_months,
                            capacity_threshold_pct=capacity_threshold_pct,
                            arima_p=arima_p,
                            arima_d=arima_d,
                            arima_q=arima_q
                        )
                    )

                else:

                    raise ValueError(
                        f"Unsupported forecast_method: "
                        f"{forecast_method}"
                    )

                trend_df = forecast_results[
                    "trend_df"
                ]

                projection_df = forecast_results[
                    "projection_df"
                ]

                projection_table_df = forecast_results[
                    "projection_table_df"
                ]

                peak_projection_df = forecast_results[
                    "peak_projection_df"
                ]

                peak_projection_table_df = forecast_results[
                    "peak_projection_table_df"
                ]

                peak_observed_census = forecast_results[
                    "peak_observed_census"
                ]

                peak_anchor_date = forecast_results[
                    "peak_anchor_date"
                ]

            else:
                logger.warning(
                    f"[{VISUAL_ID}] Insufficient data for "
                    f"{forecast_method.upper()} projection. "
                    f"Training records: {len(training_df)}"
                )

        if (
            enable_trend_projection
            and peak_anchor_date is not None
            and peak_observed_census is not None
        ):

            peak_marker = plt.scatter(
                [peak_anchor_date],
                [peak_observed_census],
                s=90,
                facecolors="white",
                edgecolors="red",
                linewidths=2,
                zorder=20,
                label=(
                    f"Observed Peak "
                    f"({peak_observed_census:.1f})"
                )
            )

            logger.info(
                f"[{VISUAL_ID}] Peak census anchor: "
                f"{peak_observed_census:.2f} "
                f"on {peak_anchor_date:%Y-%m-%d}"
            )

        if (
            enable_trend_projection
            and not trend_df.empty
            and "trend" in trend_df.columns
        ):

            trend_line, = plt.plot(
                trend_df["interval"],
                trend_df["trend"],
                color=trend_line_color,
                linewidth=trend_linewidth,
                linestyle=trend_linestyle,
                label=(
                    f"{forecast_method.upper()} Trend"
                ),
                zorder=12
            )

        plot_projection_df = projection_df.copy()

        if "month_offset" in plot_projection_df.columns:

            plot_projection_df = plot_projection_df[
                plot_projection_df["month_offset"]
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

        if not plot_projection_df.empty:

            projection_line, = plt.plot(
                plot_projection_df["interval"],
                plot_projection_df["census"],
                color=projection_line_color,
                linewidth=projection_linewidth,
                linestyle=projection_linestyle,
                label=(
                    f"{forecast_method.upper()} Projection "
                    f"({projection_months} mo)"
                ),
                zorder=13
            )

        if not projection_df.empty:

            logger.info(
                f"[{VISUAL_ID}] Projection records generated: "
                f"{len(projection_df):,}"
            )

        # =========================================================
        # OUTPUT CSV
        # =========================================================
        filename = generate_output_name(
            visual_id=output_visual_id,
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
            visual_id=output_visual_id,
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
                visual_id=f"{output_visual_id}_title",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        enable_trend_projection = bool(
            int(params.get("enable_trend_projection", 0))
        )

        if enable_trend_projection:

            projection_label = (
                "ARIMA Projection"
                if forecast_method == "arima"
                else "Linear Projection"
            )

            title_suffix = (
                f"Census with Capacity Line and {projection_label}"
            )

        else:

            title_suffix = (
                "Census with Capacity Line"
            )

        report_title = (
            f"{cohort_desc} | "
            f"Facility Daily "
            f"{title_suffix}"
        )

        save_title_png(
            title=report_title,
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

        if peak_marker is not None:

            legend_handles.append(
                peak_marker
            )

            legend_labels.append(
                f"Observed Peak ({peak_observed_census:.1f})"
            )

        legend_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id=f"{output_visual_id}_legend",
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
                visual_id=f"{output_visual_id}_projection_table",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        save_projection_table_png(
            df=projection_table_df,
            output_file=projection_table_output_file,
            title="Trend Projection",
            font_family=font_family
        )

        if peak_observed_census is not None:

            peak_kpi_output_file = os.path.join(
                output_dir,
                generate_output_name(
                    visual_id=f"{output_visual_id}_peak_point",
                    start_date=start_date,
                    end_date=end_date,
                    cohort_id=params.get("cohort_id"),
                    ext="png"
                )
            )

            peak_display = (
                f"{peak_observed_census:.1f}"
            )

            fig, ax = plt.subplots(
                figsize=(1.0, 0.45)
            )

            ax.axis("off")

            table = ax.table(
                cellText=[[peak_display]],
                colLabels=["Observed Peak"],
                cellLoc="center",
                colLoc="center",
                loc="center"
            )

            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1.5, 1.6)

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

            fig.subplots_adjust(
                left=0,
                right=1,
                top=1,
                bottom=0
            )

            plt.savefig(
                peak_kpi_output_file,
                dpi=int(dpi),
                bbox_inches="tight",
                pad_inches=0
            )

            plt.close(fig)

            logger.info(
                f"[{VISUAL_ID}] peak KPI written: "
                f"{peak_kpi_output_file}"
            )

        peak_projection_table_output_file = os.path.join(
            output_dir,
            generate_output_name(
                visual_id=f"{output_visual_id}_peak_projection_table",
                start_date=start_date,
                end_date=end_date,
                cohort_id=params.get("cohort_id"),
                ext="png"
            )
        )

        if not peak_projection_table_df.empty:

            save_projection_table_png(
                df=peak_projection_table_df,
                output_file=peak_projection_table_output_file,
                title="Peak Anchored Projection",
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

                    "report_title": report_title
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
                            report_title

                    })       

        logger.info(f"[{VISUAL_ID}] Outputs saved: CSV and PNG")

        return {
            "output_path": png_path,
            "rdb": rdb_rows
        }

    except Exception as e:
        logger.error(
            f"[{VISUAL_ID}] Failed: {str(e)}"
        )
        raise