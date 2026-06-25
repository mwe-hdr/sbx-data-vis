import pandas as pd
import matplotlib.ticker as mtick

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