import os
import logging
import pandas as pd

VISUAL_ID = "tbl_01"
logger = logging.getLogger(__name__)

def _apply_formatting(df, params):
    if not params:
        return df

    df_formatted = df.copy()

    for key, fmt in params.items():
        if not key.startswith("format."):
            continue

        col = key.replace("format.", "")

        if col not in df_formatted.columns:
            continue

        if fmt == "int":
            df_formatted[col] = df_formatted[col].astype(int)

        elif fmt == "comma":
            df_formatted[col] = df_formatted[col].apply(
                lambda x: f"{int(x):,}" if pd.notna(x) else ""
            )

        elif fmt == "float1":
            df_formatted[col] = df_formatted[col].apply(
                lambda x: f"{float(x):,.1f}" if pd.notna(x) else ""
            )

        elif fmt == "percent":
            df_formatted[col] = df_formatted[col].apply(
                lambda x: f"{float(x)*100:.1f}%" if pd.notna(x) else ""
            )

    return df_formatted


def _safe_numeric(series, fill_value=0):
    """
    Safely convert a pandas Series to numeric.
    Invalid values coerced to NaN, then filled.
    """
    return pd.to_numeric(series, errors="coerce").fillna(fill_value)


def run(df, params, start_date, end_date, output_dir, generate_output_name):
    """
    Table 01: Patient and Patient Days Summary by Year

    Spec:
    - Group by discharge_fiscal_year
    - patients = sum(count_of_patients)
    - patient_days = sum(total_days)
    """

    logger.info(f"[{VISUAL_ID}] Starting execution")

    # --------------------------------------------------
    # ✅ Required Columns Validation
    # --------------------------------------------------

    required_cols = {
        "discharge_fiscal_year",
        "count_of_patients",
        "total_days"
    }

    missing = required_cols - set(df.columns)
    if missing:
        logger.warning(f"[{VISUAL_ID}] Missing required columns: {missing}")
        return

    if df.empty:
        logger.warning(f"[{VISUAL_ID}] Input dataframe is empty")
        return

    # --------------------------------------------------
    # ✅ Data Preparation
    # --------------------------------------------------

    working_df = df.copy()

    logger.info(f"[{VISUAL_ID}] Input rows: {len(working_df):,}")

    # Ensure numeric fields
    working_df["count_of_patients"] = _safe_numeric(
        working_df["count_of_patients"], fill_value=0
    )

    working_df["total_days"] = _safe_numeric(
        working_df["total_days"], fill_value=0
    )

    # Ensure year is usable
    working_df["discharge_fiscal_year"] = pd.to_numeric(
        working_df["discharge_fiscal_year"], errors="coerce"
    )

    # Drop rows with invalid year
    working_df = working_df.dropna(subset=["discharge_fiscal_year"])

    if working_df.empty:
        logger.warning(f"[{VISUAL_ID}] No valid rows after cleaning")
        return

    # --------------------------------------------------
    # ✅ Aggregation
    # --------------------------------------------------

    try:
        agg_df = (
            working_df
            .groupby("discharge_fiscal_year", as_index=False)
            .agg(
                patients=("count_of_patients", "sum"),
                patient_days=("total_days", "sum")
            )
        )
    except Exception as e:
        logger.error(f"[{VISUAL_ID}] Aggregation failed: {e}")
        return

    if agg_df.empty:
        logger.warning(f"[{VISUAL_ID}] Aggregation returned empty dataset")
        return

    # --------------------------------------------------
    # ✅ Sorting
    # --------------------------------------------------

    agg_df = agg_df.sort_values("discharge_fiscal_year")

    # Convert to integer where appropriate
    for col in ["discharge_fiscal_year", "patients", "patient_days"]:
        agg_df[col] = pd.to_numeric(agg_df[col], errors="coerce").fillna(0)

    agg_df["discharge_fiscal_year"] = agg_df["discharge_fiscal_year"].astype(int)
    agg_df["patients"] = agg_df["patients"].astype(int)
    agg_df["patient_days"] = agg_df["patient_days"].astype(int)

    logger.info(f"[{VISUAL_ID}] Output rows: {len(agg_df):,}")

    # --------------------------------------------------
    # ✅ Output
    # --------------------------------------------------

    try:
        filename = generate_output_name(
            visual_id=VISUAL_ID,
            start_date=start_date,
            end_date=end_date,
            cohort_id=(params or {}).get("cohort_id"),
            ext="csv"
        )

        output_path = os.path.join(output_dir, filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        output_df = _apply_formatting(agg_df, params)

        params = params or {}

        title = params.get("title", "")
        subtitle = params.get("cohort_desc")

        with open(output_path, "w", newline="", encoding="utf-8") as f:

            # Row 1 — title
            if title:
                f.write(f"{title}\n")
            else:
                f.write("\n")

            # Row 2 — subtitle
            logger.info(f"[{VISUAL_ID}] cohort_desc value: {params.get('cohort_desc')}")
            if subtitle:
                f.write(f"{subtitle}\n")
            else:
                logger.warning(f"[{VISUAL_ID}] Missing cohort_desc — writing blank subtitle")
                f.write("\n")

            # Row 3 — blank spacer
            f.write("\n")

            # Table
            output_df.to_csv(f, index=False, quoting=1)

        logger.info(f"[{VISUAL_ID}] Saved output to: {output_path}")

    except Exception as e:
        logger.error(f"[{VISUAL_ID}] Failed to save output: {e}")
        return