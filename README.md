# Northstar Project Tracker · FastAPI rebuild

A clean rebuild of the project-tracking assignment. The backend uses FastAPI and SQLAlchemy with a
SQLite database for local development; the frontend remains dependency-free JavaScript. Feature 1
includes server-enforced manager/member permissions: only managers can create or archive projects,
replace a project's membership, or delete a task. Members only receive projects they belong to.
Managers can also edit project details and restore archived projects; archived projects are omitted
from the default project list without deleting their records.
Tasks live inside one project and include descriptions, priorities, optional due dates, and
same-project blockers. Project members can create and edit tasks; only managers can delete them.
Tasks begin in Backlog and advance through In Progress, In Review, and Done. They may be blocked
from either active state and return to that state when unblocked; reopening a completed task returns
it to In Progress. The API supplies each task's currently legal next moves, while independently
rejecting invalid transitions and completion with unfinished blockers.
Tasks also support multiple assignees, limited to the task's project members. Each person's home
view includes all of their assigned tasks across projects; removing a member from a project clears
their assignments in that project.
The task finder performs all cross-project search, filtering, sorting and pagination in FastAPI.
It supports title/description search plus project, status, assignee, priority and overdue filters,
and returns the total matching count with every page.
Selected finder tasks can receive one bulk status, assignee-replacement, or due-date change. The
server applies the normal rules independently to each task and returns a success or rejection reason
for every selected item; valid changes are not rolled back because another item was invalid. The
currently filtered finder results can also be exported as a server-generated CSV file.

The landing dashboard is an authenticated, visibility-scoped server summary. It shows open,
overdue, due-this-week, and completed-this-week totals; task counts by status and assignee; and an
eight-week completion chart. Tasks store their completion timestamp when they move to Done, so later
edits do not alter completion reporting.

Every task includes an append-only timeline for creation, field and status changes, assignments,
unassignments, and comments. Each event records the actor and before/after values where relevant.
Comments are timeline entries and cannot be edited or deleted, including by managers.

The header alert badge shows each person's currently overdue assigned tasks. An alert can be
dismissed by its assignee; changing that task's due date restores the alert for every assignee.

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
