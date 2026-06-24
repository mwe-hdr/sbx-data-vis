import os
import logging
from datetime import datetime

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


def generate_output_name(visual_id, start_date, end_date, ext="png"):

    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    return f"{visual_id}_{start_str}_{end_str}.{ext}"