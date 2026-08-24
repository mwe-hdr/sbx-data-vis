import pandas as pd
from pathlib import Path

# Input file
input_file = r"C:\lwf\sbx-data-vis\data\input\ecu_cloc_vis_dtl.csv"

# Read CSV
df = pd.read_csv(input_file)

# Calculate total visits, sumproduct, and weighted average duration by CLOC
result_df = (
    df.groupby("cloc")
      .apply(
          lambda x: pd.Series({
              "total_visits": x["visits"].sum(),
              "sumproduct_duration":
                  (x["visits"] * x["average_appt_duration_in_minutes"]).sum(),
              "weighted_avg_duration_minutes":
                  (x["visits"] * x["average_appt_duration_in_minutes"]).sum()
                  / x["visits"].sum()
          })
      )
      .reset_index()
)

# Round for reporting
result_df["sumproduct_duration"] = result_df["sumproduct_duration"].round(2)
result_df["weighted_avg_duration_minutes"] = (
    result_df["weighted_avg_duration_minutes"].round(2)
)

# Output file in same folder as input
input_path = Path(input_file)
output_file = input_path.parent / "ecu_cloc_weighted_avg_duration_by_cloc.csv"

# Save results
result_df.to_csv(output_file, index=False)

print(f"Output written to: {output_file}")