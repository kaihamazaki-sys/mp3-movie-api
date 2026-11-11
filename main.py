import io
import logging
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from data_pipeline import create_cleaning_report, process_data, validate_dataframe
from src import (
    HealthResponse,
    ProcessConfig,
    setup_logging,
    log_requests,
    MovieStorage,
    MovieUploadInfo,
    MovieDataResponse,
    MovieProcessingReport,
)
from src.storage import MOVIE_COLUMNS

setup_logging(verbose=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Movie API", version="1.0.0")
app.middleware("http")(log_requests)
storage = MovieStorage()


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return the application status and version."""
    return HealthResponse(status="ok", version=app.version)


@app.post("/upload", response_model=MovieUploadInfo)
async def upload_movies(file: UploadFile = File(...)):
    """Read a movie CSV and replace the stored collection."""
    # TODO 1: extension check, read, parse
    suffix = Path(file.filename or "").suffix.lower()
    if suffix != ".csv":
        logger.warning(f"Unsupported file format: {suffix}")
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {suffix or 'none'}. Please upload a .csv file.",
        )

    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as e:
        logger.warning(f"Could not parse CSV {file.filename}: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Could not read {file.filename} as a CSV file: {e}",
        )

    # TODO 2: quick validation before saving
    if sorted(df.columns) != sorted(MOVIE_COLUMNS):
        logger.warning(f"Invalid movie columns: {list(df.columns)}")
        raise HTTPException(
            status_code=400,
            detail=f"CSV must have exactly these columns: {', '.join(MOVIE_COLUMNS)}",
        )

    if df.empty:
        logger.warning(f"Uploaded CSV has no data rows: {file.filename}")
        raise HTTPException(status_code=400, detail="CSV must contain at least one data row")

    df = df[MOVIE_COLUMNS]

    # TODO 3: save, log, return
    storage.save(df)
    logger.info(f"Uploaded movies: filename={file.filename}, rows={len(df)}")
    return {
        "filename": file.filename,
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
    }


@app.get("/movies", response_model=MovieDataResponse)
def get_movies(limit: int = Query(default=100, ge=1)):
    """Return up to limit stored movies and the total count."""
    data = storage.select_columns(MOVIE_COLUMNS, limit)
    total_rows = storage.count_movies()
    logger.info(f"Retrieved movies: returned_rows={len(data)}, total_rows={total_rows}")
    return {"data": data, "total_rows": total_rows}


@app.get("/movies/search", response_model=list[dict])
def query_movies(
    columns: list[str] = Query(default=["title"]),
    min_rating: float = Query(default=0, ge=0, le=10),
    limit: int = Query(default=100, ge=1),
):
    """Return selected fields from movies with rating >= min_rating."""
    try:
        results = storage.query_movies(columns, min_rating, limit)
    except ValueError as error:
        logger.warning(f"Invalid search: {error}")
        raise HTTPException(status_code=400, detail=str(error))

    logger.info(
        f"Queried movies: columns={columns}, min_rating={min_rating}, "
        f"returned_rows={len(results)}"
    )
    return results


@app.post("/movies/process", response_model=MovieProcessingReport)
def process_movies(config: ProcessConfig):
    """Validate and process the stored movies using MP1 functions."""
    # TODO 1: retrieve
    df = storage.get()
    if df.empty:
        logger.warning("No movies stored to process")
        raise HTTPException(status_code=400, detail="No movies stored. Upload a CSV first.")

    # TODO 2: reuse MP2 logic
    config_dict = config.model_dump()
    required_columns = config_dict["validation"]["required_columns"]
    numeric_columns = config_dict["validation"]["numeric_columns"]

    missing_numeric = [col for col in numeric_columns if col not in df.columns]
    if missing_numeric:
        logger.warning(f"Numeric columns not found: {missing_numeric}")
        raise HTTPException(
            status_code=400,
            detail=f"Numeric columns not found: {', '.join(missing_numeric)}",
        )

    try:
        validated = validate_dataframe(df, required_columns, numeric_columns)
        validation_rows_removed = len(df) - len(validated)
        logger.info(f"Validated movies: rows={len(df)} → {len(validated)}")

        df_before = validated.copy()
        processed = process_data(validated, config_dict)
    except ValueError as error:
        logger.warning(f"Processing failed: error={error}")
        raise HTTPException(status_code=400, detail=str(error))

    cleaning_report = create_cleaning_report(df_before, processed)

    # TODO 3: save and return
    storage.save(processed.reindex(columns=MOVIE_COLUMNS))
    logger.info(
        f"Processed movies: validation_removed={validation_rows_removed}, "
        f"rows_before={cleaning_report['rows_before']}, "
        f"rows_after={cleaning_report['rows_after']}"
    )

    return {
        "validation_rows_removed": validation_rows_removed,
        "cleaning_report": cleaning_report,
    }
