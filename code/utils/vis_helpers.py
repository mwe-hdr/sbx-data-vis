import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import os
import logging

def normalize_params(params):
    if params is None:
        return {}

    if not isinstance(params, dict):
        try:
            params = dict(params)
        except Exception:
            return {}

    normalized = {}
    for key, value in params.items():
        try:
            normalized[key] = None if pd.isna(value) else value
        except Exception:
            normalized[key] = value

    return normalized

def save_title_png(
    title,
    subtitle,
    output_file,
    width=12,
    height=0.8,
    dpi=300,
    font_family="Segoe UI",
    title_fontsize=16,
    subtitle_fontsize=12,
    background_color="#d9d9d9",
    title_weight="bold",
    title_alignment="left"
):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(
        figsize=(width, height),
        dpi=dpi
    )

    fig.patch.set_facecolor(background_color)
    ax.set_facecolor(background_color)

    # Left-justified title

    ax.text(
        0.01,
        0.50,
        str(title),
        ha="left",
        va="center",
        fontsize=title_fontsize,
        fontweight=title_weight,
        fontfamily=font_family,
        transform=ax.transAxes
    )

    # Right-justified reporting period

    ax.text(
        0.99,
        0.50,
        str(subtitle),
        ha="right",
        va="center",
        fontsize=subtitle_fontsize,
        fontfamily=font_family,
        transform=ax.transAxes
    )

    ax.axis("off")

    plt.subplots_adjust(
        left=0,
        right=1,
        top=1,
        bottom=0
    )

    plt.savefig(
        output_file,
        bbox_inches="tight",
        pad_inches=0
    )

    plt.close()

def format_date_range(start_date, end_date):
    try:
        start = pd.to_datetime(start_date).date()
        end = pd.to_datetime(end_date).date()
        return f"({start} to {end})"
    except Exception:
        return f"({start_date} to {end_date})"

def apply_axis_range(ax, axis="y", min_val=None, max_val=None):
    """
    Apply axis range limits safely.

    Parameters
    ----------
    ax : matplotlib axis
    axis : str ("x" or "y")
    min_val : float or None
    max_val : float or None

    Behavior
    --------
    - Only applies limits if values are valid numbers
    - Supports partial overrides (only min or only max)
    - Prevents crashes from invalid input
    """

    try:
        # Validate axis
        if axis not in ("x", "y"):
            return

        # Convert safely
        def _safe_float(v):
            try:
                return float(v)
            except Exception:
                return None

        min_val = _safe_float(min_val)
        max_val = _safe_float(max_val)

        # Get current limits
        if axis == "y":
            current_min, current_max = ax.get_ylim()
        else:
            current_min, current_max = ax.get_xlim()

        # Determine new limits
        new_min = min_val if min_val is not None else current_min
        new_max = max_val if max_val is not None else current_max

        # Prevent invalid bounds
        if new_min >= new_max:
            return

        # Apply
        if axis == "y":
            ax.set_ylim(new_min, new_max)
        else:
            ax.set_xlim(new_min, new_max)

    except Exception:
        # Fail silently (consistent with helper philosophy)
        return

def apply_yaxis_format(ax, mode="percent", decimals=1, multiplier=100, suffix="%"):
    """
    Apply consistent y-axis formatting
    """
    try:
        decimals = int(decimals)
        multiplier = float(multiplier)

        if mode == "percent":
            if multiplier == 1:
                # already percent
                fmt = lambda x, _: f"{x:.{decimals}f}{suffix}"
            else:
                # proportion → percent
                fmt = lambda x, _: f"{x * multiplier:.{decimals}f}{suffix}"

            ax.yaxis.set_major_formatter(mtick.FuncFormatter(fmt))

        elif mode == "count":
            ax.yaxis.set_major_formatter(
                mtick.FuncFormatter(
                    lambda x, _: f"{int(x):,}"
                )
            )

        elif mode == "raw":
            ax.yaxis.set_major_formatter(
                mtick.FuncFormatter(
                    lambda x, _: f"{x:.{decimals}f}"
                )
            )

    except Exception:
        pass


def save_legend_png(
    handles,
    labels,
    output_file,
    ncol=4,
    width=8,
    dpi=300,
    height=1,
    font_family="Segoe UI",
    font_size=10
):
    
    legend_fig = plt.figure(
        figsize=(width, height)
    )

    legend_fig.legend(
        handles,
        labels,
        loc="center",
        ncol=ncol,
        frameon=False,
        prop={
            "family": font_family,
            "size": font_size
        }
    )

    legend_fig.savefig(
        output_file,
        transparent=True,
        bbox_inches="tight",
        dpi=dpi
    )

    plt.close(legend_fig)

    return output_file

def format_display_value(value, fmt):

    try:

        if pd.isna(value):
            return ""

        fmt = str(fmt).strip().lower()

        if fmt == "percent0":
            return f"{float(value):.0%}"

        if fmt == "percent1":
            return f"{float(value):.1%}"

        if fmt == "integer":
            return f"{int(float(value)):,}"

        if fmt == "decimal1":
            return f"{float(value):,.1f}"

        if fmt == "decimal2":
            return f"{float(value):,.2f}"

        if fmt == "hour24":
            return f"{int(float(value)):02d}:00"

        if fmt == "hour12":
            hour = int(float(value))

            am_pm = "AM" if hour < 12 else "PM"

            hour12 = hour % 12

            if hour12 == 0:
                hour12 = 12

            return f"{hour12}:00 {am_pm}"

        return str(value)

    except Exception:
        return str(value)

def get_display_parameters(params):

    display_params = []

    base_params = []

    for key in params.keys():

        if (
            key.endswith("_desc")
            or key.endswith("_display")
            or key.endswith("_format")
            or key.endswith("_display_order")
        ):
            continue

        if f"{key}_display" not in params:
            continue

        base_params.append(key)

    def sort_key(param_name):

        try:
            return int(
                params.get(
                    f"{param_name}_display_order",
                    999999
                )
            )

        except Exception:
            return 999999

    base_params = sorted(
        base_params,
        key=sort_key
    )

    for param_name in base_params:

        display_raw = params.get(
            f"{param_name}_display",
            0
        )

        try:

            display_flag = float(display_raw)

        except Exception:

            display_flag = 0

        if display_flag != 1:
            continue

        description = params.get(
            f"{param_name}_desc",
            param_name
        )

        display_format = params.get(
            f"{param_name}_format",
            ""
        )

        formatted_value = format_display_value(
            params.get(param_name),
            display_format
        )

        display_params.append({
            "description": description,
            "value": formatted_value
        })

    return display_params

def save_parameter_table_png(
    params,
    output_file,
    font_family="Segoe UI",
    font_size=10
):

    rows = []

    display_params = get_display_parameters(params)

    if not display_params:
        return None

    for item in display_params:

        value = item["value"]

        if item["description"] == "Length of peak period":
            value = f"{value} Hours"

        rows.append([item["description"]])
        rows.append([value])

    table_df = pd.DataFrame(
        rows,
        columns=["value"]
    )

    fig_height = max(
        1.8,
        len(table_df) * 0.40
    )

    plt.rcParams["font.family"] = font_family
    fig, ax = plt.subplots(
        figsize=(2.8, fig_height)
    )

    ax.axis("off")

    table = ax.table(
        cellText=table_df.values,
        loc="center",
        cellLoc="center"
    )

    table.auto_set_font_size(False)
    table.set_fontsize(font_size)
    table.scale(1.0, 1.5)

    for row_idx in range(len(table_df)):

        cell = table[(row_idx, 0)]
        cell.get_text().set_fontfamily(font_family)

        if row_idx % 2 == 0:

            cell.set_facecolor("#e6e6e6")

            cell.get_text().set_weight("bold")

        else:

            cell.set_facecolor("#ffffff")

    plt.tight_layout()

    plt.savefig(
        output_file,
        bbox_inches="tight"
    )

    plt.close()

    return output_file