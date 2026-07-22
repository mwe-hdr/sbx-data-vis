import os
import logging
import shutil
import pandas as pd
import importlib
import argparse

from utils.io_helpers import (
    load_data,
    load_driver,
    load_params,
    load_cohort_params
)

from utils.processing_helpers import (
    apply_filter,
    initialize_run,
    generate_output_name,
    build_processing_driver,
    load_processing_driver,
    row_to_params
)

# =========================
# CONFIG
# =========================
DOMAINS = {
    "inpatient": {
        "data_file": "nodata.csv",
        "cohort_dir": "inpatient",
        "domain": "inpatient"
    },

    "surgery": {
        "data_file": "nodata.csv",
        "cohort_dir": "surgery",
        "domain": "surgery"
    },

    "emergency": {
        "data_file": "rmc_emergency_export.csv",
        "cohort_dir": "ed",
        "domain": "ed"
    }
}

BASE_DIR = os.getcwd()
INPUT_DIR = os.path.join(BASE_DIR, "data", "input")
COHORT_LOCATIONS_FILE = os.path.join(
    INPUT_DIR,
    "geo",
    "cohort_locations",
    "cohort_locations.csv"
)
PARAM_DIR = os.path.join(INPUT_DIR, "params")
VIS_DRIVER_FILE = os.path.join(PARAM_DIR, "vis_driver.csv")
PROCESSING_MODE = os.getenv("PROCESSING_MODE", "parameters_only").strip().lower()
if PROCESSING_MODE in {"full_processing", "full_reports"}:
    PROCESSING_MODE = "full_reports"
elif PROCESSING_MODE != "parameters_only":
    raise ValueError(f"Unsupported PROCESSING_MODE: {PROCESSING_MODE}")

# =========================
# DYNAMIC VISUAL LOADER
# =========================
def get_visual_function(visual_id):
    try:
        module = importlib.import_module(f"visuals.{visual_id}")
        return module.run
    except Exception as e:
        logging.error(f"Failed to load {visual_id}: {str(e)}")
        return None


def mirror_processing_driver_to_params(run_dir):

    source_file = os.path.join(
        run_dir,
        "processing_driver.csv"
    )

    destination_file = os.path.join(
        PARAM_DIR,
        "processing_driver.csv"
    )

    if not os.path.exists(source_file):
        logging.warning(
            f"Processing driver not found: {source_file}"
        )
        return

    if os.path.exists(destination_file):

        backup_file = (
            destination_file
            + "."
            + run_id
            + ".bak"
        )

        shutil.copy2(
            destination_file,
            backup_file
        )

        logging.info(
            f"Created backup: {backup_file}"
        )

    shutil.copy2(
        source_file,
        destination_file
    )

    logging.info(
        f"Copied processing driver to: {destination_file}"
    )

# =========================
# PROCESSING DRIVER BUILDER
# =========================
def load_all_cohorts():

    all_cohorts = {}

    for domain, config in DOMAINS.items():

        domain_cohorts = load_cohort_params(
            os.path.join(
                PARAM_DIR,
                "cohorts",
                config["cohort_dir"]
            )
        )

        all_cohorts.update(domain_cohorts)

    return all_cohorts

# =========================
# MAIN EXECUTION LOOP
# =========================
def run_visuals(
    df,
    driver_df,
    cohorts,
    output_dir,
    enabled_visuals
):

    rdb_records = []
    cohort_cache = {}

    logging.info("[main] Loaded cohort keys:")
    for k in cohorts.keys():
        logging.info(f"[main] - {k}")

    for _, row in driver_df.iterrows():

        if str(row.get("active_flag", "Y")).upper() not in {"Y", "YES", "TRUE", "1"}:
            continue

        try:
            if int(row.get("enabled", 0)) != 1:
                continue
        except (TypeError, ValueError):
            if str(row.get("enabled", "")).upper() not in {"Y", "YES", "TRUE", "1"}:
                continue

        if str(row.get("type", "")).lower() != "cohort":
            continue

        report_id = row.get("visual_id") or row.get("report_id")
        if not report_id:
            logging.warning("[main] Skipping driver row without report identifier")
            continue
        if report_id not in enabled_visuals:
            logging.info(
                f"[main] Skipping disabled visual: {report_id}"
            )
            continue

        cohort_id = row.get("cohort_id")
        if not cohort_id:
            logging.warning("[main] Skipping driver row without cohort identifier")
            continue

        cohort_meta = cohorts.get(cohort_id)
        if not cohort_meta:
            logging.warning(f"[main] Unknown cohort_id in processing driver: {cohort_id}")
            continue

        if cohort_id not in cohort_cache:
            cohort_cache[cohort_id] = apply_filter(df, cohort_meta.get("filter"))

        cohort_df = cohort_cache[cohort_id]
        if cohort_df.empty:
            logging.warning(f"No data for {cohort_id}")
            continue

        cohort_output_dir = os.path.join(output_dir, cohort_id)
        os.makedirs(cohort_output_dir, exist_ok=True)

        params = row_to_params(row)
        params.update({
            "cohort_id": cohort_id,
            "filter_str": cohort_meta.get("filter"),
            "cohort_desc": cohort_meta.get("description"),
            "visual_name": row.get("name"),
            "run_id": run_id,
            "domain": cohort_meta.get("domain"),
            "client_name": row.get("client_name"),
            "cohort_locations_file": COHORT_LOCATIONS_FILE,
            "year_type": row.get("year_type"),
            "write_rdb": row.get("write_rdb"),
            "start_date": row.get("start_date"),
            "end_date": row.get("end_date"),
            "visual_id": report_id,
            "report_id": report_id
        })

        vis_func = get_visual_function(report_id)
        if vis_func is None:
            continue

        logging.info(f"[main] Injecting cohort_desc: {cohort_meta.get('description')}")

        result = vis_func(
            cohort_df,
            params,
            row.get("start_date"),
            row.get("end_date"),
            cohort_output_dir,
            generate_output_name
        )

        if result and "rdb" in result:
            for rec in result["rdb"]:
                rec["visual_id"] = report_id
                rec["visual_name"] = row.get("name")
            rdb_records.extend(result["rdb"])

    return rdb_records

# =========================
# ENTRY POINT
# =========================
parser = argparse.ArgumentParser()

parser.add_argument(
    "--update-processing-driver",
    action="store_true",
    help=(
        "Overwrite input/params/processing_driver.csv "
        "when rebuilding processing driver"
    )
)

args = parser.parse_args()

if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO)

    run_dir, output_dir = initialize_run()

    run_id = os.path.basename(run_dir)

    driver_df = load_driver(VIS_DRIVER_FILE)

    enabled_visuals = set(
        driver_df[
            pd.to_numeric(
                driver_df["enabled"],
                errors="coerce"
            ).fillna(0).astype(int) == 1
        ]["visual_id"]
    )

    processing_driver_file = os.path.join(run_dir, "processing_driver.csv")

    if PROCESSING_MODE == "parameters_only":

        all_cohorts = load_all_cohorts()

        build_processing_driver(
            cohorts=all_cohorts,
            visual_driver_df=driver_df,
            param_dir=PARAM_DIR,
            output_file=processing_driver_file
        )

        logging.info(
            "Processing driver generated successfully."
        )

        if args.update_processing_driver:
            mirror_processing_driver_to_params(run_dir)

            logging.info(
                "Updated input/params/processing_driver.csv"
            )

        raise SystemExit(0)

    processing_driver_file = os.path.join(PARAM_DIR, "processing_driver.csv")
    if not os.path.exists(processing_driver_file):
        logging.error(f"Missing processing driver: {processing_driver_file}")
        raise SystemExit(1)

    processing_driver_df = load_processing_driver(processing_driver_file)

    if processing_driver_df.empty:
        logging.error("Processing driver file is empty.")
        raise SystemExit(1)

    logging.info(f"Using processing driver: {processing_driver_file}")

    all_rdb_records = []

    for domain, config in DOMAINS.items():

        logging.info(f"Starting domain: {domain}")

        expected_domain = str(config.get("domain", domain)).strip().lower()

        domain_driver_df = processing_driver_df[
            processing_driver_df["domain"].astype(str).str.strip().str.lower() == expected_domain
        ].copy()

        if domain_driver_df.empty:
            logging.info(
                f"No processing requests for domain {domain}; skipping."
            )
            continue

        df = load_data(
            os.path.join(
                INPUT_DIR,
                config["data_file"]
            )
        )

        cohorts = load_cohort_params(
            os.path.join(
                PARAM_DIR,
                "cohorts",
                config["cohort_dir"]
            )
        )

        rdb = run_visuals(
            df,
            domain_driver_df,
            cohorts,
            output_dir,
            enabled_visuals
        )

        if rdb:
            all_rdb_records.extend(rdb)

    master_rdb_df = pd.DataFrame(all_rdb_records)

    master_rdb_df.to_csv(
        os.path.join(
            output_dir,
            "rdb_domain_cohort_metrics.csv"
        ),
        index=False
    )