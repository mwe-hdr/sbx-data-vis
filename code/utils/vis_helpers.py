import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import os
import logging
import datetime
from utils.date_helpers import df_date_splitter

logger = logging.getLogger(__name__)

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

    plt.close(fig)

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

def crop_image(
    crop_file,
    crop_top=0,
    crop_bottom=0,
    crop_left=0,
    crop_right=0
):

    from PIL import Image

    try:

        with Image.open(crop_file) as img:

            width, height = img.size

            left = int(
                width *
                (crop_left / 100.0)
            )

            right = int(
                width *
                (
                    1 -
                    crop_right / 100.0
                )
            )

            upper = int(
                height *
                (
                    crop_top / 100.0
                )
            )

            lower = int(
                height *
                (
                    1 -
                    crop_bottom / 100.0
                )
            )

            cropped = img.crop(
                (
                    left,
                    upper,
                    right,
                    lower
                )
            )

            cropped.save(crop_file)

    except Exception as e:
        logger.error(
            f"Image cropping failed: {e}"
        )

def generate_census(
    df,
    start_date,
    end_date,
    ao_duration_minutes=30,
    census_helper_csv=None,
    census_helper_type=None,
    census_helper_operation=None,
    max_census_delta=None
):

    df_all, df_reporting = df_date_splitter(
        df,
        start_date,
        end_date
    )

    df = df_all.copy()

    try:
        df = df.copy()

        # =========================
        # DATE WINDOW FILTER
        # =========================        
        df["effective_start"] = df["arrival_dtm"]
        df["effective_end"] = df["tmt_stop_dtm"]

        # PATIENTS WHO ARE BEING ACTIVELY TREATED (tmt_start_dtm is not null) → use arrival_dtm as effective start, tmt_stop_dtm as effective end (or end_date if null)
        mask_treatment = df["tmt_start_dtm"].notna()

        df.loc[mask_treatment, "effective_start"] = (
            df.loc[mask_treatment, "arrival_dtm"]
        )

        df.loc[mask_treatment, "effective_end"] = (
            df.loc[mask_treatment, "tmt_stop_dtm"]
            .fillna(end_date)
        )        

        # PATIENTS WHO ARRIVED ONLY (tmt_start_dtm is null) → use arrival_dtm as effective start, arrival_dtm + 30 minutes as effective end
        mask_arrival_only = (
            df["tmt_start_dtm"].isna() &
            df["tmt_stop_dtm"].isna()
        )

        df.loc[mask_arrival_only, "effective_end"] = (
            df.loc[mask_arrival_only, "arrival_dtm"]
            + pd.Timedelta(minutes=ao_duration_minutes)
        )

        arrival_only_count = mask_arrival_only.sum()

        logger.info(
            f"[census] Imputed {ao_duration_minutes}-minute census intervals for "
            f"{arrival_only_count:,} arrival-only encounters."
        )

        bad_window_mask = (
            df["effective_start"].isna() |
            df["effective_end"].isna() |
            (df["effective_end"] < df["effective_start"])
        )

        bad_window_count = bad_window_mask.sum()

        if bad_window_count > 0:
            logger.warning(
                f"[census] Excluding {bad_window_count:,} encounters"
                f"[census] Invalid window breakdown: "
                f"null_start={df['effective_start'].isna().sum():,}, "
                f"null_end={df['effective_end'].isna().sum():,}, "
                f"end_before_start={(df['effective_end'] < df['effective_start']).sum():,}"
            )

        df = df[~bad_window_mask].copy()

        # Include any record whose interval overlaps the requested window
        df = df[
            (df["effective_start"] <= end_date) &
            (df["effective_end"] >= start_date)
        ].copy()
 
        # =========================================================
        # VISIT WINDOWS
        # =========================================================
        df["start"] = df["effective_start"]

        df["end"] = (
            df["effective_end"]
            .clip(
                lower=start_date,
                upper=end_date
            )
            + pd.Timedelta(minutes=1)
        )

        # =========================================================
        # TIME GRID
        # =========================================================
        intervals = pd.date_range(start=start_date, end=end_date, freq="min")
        base = pd.DataFrame({"interval": intervals})

        # =========================================================
        # EVENTS
        # =========================================================
        start_events = (
            df[df["start"] >= start_date][["start"]]
            .rename(columns={"start": "interval"})
        )

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
            (df["effective_start"] < start_date) &
            (df["effective_end"] >= start_date)
        ].shape[0]

        ts["census"] = ts["delta"].cumsum()
        ts["census"] += initial_count

        ts["census"] = (
            pd.to_numeric(ts["census"], errors="coerce")
            .round()
            .astype("Int64")
        )

        helper_type = (
            str(census_helper_type or "")
            .strip()
            .lower()
        )

        helper_operation = (
            str(census_helper_operation or "")
            .strip()
            .lower()
        )

        if helper_type == "bypass":

            logger.info(
                f"[census] Using bypass file: "
                f"{census_helper_csv}"
            )

            ts = pd.read_csv(
                census_helper_csv,
                parse_dates=["interval"]
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

            return ts, ts.copy()

        elif helper_type == "operation":

            helper = pd.read_csv(
                census_helper_csv,
                parse_dates=["interval"]
            )

            required_columns = [
                "interval",
                "census"
            ]

            missing = [
                c
                for c in required_columns
                if c not in helper.columns
            ]

            if missing:
                raise ValueError(
                    f"Helper file missing columns: "
                    f"{missing}"
                )

            helper["interval"] = pd.to_datetime(
                helper["interval"],
                errors="raise"
            )

            helper["census"] = pd.to_numeric(
                helper["census"],
                errors="raise"
            )

            merged = ts.merge(
                helper,
                on="interval",
                how="left",
                suffixes=("", "_helper")
            )

            merged["census_helper"] = (
                merged["census_helper"]
                .fillna(0)
            )

            if helper_operation == "subtract":

                merged["census"] = (
                    merged["census"]
                    - merged["census_helper"]
                )

            elif helper_operation == "add":

                merged["census"] = (
                    merged["census"]
                    + merged["census_helper"]
                )

            elif helper_operation == "multiply":

                merged["census"] = (
                    merged["census"]
                    * merged["census_helper"]
                )

            elif helper_operation == "divide":

                merged["census"] = (
                    merged["census"]
                    / merged["census_helper"]
                    .replace(0, np.nan)
                )

            else:

                raise ValueError(
                    f"Unsupported census helper operation: "
                    f"{helper_operation}"
                )

            ts = merged[
                ["interval", "census"]
            ].copy()

            ts["census"] = (
                pd.to_numeric(
                    ts["census"],
                    errors="coerce"
                )
            )

            logger.info(
                f"[census] Helper operation applied: "
                f"{helper_operation}"
            )

        if max_census_delta is not None:

            try:

                max_census_delta = float(max_census_delta)

                ts = (
                    ts.sort_values("interval")
                    .reset_index(drop=True)
                )

                prev_delta = (
                    ts["census"] -
                    ts["census"].shift(1)
                ).abs()

                next_delta = (
                    ts["census"] -
                    ts["census"].shift(-1)
                ).abs()

                outlier_mask = (
                    (prev_delta > max_census_delta) &
                    (next_delta > max_census_delta)
                )

                outlier_count = int(outlier_mask.sum())

                if outlier_count > 0:

                    logger.info(
                        f"[census] Clipping "
                        f"{outlier_count:,} census outliers "
                        f"using max_delta={max_census_delta}"
                    )

                    ts.loc[outlier_mask, "census"] = pd.NA

                    ts["census"] = (
                        ts["census"]
                        .interpolate(method="linear")
                        .ffill()
                        .bfill()
                    )

            except Exception as e:

                logger.warning(
                    f"[census] Outlier clipping failed: {e}"
                )
                
        return ts, df

    except Exception as e:
        logger.error(f"Census generation failed: {e}")
        return pd.DataFrame()

def map_arrival_method(value):

    if pd.isna(value):
        return "Other"

    txt = str(value).strip().lower()

    ambulance_terms = [
        "ambulance",
        "medical flight",
        "hospital transport",
        "tc bls stretcher",
        "tc als stretcher",
        "tc critical care team",
        "tc pals stretcher",
        "tc bariatric",
        "ems"
    ]

    if any(term in txt for term in ambulance_terms):
        return "EMT"

    if (
        txt == "police"
        or "police" in txt
        or "sheriff" in txt
    ):
        return "Police"

    if (
        "wheelchair" in txt
        or "wheelchair van" in txt
    ):
        return "Wheelchair"

    car_walk_terms = [
        "car",
        "walk",
        "ambulatory",
        "assist from vehicle",
        "self",
        "taxi",
        "public transportation",
        "bus",
        "community assistance"
    ]

    if any(term in txt for term in car_walk_terms):
        return "Car / Walk-in"

    return "Other"

def map_disposition(value):
    """
    Standardized ED disposition mapping.

    Returns:
        Observation
        Inpatient
        Transfer
        Expired
        Discharge
        Exit w/o Care
        Unknown
    """

    if pd.isna(value):
        return "Unknown"

    txt = str(value).strip().lower()

    if txt == "":
        return "Unknown"

    # Observation (must be checked before inpatient)
    if (
        "observation" in txt
        or txt.startswith("obs")
        or "obs unit" in txt
    ):
        return "Observation"

    # Inpatient
    if (
        "admit" in txt
        or "admitted" in txt
        or "inpatient" in txt
    ):
        return "Inpatient"

    # Transfer
    if "transfer" in txt:
        return "Transfer"

    # Expired
    if (
        "expired" in txt
        or "death" in txt
        or "deceased" in txt
        or "doa" in txt
        or "pronounced dead" in txt
    ):
        return "Expired"

    # Exit Without Care
    if (
        "lwbs" in txt
        or "left without being seen" in txt
        or "left before triage" in txt
        or "left prior to triage" in txt
        or "left without treatment" in txt
        or "left during treatment" in txt
        or "against medical advice" in txt
        or txt == "ama"
    ):
        return "Exit w/o Care"

    # Discharge
    if (
        "discharge" in txt
        or "discharged" in txt
        or "home" in txt
    ):
        return "Discharge"

    return "Unknown"