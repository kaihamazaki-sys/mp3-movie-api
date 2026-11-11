import logging
import pandas as pd

logger = logging.getLogger(__name__)


def remove_duplicates(df):
    """Remove duplicate rows."""
    result = df.drop_duplicates()
    logger.debug(f"remove_duplicates: {len(df)} → {len(result)} rows")
    return result


def handle_missing(df, axis="rows"):
    """Drop rows or columns containing missing values."""
    if axis == "rows":
        result = df.dropna(axis=0)
        logger.debug(f"handle_missing: {len(df)} → {len(result)} rows")
    elif axis == "columns":
        result = df.dropna(axis=1)
        logger.debug(
            f"handle_missing: {len(df.columns)} → {len(result.columns)} columns"
        )
    else:
        logger.error(f"Unsupported axis: {axis}")
        raise ValueError(f"Unsupported axis: {axis}")
    return result


def remove_outliers(df, columns, method, threshold):
    """Remove outliers from the specified numeric columns."""
    if method not in ("iqr", "zscore"):
        logger.error(f"Unsupported outlier method: {method}")
        raise ValueError(f"Unsupported outlier method: {method}")

    result = df
    for col in columns:
        if col not in result.columns:
            logger.warning(f"Column not found: {col}")
            continue
        if not pd.api.types.is_numeric_dtype(result[col]):
            logger.warning(f"Column is not numeric: {col}")
            continue

        values = result[col]
        if method == "iqr":
            q1 = values.quantile(0.25)
            q3 = values.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - threshold * iqr
            upper = q3 + threshold * iqr
            keep = values.between(lower, upper)
        else:
            std = values.std()
            if pd.isna(std) or std == 0:
                keep = pd.Series(True, index=values.index)
            else:
                keep = ((values - values.mean()) / std).abs() <= threshold

        # Missing values are not outliers; handle_missing deals with them.
        keep = keep | values.isna()
        before = len(result)
        result = result[keep]
        logger.debug(
            f"{col}: method={method}, threshold={threshold}, "
            f"removed={before - len(result)}"
        )

    return result


def process_data(df, config):
    """Apply the processing steps enabled in the configuration."""
    processing = config["processing"]

    if processing.get("remove_duplicates", False):
        df = remove_duplicates(df)

    missing = processing.get("missing", {})
    if missing.get("enabled", False):
        df = handle_missing(df, axis=missing.get("axis", "rows"))

    outliers = processing.get("outliers", {})
    if outliers.get("enabled", False):
        df = remove_outliers(
            df,
            columns=outliers.get("columns", []),
            method=outliers.get("method", "iqr"),
            threshold=outliers.get("threshold", 1.5),
        )

    return df


def create_cleaning_report(df_before, df_after):
    """Return a dictionary summarizing the cleaning results."""
    rows_before = len(df_before)
    rows_after = len(df_after)
    columns_before = len(df_before.columns)
    columns_after = len(df_after.columns)
    return {
        "rows_before": rows_before,
        "rows_after": rows_after,
        "rows_removed": rows_before - rows_after,
        "columns_before": columns_before,
        "columns_after": columns_after,
        "columns_removed": columns_before - columns_after,
    }
