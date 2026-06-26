import pandas as pd
import logging

def apply_filter(df, filter_str):
    if df is None or df.empty:
        logging.warning("apply_filter: input dataframe is empty")
        return df

    if not filter_str or pd.isna(filter_str):
        logging.info("apply_filter: no filter provided; returning original dataframe")
        return df

    try:
        before_count = len(df)

        # Minimal normalization (safe + cheap)
        df_copy = df.copy()
        for col in df_copy.select_dtypes(include="object").columns:
            df_copy[col] = df_copy[col].str.strip()

        filtered_df = df_copy.query(filter_str, engine="python")

        after_count = len(filtered_df)

        logging.info(
            f"apply_filter: rows {before_count} → {after_count} | filter: {filter_str}"
        )

        return filtered_df

    except Exception as e:
        logging.error(f"apply_filter failed: {str(e)}")
        return df.iloc[0:0]