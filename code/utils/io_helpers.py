import os
import pandas as pd
import logging

def load_data(file_path):
    logging.info("Loading data")
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
        return pd.DataFrame()

    try:
        return pd.read_csv(param_file)

    except Exception as e:
        logging.error(
            f"Failed to load params for {visual_id}: {str(e)}"
        )
        return pd.DataFrame()
    
def load_cohort_params(cohort_root_dir):
    """
    Recursively load all cohort CSVs.
    Supports existing structure:
        cohorts/<domain>/<file>.csv

    Each row = subcohort
    """

    cohorts = {}

    for root, _, files in os.walk(cohort_root_dir):
        for file in files:
            if not file.endswith(".csv"):
                continue

            file_path = os.path.join(root, file)

            try:
                df = pd.read_csv(file_path)
            except Exception as e:
                logging.error(f"Failed to read {file_path}: {e}")
                continue

            required_cols = {"name", "param", "value"}
            if not required_cols.issubset(df.columns):
                logging.warning(f"Skipping {file_path} (invalid columns)")
                continue

            # derive namespace from folder + filename
            relative_path = os.path.relpath(file_path, cohort_root_dir)
            parts = relative_path.replace(".csv", "").split(os.sep)

            # e.g. emergency/beaufort → emergency.beaufort
            cohort_group = ".".join(parts)

            for _, row in df.iterrows():

                sub_name = str(row["name"]).strip()
                cohort_id = f"{cohort_group}.{sub_name}"

                param = row["param"]
                value = row["value"]
                desc = row.get("description")
                domain = row.get("domain")
                cohort_file = row.get("cohort_file") if "cohort_file" in df.columns else None

                if pd.isna(domain) or str(domain).strip() == "":
                    domain = parts[0] if parts else None

                cohorts[cohort_id] = {
                    "group": cohort_group,
                    "name": sub_name,
                    "filter": value if param == "filter" else None,
                    "description": str(desc).strip() if pd.notna(desc) else None,
                    "domain": str(domain).strip() if pd.notna(domain) else None,
                    "cohort_file": str(cohort_file).strip() if pd.notna(cohort_file) else None
                }

                logging.info(f"[loader] FINAL cohort_id: {cohort_id}")
                logging.info(f"[loader] DATA: {cohorts[cohort_id]}")

    logging.info(f"Loaded {len(cohorts)} cohorts")
    return cohorts