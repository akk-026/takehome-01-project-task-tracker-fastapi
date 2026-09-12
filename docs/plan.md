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

The next sessions will cover immutable history/comments and overdue alerts. I have not estimated
those as complete work; they remain intentionally out of scope rather than being shown as partially
finished features.
