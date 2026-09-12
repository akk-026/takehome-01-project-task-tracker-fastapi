# Plan

I split the work into focused, incremental feature commits so each requirement can be reviewed and
tested independently.

1. Set up FastAPI, SQLAlchemy, SQLite, seeded users, and bearer-session authentication.
2. Add server-enforced manager/member authorization and project membership.
3. Build projects, task fields, dependencies, and manager-only deletion.
4. Add lifecycle validation before exposing lifecycle controls in the interface.
5. Add many-to-many task assignments and each person's cross-project assigned list.
6. Build the server-side task finder with search, filters, sorting, pagination, visibility rules, and
   a total count.
7. Add bulk actions with isolated per-task outcomes and a server-side CSV export of the current finder
   filters. Refactor the frontend from compact single-line templates into named rendering and event
   functions so follow-on work is easier to change safely.
8. Add the authenticated dashboard summary, persist completion timestamps through lifecycle changes,
   and cover manager/member visibility plus calendar-week reporting with automated tests.
9. Add an append-only timeline, record task mutation and membership-driven unassignment events in the
   server transaction, and add comments without any edit or delete capability.
10. Add personal overdue alerts, a navigation count badge, dismissal controls, and deadline-change
    restoration backed by a per-user dismissal table.
11. Add the optional project board with native drag-and-drop, reusing the server's legal transition
    data and single-task status endpoint rather than creating a second lifecycle path.
12. Prepare a Vercel deployment entrypoint and route all browser requests through the existing
    FastAPI application. Keep SQLite for local use while adding a hosted Postgres configuration for
    deployment.

All ten required features, the optional board, and a Vercel-ready deployment configuration are
implemented in focused, independently testable commits.
