import os
import logging
import pandas as pd
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

REPORT_ID = "rpt_01"

def run(
    df,
    params,
    output_dir,
    generate_output_name
):

    cohort_id = params.get(
        "cohort_id"
    )

    summary_df = df[
        df["metric"]
        ==
        "average_census"
    ]

    if summary_df.empty:

        logger.warning(
            f"[{REPORT_ID}] "
            f"No census data"
        )

        return

    mean_census = (
        summary_df["value"]
        .mean()
    )

    peak_census = (
        df[
            df["metric_type"]
            ==
            "peak_census"
        ]["value"]
        .max()
    )

    room_need = (
        df[
            df["metric_type"]
            ==
            "room_need"
        ]["value"]
        .max()
    )

    fig, ax = plt.subplots(
        figsize=(4,2)
    )

    ax.axis("off")

    table = ax.table(

        cellText=[
            [f"{mean_census:,.1f}"],
            [f"{peak_census:,.1f}"],
            [f"{room_need:,.1f}"]
        ],

        rowLabels=[
            "Average Census",
            "Peak Census",
            "Bed Need"
        ],

        loc="center"
    )

    output_file = os.path.join(

        output_dir,

        generate_output_name(
            visual_id=REPORT_ID,
            cohort_id=cohort_id,
            ext="png"
        )

    )

    plt.savefig(
        output_file,
        bbox_inches="tight"
    )

    plt.close()

    logger.info(
        f"[{REPORT_ID}] Saved "
        f"{output_file}"
    )

    return {
        "output_path": output_file
    }