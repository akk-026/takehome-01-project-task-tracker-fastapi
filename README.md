# Northstar Project Tracker · FastAPI rebuild

A clean rebuild of the project-tracking assignment. The backend uses FastAPI and SQLAlchemy with a
SQLite database for local development; the frontend remains dependency-free JavaScript. Feature 1
includes server-enforced manager/member permissions: only managers can create or archive projects,
replace a project's membership, or delete a task. Members only receive projects they belong to.

## Run locally

```sh
cd backend
../.venv/bin/uvicorn app.main:app --reload
```

Open the app at [http://localhost:8000](http://localhost:8000). The API health check is available at
[http://localhost:8000/api/health](http://localhost:8000/api/health). If you serve `frontend/` with
another local server on port 3000, it will use the FastAPI API on port 8000 automatically.

## Test

```sh
cd backend
../.venv/bin/python -m unittest discover -s tests
```

## Demo accounts

| Role | Email | Password |
| --- | --- | --- |
| Manager | `alice@northstar.test` | `manager123` |
| Member | `dan@northstar.test` | `member123` |
| Member | `priya@northstar.test` | `member123` |
