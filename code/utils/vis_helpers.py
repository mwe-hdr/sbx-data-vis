import pandas as pd
import matplotlib.ticker as mtick

def format_date_range(start_date, end_date):
    try:
        start = pd.to_datetime(start_date).date()
        end = pd.to_datetime(end_date).date()
        return f"({start} to {end})"
    except Exception:
        return f"({start_date} to {end_date})"

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