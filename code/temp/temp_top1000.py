import pandas as pd
from pathlib import Path

# ============================================================
# Input Files
# ============================================================

INPUT_FILES = [
    r"C:\lwf\sbx-data-vis\data\input\lc_adf_class_pod_history_flat_enriched.csv"
]

# ============================================================
# Create Top-1000 Files
# ============================================================

for input_file in INPUT_FILES:

    df = pd.read_csv(input_file)

    df_top1000 = df.head(1000)

    input_path = Path(input_file)

    output_file = (
        input_path.parent /
        f"{input_path.stem}_top1000.csv"
    )

    df_top1000.to_csv(
        output_file,
        index=False
    )

    print(
        f"Created: {output_file} "
        f"({len(df_top1000):,} rows)"
    )

print("Complete.")