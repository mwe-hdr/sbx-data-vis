import logging
import pandas as pd
from utils.col_helpers import (
    prepare_common_columns
)

logger = logging.getLogger(__name__)

def load_mapping_file(mapping_file):

    df = pd.read_csv(
    mapping_file,
    dtype={
        "source_value": str,
        "target_value": str
        }
    )

    mappings = {}

    for domain in df["domain"].dropna().unique():

        domain_df = df[
            df["domain"].astype(str).str.lower()
            == str(domain).lower()
        ]

        field_mappings = {}

        value_mappings = []

        active_df = domain_df[
            domain_df["active_flag"]
            .astype(str)
            .str.upper()
            .isin(["Y", "YES", "TRUE", "1"])
        ]

        field_rows = active_df[
            active_df["mapping_type"]
            .astype(str)
            .str.lower()
            == "field"
        ]

        logger.info(
            f"[mapping] Loaded {len(field_rows)} field rows "
            f"for domain={domain}"
        )

        value_rows = active_df[
            active_df["mapping_type"]
            .astype(str)
            .str.lower()
            == "value"
        ]

        logger.info(
            f"[mapping] Loaded {len(value_rows)} value rows "
            f"for domain={domain}"
        )

        for _, row in field_rows.iterrows():     

            field_mappings[
                row["source_field"]
            ] = {
                "target_field": row["target_field"],
                "source_format": row["source_format"],
                "target_format": row["target_format"]
            }

            logger.info(
                f"[mapping] Registered field mapping "
                f"{row['source_field']} -> "
                f"{row['target_field']} "
                f"({row['source_format']} -> "
                f"{row['target_format']})"
            )

        grouped = value_rows.groupby(
            [
                "source_field",
                "target_field",
                "source_format",
                "target_format"
            ]
        )

        for (
            source_field,
            target_field,
            source_format,
            target_format
        ), group in grouped:

            mapping_dict = {}

            for _, row in group.iterrows():

                mapping_key = str(
                    row["source_value"]
                ).strip()

                mapping_dict[mapping_key] = row["target_value"]           

            value_mappings.append(
                {
                    "domain": str(domain).lower(),
                    "source_field": source_field,
                    "target_field": target_field,
                    "source_format": source_format,
                    "target_format": target_format,
                    "mapping": mapping_dict,
                    "mapping_type": "value"
                }
            )

        mappings[str(domain).lower()] = {
            "field_mappings": field_mappings,
            "value_mappings": value_mappings
        }

    return mappings

def normalize_field_format(
    series,
    format_type
):

    format_type = str(format_type).lower()

    if format_type == "str":

        return (
            series
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
        )

    if format_type == "int":

        return (
            pd.to_numeric(
                series,
                errors="coerce"
            )
            .astype("Int64")
            .astype(str)
            .replace("<NA>", "")
        )

    if format_type == "zip5":

        return (
            series
            .fillna("")
            .astype(str)
            .str.extract(r"(\d+)", expand=False)
            .fillna("")
            .str[:5]
            .str.zfill(5)
        )

    return (
        series
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

def apply_target_format(series, format_type):

    format_type = str(format_type).lower()

    if format_type == "str":
        return (
            series
            .fillna("")
            .astype(str)
        )

    if format_type == "int":
        return pd.to_numeric(
            series,
            errors="coerce"
        )

    if format_type == "datetime":

        return pd.to_datetime(
            series,
            errors="coerce"
        )

    if format_type == "zip5":
        return (
            series
            .fillna("")
            .astype(str)
            .str.extract(r"(\d+)", expand=False)
            .fillna("")
            .str.zfill(5)
            .str[:5]
        )

    return series

def apply_field_mappings(df, field_mappings):

    for source_field, config in field_mappings.items():

        if source_field not in df.columns:
            logger.warning(
                f"[mapping] Missing source field: {source_field}"
            )
            continue

        target_field = config["target_field"]

        normalized_source = normalize_field_format(
            df[source_field],
            config.get("source_format", "str")
        )

        transformed_target = apply_target_format(
            normalized_source,
            config.get("target_format", "str")
        )

        df[target_field] = transformed_target

    return df

def apply_value_mappings(
    df,
    value_mappings
):

    for config in value_mappings:

        source_field = config["source_field"]
        target_field = config["target_field"]
        mapping = config["mapping"]

        if source_field not in df.columns:

            logger.warning(
                f"[mapping] Missing source field: "
                f"{source_field}"
            )

            continue

        source_values = normalize_field_format(
            df[source_field],
            config.get("source_format", "str")
        )

        logger.info(
            f"[mapping] source_field={source_field} "
        )

        raw_mapped_values = source_values.map(mapping)

        logger.info(
            f"[mapping] mapping keys={list(mapping.keys())}"
        )

        logger.info(
            f"[mapping] top 20 unique source values="
            f"{sorted(source_values.dropna().unique().tolist())[:20]}"
        )

        logger.info(
            f"[mapping] Mapping audit "
            f"source_field={source_field} "
            f"target_field={target_field}"
        )

        for source_value, target_value in mapping.items():

            mapped_record_count = (
                source_values == source_value
            ).sum()

            if mapped_record_count > 0:

                logger.info(
                    f"[mapping] "
                    f"{source_value!r} -> "
                    f"{target_value!r} "
                    f"records={mapped_record_count:,}"
                )

        unmapped_counts = (
            source_values[
                raw_mapped_values.isna()
                & source_values.notna()
                & (source_values.astype(str) != "")
            ]
            .value_counts()
        )

        if not unmapped_counts.empty:

            logger.warning(
                f"[mapping] Unmapped values "
                f"source_field={source_field} "
                f"target_field={target_field}"
            )

            for value, count in unmapped_counts.items():

                logger.warning(
                    f"[mapping] "
                    f"value={value!r} "
                    f"records={count:,}"
                )

        mapped_values = apply_target_format(
            raw_mapped_values,
            config.get("target_format", "str")
        )

        df[target_field] = mapped_values

    return df

def apply_standard_mappings(
    df,
    domain_mapping
):

    field_mappings = domain_mapping.get(
        "field_mappings",
        {}
    )

    value_mappings = domain_mapping.get(
        "value_mappings",
        []
    )

    logger.info(
        f"[mapping] Field mappings loaded: "
        f"{len(field_mappings)}"
    )

    logger.info(
        f"[mapping] Value mappings loaded: "
        f"{len(value_mappings)}"
    )

    df = apply_field_mappings(
        df,
        field_mappings
    )

    df = apply_value_mappings(
        df,
        value_mappings
    )

    required_fields = [
        "patient_zipcode"
    ]

    missing_fields = [
        col
        for col in required_fields
        if col not in df.columns
    ]

    if missing_fields:

        logger.warning(
            "[mapping] Missing required "
            f"standardized fields: "
            f"{missing_fields}"
        )

    df = prepare_common_columns(df)

    return df