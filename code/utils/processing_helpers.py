from datetime import datetime
import os
import logging
import pandas as pd

from utils.io_helpers import load_params

def build_processing_driver(
    cohorts,
    visual_driver_df,
    param_dir,
    output_file
):
    """
    Build processing driver file.

    Creates one row per cohort x report combination using each report
    parameter file as the default parameter set.
    """

    logging.info("Building processing driver")

    driver_rows = []

    enabled_reports = visual_driver_df.copy()

    if "enabled" in enabled_reports.columns:
        enabled_reports = enabled_reports[
            enabled_reports["enabled"]
            .astype(str)
            .str.upper()
            .isin(["Y", "YES", "TRUE", "1"])
        ]

    for _, report_row in enabled_reports.iterrows():

        report_id = report_row.get("visual_id") or report_row.get("report_id")

        if not report_id:
            logging.warning("Skipping row without report identifier")
            continue

        try:
            params_df = load_params(param_dir, report_id)
        except Exception as e:

            logging.error(
                f"Unable to load params for {report_id}: {e}"
            )

            continue

        report_domain = str(report_row.get("domain", "")).strip().lower()

        for cohort_id, cohort_meta in cohorts.items():

            cohort_meta = cohort_meta or {}

            cohort_domain = str(
                cohort_meta.get("domain") or cohort_meta.get("group") or ""
            ).strip().lower()

            if cohort_domain and report_domain and cohort_domain != report_domain:
                continue

            row = {
                "active_flag": "Y",
                "report_id": report_id,
                "visual_id": report_id,
                "domain": cohort_meta.get("domain"),
                "cohort_id": cohort_id,
                "cohort_file": cohort_meta.get("cohort_file"),
                "cohort_desc": cohort_meta.get("description"),
                "filter_str": cohort_meta.get("filter"),
                "group": cohort_meta.get("group"),
                "name": cohort_meta.get("name")
            }

            # include vis_driver metadata
            for col in visual_driver_df.columns:
                if col not in row:
                    row[col] = report_row[col]

            # flatten report parameters
            if not params_df.empty:

                for _, param_row in params_df.iterrows():

                    param_name = str(param_row["param"]).strip()

                    row[param_name] = param_row.get("value")

                    row[f"{param_name}_desc"] = (
                        param_row.get("description")
                    )

                    row[f"{param_name}_display"] = (
                        param_row.get("display")
                    )

                    row[f"{param_name}_format"] = (
                        param_row.get("display_format")
                    )

            driver_rows.append(row)

    driver_df = pd.DataFrame(driver_rows)

    if driver_df.empty:
        logging.warning("No processing driver rows generated")
        return driver_df

    system_cols = [
        "active_flag",
        "report_id",
        "visual_id",
        "domain",
        "cohort_id",
        "cohort_file",
        "cohort_desc",
        "filter_str",
        "group",
        "name"
    ]

    other_cols = [
        c for c in driver_df.columns
        if c not in system_cols
    ]

    driver_df = driver_df[
        system_cols + sorted(other_cols, key=str)
    ]

    os.makedirs(
        os.path.dirname(output_file),
        exist_ok=True
    )

    driver_df.to_csv(
        output_file,
        index=False
    )

    logging.info(
        f"Generated processing driver with {len(driver_df):,} rows"
    )
    logging.info(f"Saved processing driver: {output_file}")

    return driver_df


def load_processing_driver(file_path):

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Missing processing driver: {file_path}"
        )

    return pd.read_csv(file_path)


def row_to_params(row):

    system_fields = {
        "execution_id",
        "active_flag",
        "report_id",
        "visual_id",
        "domain",
        "cohort_id",
        "cohort_file",
        "cohort_desc",
        "filter_str",
        "group",
        "name",
        "client_name",
        "year_type",
        "write_rdb",
        "start_date",
        "end_date",
        "enabled",
        "type"
    }

    return {
        k: v
        for k, v in row.items()
        if k not in system_fields
    }

def apply_filter(df, filter_str):
    if df is None or df.empty:
        logging.warning("apply_filter: input dataframe is empty")
        return df

    if not filter_str or pd.isna(filter_str):
        logging.info("apply_filter: no filter provided; returning original dataframe")
        return df

    try:
        before_count = len(df)

        # Minimal normalization (safe + cheap)
        df_copy = df.copy()
        for col in df_copy.select_dtypes(include="object").columns:
            df_copy[col] = df_copy[col].str.strip()

        filtered_df = df_copy.query(filter_str, engine="python")

        after_count = len(filtered_df)

        logging.info(
            f"apply_filter: rows {before_count} → {after_count} | filter: {filter_str}"
        )

        return filtered_df

    except Exception as e:
        logging.error(f"apply_filter failed: {str(e)}")
        return df.iloc[0:0]
    
BASE_DIR = os.getcwd()
RUNS_DIR = os.path.join(BASE_DIR, "data", "runs")

def initialize_run():

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    run_dir = os.path.join(RUNS_DIR, f"run_{timestamp}")
    output_dir = os.path.join(run_dir, "outputs")

    os.makedirs(output_dir, exist_ok=True)

    # setup logging
    log_file = os.path.join(run_dir, "logfile.txt")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    return run_dir, output_dir


def generate_output_name(
    *,
    visual_id,
    start_date,
    end_date,
    cohort_id=None,
    ext="csv"
):
    def clean(val):
        if val is None:
            return ""

        return (
            str(val)
            .replace("/", "-")
            .replace("\\", "-")
            .replace(" ", "_")
            .replace(".", "_")
            .replace(":", "-")
        )

    parts = [clean(visual_id)]

    if cohort_id:
        parts.append(clean(cohort_id))

    if start_date and end_date:
        parts.append(f"{clean(start_date)}_to_{clean(end_date)}")

    filename = "__".join(parts) + f".{ext}"

    return filename
