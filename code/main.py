import os
import logging
import pandas as pd
import importlib

from utils.io_helpers import load_data, load_driver, load_params, load_cohort_params
from utils.run_helpers import initialize_run, generate_output_name
from utils.cohort_helpers import apply_filter

# =========================
# CONFIG
# =========================
BASE_DIR = os.getcwd()
INPUT_DIR = os.path.join(BASE_DIR, "data", "input")
PARAM_DIR = os.path.join(INPUT_DIR, "params")
COHORT_SUBDIR = "inpatient"  
COHORT_DIR = os.path.join(PARAM_DIR, "cohorts", COHORT_SUBDIR)

ED_LAYOUT_FILE = os.path.join(INPUT_DIR, "ecu_hospital_encounters_export.csv")
VIS_DRIVER_FILE = os.path.join(PARAM_DIR, "vis_driver.csv")

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

# =========================
# MAIN EXECUTION LOOP
# =========================
def run_visuals(df, driver_df, cohorts, output_dir):

    logging.info(f"[main] Loaded cohort keys:")
    for k in cohorts.keys():
        logging.info(f"[main] - {k}")

    for cohort_id, meta in cohorts.items():

        logging.info(f"Running FULL cohort_id: {cohort_id}")
        logging.info(f"[main] meta keys: {list(meta.keys())}")

        cohort_df = apply_filter(df, meta.get("filter"))

        if cohort_df.empty:
            logging.warning(f"No data for {cohort_id}")
            continue

        cohort_output_dir = os.path.join(output_dir, cohort_id)
        os.makedirs(cohort_output_dir, exist_ok=True)

        for _, row in driver_df.iterrows():

            if int(row["enabled"]) != 1:
                continue

            visual_id = row["visual_id"]

            vis_func = get_visual_function(visual_id)
            if vis_func is None:
                continue

            params = load_params(PARAM_DIR, visual_id) or {}
            params = dict(params)

            params["cohort_id"] = cohort_id
            params["filter_str"] = meta.get("filter")
            params["cohort_desc"] = meta.get("description")
            logging.info(f"[main] Injecting cohort_desc: {meta.get('description')}")

            vis_func(
                cohort_df,
                params,
                row["start_date"],
                row["end_date"],
                cohort_output_dir,
                generate_output_name   # ✅ pass directly
            )

# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO)

    run_dir, output_dir = initialize_run()

    df = load_data(ED_LAYOUT_FILE)
    driver_df = load_driver(VIS_DRIVER_FILE)

    cohorts = load_cohort_params(COHORT_DIR)

    run_visuals(df, driver_df, cohorts, output_dir)