import os
import logging
import shutil
import pandas as pd
import importlib
import argparse
import time
from concurrent.futures import (
    ProcessPoolExecutor,
    as_completed
)

from utils.io_helpers import (
    load_data,
    load_driver,
    load_params,
    load_cohort_params,
)

from utils.processing_helpers import (
    apply_filter,
    initialize_run,
    generate_output_name,
    build_processing_driver,
    load_processing_driver,
    row_to_params,
    normalize_reporting_window,
    combine_processing_drivers
)

from utils.mapping_helpers import (
    load_mapping_file,
    apply_standard_mappings
)

from utils.pptx_helpers import (
    build_powerpoint
)


# =========================
# CONFIG
# =========================
DOMAINS = {
    "inpatient": {
        "data_file": "ecu_hospital_encounters_export.csv",
        "cohort_dir": "inpatient",
        "domain": "inpatient"
    },

    "surgery_ts": {
        "data_file": "ecu_surgery_export.csv",
        "cohort_dir": "surgery_ts",
        "domain": "surgery_ts"
    },

    "surgery_alt": {
        "data_file": "ecu_surgery_and_gi_export_flat.csv",
        "cohort_dir": "surgery_alt",
        "domain": "surgery_alt"
    },    

    "emergency": {
        "data_file": "rmc_emergency_export.csv",
        "cohort_dir": "ed",
        "domain": "ed"
    },
    
    "adf": {
        "data_file": "lc_adf_booking_housing_classification_chronic_detox.csv",
        "cohort_dir": "adf",
        "domain": "adf"
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
RUNS_DIR = os.path.join(
    BASE_DIR,
    "data",
    "runs"
)
VIS_DRIVER_FILE = os.path.join(PARAM_DIR, "vis_driver.csv")
SUMMARY_REPORT_DRIVER_FILE = os.path.join(
    PARAM_DIR,
    "summary_report_driver.csv"
)

VALID_MODES = {
    "parameters_only",
    "full_reports",
    "summary_report"
}

PROCESSING_MODE = os.getenv(
    "PROCESSING_MODE",
    "full_reports"
).strip().lower()

if PROCESSING_MODE in {
    "full_processing",
    "full_reports"
}:
    PROCESSING_MODE = "full_reports"

elif PROCESSING_MODE not in VALID_MODES:
    raise ValueError(
        f"[main] Unsupported PROCESSING_MODE: "
        f"{PROCESSING_MODE}"
    )

MAPPINGS_FILE = os.path.join(
    PARAM_DIR,
    "mappings.csv"
)
mappings = load_mapping_file(
    MAPPINGS_FILE
)
# =========================
# DYNAMIC VISUAL LOADER
# =========================
def get_visual_function(visual_id):
    try:
        module = importlib.import_module(f"visuals.{visual_id}")
        return module.run
    except Exception as e:
        logging.error(f"[main] Failed to load {visual_id}: {str(e)}")
        return None

def get_summary_report_function(report_id):

    try:

        module = importlib.import_module(
            f"summary_reports.{report_id}"
        )

        return module.run

    except Exception as e:

        logging.error(
            f"[main] Failed to load summary report "
            f"{report_id}: {e}"
        )

        return None

def get_enabled_cohorts():

    vis_df = load_driver(
        VIS_DRIVER_FILE
    )

    processing_driver_df = (
        load_processing_driver(
            os.path.join(
                PARAM_DIR,
                "processing_driver.csv"
            )
        )
    )

    enabled_visuals = set(

        vis_df[
            pd.to_numeric(
                vis_df["enabled"],
                errors="coerce"
            )
            .fillna(0)
            .astype(int)
            == 1
        ]["visual_id"]

    )

    cohorts = set()

    for _, row in processing_driver_df.iterrows():

        if (
            str(
                row.get(
                    "active_flag",
                    "Y"
                )
            ).upper()
            not in {
                "Y",
                "YES",
                "TRUE",
                "1"
            }
        ):
            continue

        if row["visual_id"] not in enabled_visuals:
            continue

        cohorts.add(
            row["cohort_id"]
        )

    return sorted(cohorts)

def load_summary_rdb(run_id):

    rdb_file = os.path.join(
        RUNS_DIR,
        run_id,
        "outputs",
        "rdb_domain_cohort_metrics.csv"
    )

    if not os.path.exists(rdb_file):

        raise FileNotFoundError(
            rdb_file
        )

    logging.info(
        f"[summary_report] Loading {rdb_file}"
    )

    return pd.read_csv(
        rdb_file
    )

def run_summary_reports(
    rdb_df,
    driver_df,
    cohort_ids,
    output_dir,
    run_id
):

    for cohort_id in cohort_ids:

        cohort_rdb = rdb_df[
            rdb_df["cohort_id"]
            ==
            cohort_id
        ].copy()

        if cohort_rdb.empty:

            logging.warning(
                f"[summary_report] "
                f"No RDB records for "
                f"{cohort_id}"
            )

            continue

        cohort_output_dir = os.path.join(
            output_dir,
            cohort_id
        )

        os.makedirs(
            cohort_output_dir,
            exist_ok=True
        )

        for _, row in driver_df.iterrows():

            if (
                int(
                    row.get(
                        "enabled",
                        0
                    )
                ) != 1
            ):
                continue

            report_id = row["report_id"]

            report_func = (
                get_summary_report_function(
                    report_id
                )
            )

            if report_func is None:
                continue

            params = row_to_params(
                row
            )

            params.update({

                "run_id": run_id,

                "cohort_id": cohort_id

            })

            report_func(

                cohort_rdb,

                params,

                cohort_output_dir,

                generate_output_name

            )

# =========================
# WORKER FUNCTION
# =========================
def execute_cohort_job(job):

    log_file = job["log_file"]

    logger = logging.getLogger()

    if not logger.handlers:

        logger.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "%(asctime)s | PID=%(process)d | %(processName)s | %(levelname)s | %(message)s"
        )

        file_handler = logging.FileHandler(
            log_file,
            mode="a"
        )

        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

    cohort_id = job["cohort_id"]

    cohort_df = job["cohort_df"]

    output_dir = job["output_dir"]

    rows = job["rows"]

    rdb_records = []

    logging.info(
        f"[worker] Started cohort {cohort_id}"
    )

    for row_dict in rows:

        visual_id = row_dict["visual_id"]

        params = row_dict["params"]

        start_date = row_dict["start_date"]

        end_date = row_dict["end_date"]

        visual_name = row_dict["visual_name"]

        vis_func = get_visual_function(visual_id)

        if vis_func is None:
            continue

        start = time.perf_counter()

        result = vis_func(
            cohort_df,
            params,
            start_date,
            end_date,
            output_dir,
            generate_output_name
        )

        elapsed = time.perf_counter() - start

        logging.info(
            f"[worker] {visual_id} "
            f"{cohort_id} "
            f"completed in {elapsed:.2f}s"
        )

        if result and "rdb" in result:

            for rec in result["rdb"]:

                rec["visual_id"] = visual_id
                rec["visual_name"] = visual_name

            rdb_records.extend(result["rdb"])

    logging.info(
        f"[worker] Finished cohort {cohort_id}"
    )

    return rdb_records

def mirror_processing_driver_to_params(run_dir):

    run_id = os.path.basename(run_dir)

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
            f"[main] Processing driver not found: {source_file}"
        )
        logging.info(f"[main] No processing driver found in {run_dir}")
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
            f"[main] Created backup: {backup_file}"
        )

    shutil.copy2(
        source_file,
        destination_file
    )

    logging.info(
        f"[main] Copied processing driver to: {destination_file}"
    )

# =========================
# PROCESSING DRIVER BUILDER
# =========================
def load_all_cohorts():

    logging.info(
        f"[load_all_cohorts] DOMAINS={list(DOMAINS.keys())}"
    )

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
    enabled_visuals,
    log_file
):

    rdb_records = []
    cohort_cache = {}
    cohort_jobs = {}

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

        visual_id = row.get("visual_id") 
        if not visual_id:
            logging.warning("[main] Skipping driver row without report identifier")
            continue
        if visual_id not in enabled_visuals:
            logging.info(
                f"[main] Skipping disabled visual: {visual_id}"
            )
            continue

        cohort_id = row.get("cohort_id")
        if not cohort_id:
            logging.warning("[main] Skipping driver row without cohort identifier")
            continue

        cohort_meta = cohorts.get(cohort_id)

        if not cohort_meta:

            logging.error(
                "[main] Processing driver references "
                f"unknown cohort_id={cohort_id}"
            )

            logging.error(
                f"[main] Available cohorts: "
                f"{list(cohorts.keys())}"
            )

            continue

        driver_filter = row.get("filter_str")
        current_filter = cohort_meta.get("filter")

        if str(driver_filter).strip() != str(current_filter).strip():

            logging.warning(
                "[main] Cohort filter mismatch "
                f"cohort={cohort_id} "
                f"driver_filter={driver_filter} "
                f"runtime_filter={current_filter}"
            )

        if cohort_id not in cohort_cache:
            cohort_cache[cohort_id] = apply_filter(df, cohort_meta.get("filter"))

        cohort_df = cohort_cache[cohort_id]
        if cohort_df.empty:
            logging.warning(f"[main] No data for {cohort_id}")
            continue

        cohort_output_dir = os.path.join(output_dir, cohort_id)
        os.makedirs(cohort_output_dir, exist_ok=True)

        start_date = row.get("start_date")
        end_date = row.get("end_date")

        start_date, end_date = normalize_reporting_window(
            start_date,
            end_date
        )

        params = row_to_params(row)
        params.update({
            "cohort_id": cohort_id,
            "cohort_name": cohort_meta.get("cohort_name"),
            "cohort_group": cohort_meta.get("cohort_group"),
            "cohort_tier": cohort_meta.get("cohort_tier"),
            "cohort_type_1": cohort_meta.get("cohort_type_1"),
            "cohort_type_2": cohort_meta.get("cohort_type_2"),
            "cohort_type_3": cohort_meta.get("cohort_type_3"),
            "cohort_type_4": cohort_meta.get("cohort_type_4"),
            "filter_str": cohort_meta.get("filter"),
            "cohort_desc": cohort_meta.get("description"),
            "visual_name": row.get("name"),
            "run_id": run_id,
            "domain": cohort_meta.get("domain"),
            "client_name": row.get("client_name"),
            "cohort_locations_file": COHORT_LOCATIONS_FILE,
            "year_type": row.get("year_type"),
            "write_rdb": row.get("write_rdb"),
            "start_date": start_date,
            "end_date": end_date,
            "visual_id": visual_id
        })

        logging.info(
            "[main] Queued "
            f"visual={visual_id} "
            f"cohort={cohort_id} "
            f"cohort_file={cohort_meta.get('cohort_file')} "
            f"cohort_desc={cohort_meta.get('description')}"
        )

        if cohort_id not in cohort_jobs:

            cohort_jobs[cohort_id] = {
                "cohort_df": cohort_df,
                "output_dir": cohort_output_dir,
                "rows": []
            }

        cohort_jobs[cohort_id]["rows"].append(
            {
                "visual_id": visual_id,
                "params": params,
                "start_date": start_date,
                "end_date": end_date,
                "visual_name": row.get("name")
            }
        )

    workers = min(
        12,
        len(cohort_jobs)
    )

    logging.info(
        f"[main] Executing "
        f"{len(cohort_jobs)} cohorts "
        f"using {workers} workers"
    )

    with ProcessPoolExecutor(
        max_workers=workers
    ) as executor:

        futures = []

        for cohort_id, payload in cohort_jobs.items():

            futures.append(

                executor.submit(
                    execute_cohort_job,
                    {
                        "cohort_id": cohort_id,
                        "cohort_df": payload["cohort_df"],
                        "output_dir": payload["output_dir"],
                        "rows": payload["rows"],
                        "log_file": log_file
                    }
                )
            )

        for future in as_completed(futures):

            try:

                cohort_rdb = future.result()

                if cohort_rdb:
                    rdb_records.extend(cohort_rdb)

            except Exception:

                logging.exception(
                    "[main] Cohort worker failed"
                )

    return rdb_records

# =========================
# ENTRY POINT
# =========================
parser = argparse.ArgumentParser()

parser.add_argument(
    "--run-id",
    default=None,
    help="Externally supplied run identifier"
)

parser.add_argument(
    "--summary-run-id",
    default=None,
    help="Run ID containing RDB outputs"
)

parser.add_argument(
    "--test",
    type=int,
    default=None,
    metavar="N",
    help=(
        "Process a random sample of N rows from the "
        "processing driver for testing"
    )
)

parser.add_argument(
    "--combine-parameters",
    nargs="+",
    metavar="RUN_ID",
    help=(
        "Combine processing_driver.csv files from one or more "
        "parameter-generation runs"
    )
)

parser.add_argument(
    "--update-processing-driver",
    action="store_true",
    help=(
        "Overwrite input/params/processing_driver.csv "
        "when rebuilding processing driver"
    )
)

parser.add_argument(
    "--powerpoint",
    action="store_true",
    help="Generate PowerPoint from a completed run"
)

parser.add_argument(
    "--ppt-run-id",
    default=None,
    help="Run ID containing output folders"
)

parser.add_argument(
    "--ppt-output",
    default=None,
    help="Output PPTX file"
)

args = parser.parse_args()

if args.combine_parameters:
    
    run_dir, output_dir, log_file = initialize_run(
    args.run_id
    )

    output_file = os.path.join(
        run_dir,
        "processing_driver.csv"
    )

    combine_processing_drivers(
        run_ids=args.combine_parameters,
        runs_dir=RUNS_DIR,
        output_file=output_file
    )

    if args.update_processing_driver:
        mirror_processing_driver_to_params(
            run_dir
        )

    raise SystemExit(0)

if args.powerpoint:

    if not args.ppt_run_id:
        raise ValueError(
            "--ppt-run-id is required"
        )
    build_powerpoint(
        run_id=args.ppt_run_id,
        output_file=args.ppt_output
    )

    raise SystemExit(0)

if __name__ == "__main__":

    run_dir, output_dir, log_file = initialize_run(
    args.run_id
    )

    logging.info(f"[main] Run initialized: {run_dir}")

    run_id = os.path.basename(run_dir)

    terminal_log_file = os.path.join(
        RUNS_DIR,
        "terminal_logs",
        f"terminal_log_{args.run_id}.log"
    )

    driver_df = load_driver(VIS_DRIVER_FILE)

    enabled_visuals = set(
        driver_df[
            pd.to_numeric(
                driver_df["enabled"],
                errors="coerce"
            ).fillna(0).astype(int) == 1
        ]["visual_id"]
    )

    if PROCESSING_MODE == "summary_report":

        if not args.summary_run_id:

            raise ValueError(
                "--summary-run-id required"
            )

        rdb_df = load_summary_rdb(
            args.summary_run_id
        )

        summary_driver_df = pd.read_csv(
            SUMMARY_REPORT_DRIVER_FILE
        )

        cohort_ids = (
            get_enabled_cohorts()
        )

        run_summary_reports(

            rdb_df=rdb_df,

            driver_df=summary_driver_df,

            cohort_ids=cohort_ids,

            output_dir=output_dir,

            run_id=args.summary_run_id
        )

        raise SystemExit(0)

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
            f"[main] Processing driver generated successfully."
        )

        if args.update_processing_driver:
            mirror_processing_driver_to_params(run_dir)

            logging.info(
                f"[main] Updated input/params/processing_driver.csv"
            )

        raise SystemExit(0)

    processing_driver_file = os.path.join(PARAM_DIR, "processing_driver.csv")
    if not os.path.exists(processing_driver_file):
        logging.error(f"[main] Missing processing driver: {processing_driver_file}")
        raise SystemExit(1)

    processing_driver_df = load_processing_driver(processing_driver_file)

    if args.test is not None:

        if args.test <= 0:
            raise ValueError("--test must be greater than 0")

        sample_size = min(
            args.test,
            len(processing_driver_df)
        )

        processing_driver_df = (
            processing_driver_df
            .sample(
                n=sample_size,
                random_state=42
            )
            .reset_index(drop=True)
        )

        logging.info(
            f"[main] TEST MODE ENABLED: "
            f"selected {sample_size} random rows "
            f"from processing_driver.csv"
        )

    if processing_driver_df.empty:
        logging.error(f"[main] Processing driver file is empty.")
        raise SystemExit(1)

    logging.info(f"[main] Using processing driver: {processing_driver_file}")

    all_rdb_records = []

    for domain, config in DOMAINS.items():

        logging.info(f"[main] Starting domain: {domain}")

        expected_domain = str(config.get("domain", domain)).strip().lower()

        domain_driver_df = processing_driver_df[
            processing_driver_df["domain"].astype(str).str.strip().str.lower() == expected_domain
        ].copy()

        if domain_driver_df.empty:
            logging.info(
                f"[main] No processing requests for domain {domain}; skipping."
            )
            continue

        df = load_data(
            os.path.join(
                INPUT_DIR,
                config["data_file"]
            )
        )

        data_path = os.path.join(
            INPUT_DIR,
            config["data_file"]
        )

        logging.info(f"[main] Loading file: {data_path}")

        df = load_data(data_path)

        logging.info(f"[main] Loaded shape: {df.shape}")
        logging.info(f"[main] Columns: {df.columns.tolist()}")

        domain_mapping = mappings.get(
            expected_domain,
            {}
        )

        df = apply_standard_mappings(
            df,
            domain_mapping
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
            enabled_visuals,
            log_file
        )

        if rdb:
            all_rdb_records.extend(rdb)

    master_rdb_df = pd.DataFrame(all_rdb_records)

    master_rdb_file = os.path.join(
        output_dir,
        "rdb_domain_cohort_metrics.csv"
    )

    master_rdb_df.to_csv(
        master_rdb_file,
        index=False
    )

    logging.info(
        "[main] RUN COMPLETE | "
        f"run_id={run_id} | "
        f"domains_processed={len(DOMAINS)} | "
        f"rdb_records={len(master_rdb_df)} | "
        f"output_dir={output_dir} | "
        f"rdb_file={master_rdb_file}"
    )

    raise SystemExit(0)