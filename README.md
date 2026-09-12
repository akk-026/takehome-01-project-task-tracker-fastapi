# Northstar Project Tracker · FastAPI rebuild

A clean rebuild of the project-tracking assignment. The backend uses FastAPI and SQLAlchemy with a
SQLite database for local development; the frontend remains dependency-free JavaScript.

## Run locally

```sh
cd backend
../.venv/bin/uvicorn app.main:app --reload
```

Open the API health check at [http://localhost:8000/api/health](http://localhost:8000/api/health).
The frontend is being built feature by feature in `frontend/`.

## Test

```sh
cd backend
../.venv/bin/python -m unittest discover -s tests
```
