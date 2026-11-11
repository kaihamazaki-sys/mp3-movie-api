import logging
import pandas as pd


logger = logging.getLogger(__name__)


def validate_dataframe(df, required_columns, numeric_columns):
    """Validate the DataFrame and return valid data.

    required_columns: a list of column names that must exist.
    numeric_columns: a list of column names whose values should be numeric.
    """
    for col in required_columns:
        if col not in df.columns:
            logger.error(f"Required column missing: {col}")
            raise ValueError(f"Required column missing: {col}")

    rows_before = len(df)
    df = df.copy()

    for col in numeric_columns:
        invalid_rows = []
        for i, value in df[col].items():
            if pd.notna(value):
                try:
                    float(value)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid value in {col}: {value}")
                    invalid_rows.append(i)

        df = df.drop(index=invalid_rows)

        # convert to a numeric data type
        df[col] = pd.to_numeric(df[col])

    logger.debug(f"Validation: {rows_before} → {len(df)} rows")
    return df
