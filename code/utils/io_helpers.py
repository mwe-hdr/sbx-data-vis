import os
import pandas as pd
import logging

def load_data(file_path):
    logging.info("Loading ED data")
    df = pd.read_csv(file_path, low_memory=False)

    # defensive datetime parsing
    if "visit_dtm" in df.columns:
        df["visit_dtm"] = pd.to_datetime(df["visit_dtm"], errors="coerce")

    return df


def load_driver(file_path):
    logging.info("Loading visual driver")
    return pd.read_csv(file_path)


def load_params(param_dir, visual_id):

    param_file = os.path.join(param_dir, f"{visual_id}.csv")

    if not os.path.exists(param_file):
        logging.warning(f"No params found for {visual_id}")
        return {}

    try:
        df = pd.read_csv(param_file)
        return dict(zip(df["param"], df["value"]))
    except Exception as e:
        logging.error(f"Failed to load params for {visual_id}: {str(e)}")
        return {}