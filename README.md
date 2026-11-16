# Movie API

This project is a FastAPI application for uploading, storing, processing, and retrieving a collection of movies. `POST /upload` reads a CSV, checks that it has exactly the four movie columns (`title`, `release_year`, `rating`, `genre`) and at least one row, and replaces the stored collection. Storage is handled by `src/storage.py` and `src/database.py`, which save the movies to a SQLite database (`data/movies.db`) so the data persists across server restarts, and which run the SQL queries behind `GET /movies` and `GET /movies/search`. `POST /movies/process` loads the stored movies, validates and cleans them with the reusable functions in `data_pipeline` (duplicate removal, missing-value handling, and IQR outlier removal), and saves the cleaned result back to SQLite. `GET /movies` is cached by `src/cache.py`, which stores each response in FakeRedis under a key for its `limit` for 90 seconds, so repeated requests skip the database entirely. Whenever an upload or processing step saves successfully, the whole cache is cleared, so the next request reads fresh data instead of an outdated response. The remaining modules support the API: `src/models.py` defines the Pydantic request and response models, `src/middleware.py` logs each request with an ID and timing, and `src/utils.py` configures logging.

## Running the API

From the repository root, with the virtual environment active:

```bash
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Then open http://127.0.0.1:8000/docs to try the endpoints.

## Running the Tests

```bash
python -m pytest tests -v
```

## Sample Processing Request

After uploading `fixtures/sample_movies.csv`, send this body to `POST /movies/process`:

```json
{
  "validation": {
    "required_columns": ["title", "release_year", "rating", "genre"],
    "numeric_columns": ["release_year", "rating"]
  },
  "processing": {
    "remove_duplicates": true,
    "missing": {"enabled": true, "axis": "rows"},
    "outliers": {
      "enabled": true,
      "columns": ["rating"],
      "method": "iqr",
      "threshold": 1.5
    }
  }
}
```

Expected result:

```json
{
  "validation_rows_removed": 0,
  "cleaning_report": {
    "rows_before": 20,
    "rows_after": 16,
    "rows_removed": 4,
    "columns_before": 4,
    "columns_after": 4,
    "columns_removed": 0
  }
}
```

The 4 removed rows are the duplicate entries for Movie B and Movie D and the low-rating outliers Movie Q and Movie R. A following `GET /movies?limit=100` returns `total_rows: 16`, with Movie A through Movie P.
