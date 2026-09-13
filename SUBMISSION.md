# Submission

## Links

- **GitHub repository:** https://github.com/akk-026/takehome-01-project-task-tracker-fastapi
- **Live application:** https://takehome-01-project-task-tracker-fa.vercel.app

## Demo credentials

| Role | Email | Password |
| --- | --- | --- |
| Manager | `alice@northstar.test` | `manager123` |
| Member | `dan@northstar.test` | `member123` |
| Member | `priya@northstar.test` | `member123` |

## Notes for the reviewer

The deployed application uses Supabase Postgres and seeds the demo accounts on first start. It is
safe to create and edit demo projects and tasks. The Supabase Free tier may pause after inactivity,
so the first request after a long idle period can take a little longer than normal.

## Stack

| Layer | Technology | Why |
| --- | --- | --- |
| Frontend | Vanilla HTML, CSS and JavaScript | Small, inspectable UI with no build step. |
| API | FastAPI | Typed routes and explicit server-side policy checks. |
| Data access | SQLAlchemy | One relational model for local SQLite and hosted Postgres. |
| Production database | Supabase Postgres | Persistent free-tier database for the Vercel function. |
| Hosting | Vercel | Serves the FastAPI application and same-origin browser client from one URL. |

## Goal checklist

| # | Goal | Status | Notes |
| --- | --- | --- | --- |
| 1 | Accounts and roles | Done | Password sign-in and server-enforced manager/member permissions. |
| 2 | Projects | Done | Create, edit, archive and restore with owner and membership. |
| 3 | Tasks inside projects | Done | Full task fields, same-project blockers and project task views. |
| 4 | Task lifecycle | Done | Server-only transition validation, blocked return state and blocker checks. |
| 5 | Assignment | Done | Multi-assignee tasks, project-member validation and automatic unassignment. |
| 6 | Finding things | Done | Server-side search, filters, sorting, pagination and match totals. |
| 7 | Bulk actions and export | Done | Per-task result reporting plus filtered CSV export. |
| 8 | Dashboard | Done | Required headline metrics, breakdowns and eight-week completion chart. |
| 9 | Immutable history | Done | Append-only events, comments and retained audit history after soft deletion. |
| 10 | Overdue alerts | Done | Assigned-user alerts, navigation badge, personal dismissal and due-date reappearance. |
| Stretch | Project board | Done | Native drag-and-drop board reusing server lifecycle validation. |

## Time spent

About 14 hours across the planned functional work, test coverage, documentation, deployment
configuration, and production verification.

## What I would do with another 12 hours

Add database migrations and production indexes, introduce a real authentication provider with
password reset, add browser-level integration coverage, detect dependency cycles, and improve the
board’s keyboard interaction.

## What I am least happy with

The app intentionally favours a small, dependency-free take-home implementation. For production I
would replace ad-hoc demo sessions with managed identity, add migrations rather than startup schema
creation, and add a background delivery mechanism for notifications.
