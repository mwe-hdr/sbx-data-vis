import os
import logging
import pandas as pd
import importlib

from utils.io_helpers import load_data, load_driver, load_params
from utils.run_helpers import initialize_run, generate_output_name

# =========================
# CONFIG
# =========================
BASE_DIR = os.getcwd()
INPUT_DIR = os.path.join(BASE_DIR, "data", "input")
PARAM_DIR = os.path.join(INPUT_DIR, "params")

ED_LAYOUT_FILE = os.path.join(INPUT_DIR, "rmc_emergency_export.csv")
VIS_DRIVER_FILE = os.path.join(INPUT_DIR, "vis_driver.csv")

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
def run_visuals(df, driver_df, output_dir):

    for _, row in driver_df.iterrows():

        if row["enabled"] != 1:
            continue

        visual_id = row["visual_id"]

        try:
            start_date = pd.to_datetime(row["start_date"])
            end_date = pd.to_datetime(row["end_date"])
        except Exception:
            logging.error(f"{visual_id}: Invalid date format")
            continue

        logging.info(f"Starting {visual_id}")

        func = get_visual_function(visual_id)
        if func is None:
            continue

        params = load_params(PARAM_DIR, visual_id)

        try:
            func(df, params, start_date, end_date, output_dir, generate_output_name)
            logging.info(f"Completed {visual_id}")
        except Exception as e:
            logging.error(f"{visual_id} failed: {str(e)}")

# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":

    run_dir, output_dir = initialize_run()

    df = load_data(ED_LAYOUT_FILE)
    driver_df = load_driver(VIS_DRIVER_FILE)

    logging.info("Starting visual execution")

    run_visuals(df, driver_df, output_dir)

    logging.info("Run complete")

    print(f"Run complete. Outputs located at:\n{run_dir}")