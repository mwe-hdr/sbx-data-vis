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
        )

    parts = [clean(visual_id)]

    if cohort_id:
        parts.append(clean(cohort_id))

    if start_date and end_date:
        parts.append(f"{clean(start_date)}_to_{clean(end_date)}")

    filename = "__".join(parts) + f".{ext}"

    return filename