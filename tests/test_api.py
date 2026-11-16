def test_upload_csv(client, sample_csv_bytes):
    response = client.post(
        "/upload",
        files={"file": ("sample_data.csv", sample_csv_bytes, "text/csv")}
    )
    assert response.status_code == 200

    body = response.json()
    assert body["rows"] == 6
    assert body["columns"] == 2
    assert isinstance(body["id"], int)
    assert body["id"] > 0

def test_process_and_retrieve(
    client, uploaded_dataset_id, processing_body
):
    response = client.post(
        f"/datasets/{uploaded_dataset_id}/process",
        json=processing_body
    )
    assert response.status_code == 200

    body = response.json()
    assert body["validation_rows_removed"] == 1
    assert body["cleaning_report"]["rows_before"] == 5
    assert body["cleaning_report"]["rows_after"] == 3

    response = client.get(f"/datasets/{uploaded_dataset_id}")
    assert response.status_code == 200

    body = response.json()
    assert body["total_rows"] == 3
    student_ids = [record["student_id"] for record in body["data"]]
    scores = [record["score"] for record in body["data"]]
    assert student_ids == [1, 2, 5]
    assert scores == [80, 90, 85]

def test_retrieve_missing_dataset(client):
    response = client.get("/datasets/999")
    assert response.status_code == 404



import pytest

from src import MovieStorage
import main

def test_movies_persist(client, test_storage, uploaded_movies):
    # TODO: create another MovieStorage pointing to test_storage.db_path.
    # Use that object to get the movies and count them.
    # Check 20 rows, all four DataFrame columns, and the original title order.
    # Compare IDs from that object's select_columns() with GET /movies?limit=100.
    # Both should return IDs 1 through 20 in row order.
    reopened = MovieStorage(test_storage.db_path)

    df = reopened.get()
    assert reopened.count_movies() == 20
    assert len(df) == 20
    assert list(df.columns) == MOVIE_COLUMNS

    expected_titles = pd.read_csv("fixtures/sample_movies.csv")["title"].tolist()
    assert df["title"].tolist() == expected_titles

    db_ids = [row["id"] for row in reopened.select_columns(MOVIE_COLUMNS, 100)]

    response = client.get("/movies", params={"limit": 100})
    assert response.status_code == 200
    api_ids = [record["id"] for record in response.json()["data"]]

    assert db_ids == list(range(1, 21))
    assert api_ids == db_ids


def test_cache_and_processing(client, uploaded_movies, processing_body):
    # TODO 1: GET /movies with limits 100 and 1.
    # Check 200 and that main.cache.get(limit) equals each response body.
    response_100 = client.get("/movies", params={"limit": 100})
    response_1 = client.get("/movies", params={"limit": 1})
    assert response_100.status_code == 200
    assert response_1.status_code == 200
    assert main.cache.get(100) == response_100.json()
    assert main.cache.get(1) == response_1.json()

    # TODO 2: repeat limit=100 and check the same response.
    repeat = client.get("/movies", params={"limit": 100})
    assert repeat.status_code == 200
    assert repeat.json() == response_100.json()

    # TODO 3: POST /movies/process using json=processing_body.
    # Check 200, zero validation removals, and the 20 -> 16 cleaning report.
    # Confirm both old cache entries are None.
    response = client.post("/movies/process", json=processing_body)
    assert response.status_code == 200
    body = response.json()
    assert body["validation_rows_removed"] == 0
    assert body["cleaning_report"]["rows_before"] == 20
    assert body["cleaning_report"]["rows_after"] == 16
    assert body["cleaning_report"]["rows_removed"] == 4
    assert main.cache.get(100) is None
    assert main.cache.get(1) is None


    # TODO 4: retrieve again; check total_rows=16 and titles Movie A through Movie P, in order.
    # Check IDs 1 through 16 in the retrieved records.
    # Check that the new response is cached.
    response = client.get("/movies", params={"limit": 100})
    assert response.status_code == 200
    body = response.json()
    assert body["total_rows"] == 16

    titles = [record["title"] for record in body["data"]]
    assert titles == [f"Movie {letter}" for letter in "ABCDEFGHIJKLMNOP"]

    ids = [record["id"] for record in body["data"]]
    assert ids == list(range(1, 17))

    assert main.cache.get(100) == body


def test_cache_hit_skips_database(client, uploaded_movies, monkeypatch):
    # TODO 1: GET /movies with limit=100 to populate the cache.
    # Assert 200 and keep the response for comparison.
    first = client.get("/movies", params={"limit": 100})
    assert first.status_code == 200
    first_body = first.json()


    # TODO 2: Use monkeypatch to replace main.storage.select_columns()
    # and main.storage.count_movies() with a function that fails the test
    # if either method is called. 
    def fail_if_called(*args, **kwargs):
        pytest.fail("Database was queried on a cache hit")

    monkeypatch.setattr(main.storage, "select_columns", fail_if_called)
    monkeypatch.setattr(main.storage, "count_movies", fail_if_called)

    # TODO 3: Repeat the same GET request.
    # Assert 200 and the same response body as the first request.
    second = client.get("/movies", params={"limit": 100})
    assert second.status_code == 200
    assert second.json() == first_body