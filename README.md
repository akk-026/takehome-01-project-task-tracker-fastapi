# Northstar Project Tracker

Northstar is an internal project and task tracker for teams managing client work across several
projects. It is built with FastAPI, SQLAlchemy, and SQLite, with a dependency-free JavaScript
frontend served by the API.

## What is implemented

- **Accounts and roles:** Managers and members sign in with separate, server-enforced permissions.
  Members only see projects they belong to; managers can manage projects, membership, and task
  deletion.
- **Projects and tasks:** Projects have a key, owner, membership, archive/restore support, and a
  task list. Tasks support descriptions, priorities, optional due dates, blockers, and multiple
  assignees.
- **Task lifecycle:** Tasks move through Backlog, In Progress, In Review, Done, and Blocked.
  FastAPI validates every move, including blocking completion when unfinished dependencies remain.
- **Task discovery and bulk actions:** The server provides visibility-scoped search, filters,
  sorting, pagination, CSV export, and per-task results for bulk status, assignee, and due-date
  updates.
- **Dashboard and alerts:** The home view shows workload metrics, task breakdowns, an eight-week
  completion chart, and overdue alerts that assignees can dismiss. Revising a due date restores a
  dismissed alert.
- **Immutable history:** Each task has an append-only timeline of creation, edits, status changes,
  assignment changes, and comments.
- **Project board:** The optional drag-and-drop board organizes tasks by lifecycle state. It only
  highlights valid next states, and every drop is sent through the same server-side lifecycle
  validation as the regular task controls.

## Run locally

From the repository root:

```sh
cd backend
../.venv/bin/uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000). The health check is available at
[http://localhost:8000/api/health](http://localhost:8000/api/health).

On first start, SQLite creates the schema and the demo accounts below. Projects and tasks can then
be created in the application; the database file is local-only and ignored by Git.

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
