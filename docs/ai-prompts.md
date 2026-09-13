# AI prompts

I used AI as a pair-programming and review tool while building the application. These are the
substantive prompts in the order I used them; I have kept the wording close to the original working
questions rather than rewriting them as a project specification. I read the changes, adjusted the
approach where needed, and verified the resulting behaviour with the test suite and the browser.

## Foundation and data model

1. “I want a small FastAPI task tracker with a plain JavaScript frontend. What tables do I need for
   projects, users, project membership, tasks, assignees and blockers?”
   - I used the suggested relational shape: `projects` owns its work, `users` identifies people,
     and membership, assignment, and blocker tables model the many-to-many relationships without
     duplicating data. I kept project ownership as a direct foreign key for simple authorization,
     then added composite primary keys to the junction tables so the same person, assignment, or
     dependency cannot be recorded twice.

2. “Can you help me make a simple seeded login flow without adding a full auth provider? I need the
   manager/member distinction to be checked by API routes, not only hidden in the page.”
   - This informed the seeded demo accounts, password hashing, and short-lived bearer session
     tokens used by the browser client. I added reusable route dependencies for authentication,
     manager-only operations, and project visibility, which means hiding a control in the UI is
     never the only protection. I then tested that a member cannot invoke manager routes directly.

3. “What is a clear way to model the allowed task status changes, including Blocked returning to
   whichever state it came from?”
   - I kept an explicit transition map in the task model and added `blocked_from` to remember the
     state a task should return to when unblocked. The API calculates and returns the legal next
     states so the interface can guide people away from invalid choices; the shared server-side
     validation remains authoritative for every client and endpoint.

## Building and correcting task behaviour

4. “A task should not be marked Done if one of its blockers is unfinished. Where should I validate
   that so normal edits, buttons and any later UI all behave consistently?”
   - I placed this rule in the shared status-transition service rather than in the frontend or one
     route, so a future board, bulk action, or API consumer cannot accidentally bypass it. The
     service checks outstanding blockers before allowing Done and produces a clear validation
     response. Tests cover direct illegal jumps, Blocked/Unblocked behaviour, and unfinished
     dependency rejection.

5. “When a person is removed from a project, how can I also remove their assignments on that
   project’s tasks and leave an audit trail?”
   - I used the project-update transaction to remove only that member's assignments on tasks in the
     same project, while appending one timeline event for each automatic unassignment. Keeping both
     changes in the transaction prevents a project from being left in a partially updated state. I
     reviewed the relationship queries to ensure assignments in other projects are untouched.

6. “I need a task finder that searches and filters on the server. Can you suggest a query structure
   that lets the list endpoint and CSV export use exactly the same filters?”
   - I extracted shared helpers that start from the requesting user's visible projects and then
     apply search text, status, assignee, priority, due-date, and ordering clauses. Both the list
     endpoint and CSV export call those helpers, so an exported result matches the filtered screen
     rather than becoming a subtly different query. I added coverage for pagination, totals,
     filters, ordering, member visibility, and CSV output.

7. “For a multi-select status update, should I use one transaction for every selected task?”
   - The first suggestion was an all-or-nothing transaction, which did not fit the brief because a
     single illegal lifecycle move would undo unrelated valid updates. I changed the operation to
     use a savepoint for each selected task, preserving successful updates while rolling back only
     the rejected one. The response returns a result and clear rejection reason per task ID, and
     tests cover a deliberately mixed valid/invalid batch.

## Dashboard, history and alerts

8. “If a completed task is edited later, how should the dashboard still know when it was completed
   for an eight-week completion chart?”
   - I added a dedicated `completed_at` timestamp that is set only when a task transitions to Done
     and cleared when the task is reopened. The dashboard's eight-week series reads this lifecycle
     event rather than the generic update timestamp, so a later title, assignee, or due-date edit
     cannot make an old completion appear as a new one.

9. “I need comments and field changes in one immutable task timeline. Is it better to have separate
   comments and audit tables?”
   - I chose one append-only activity table so comments, status changes, assignments, and field
     edits can be presented in one correctly ordered timeline. Each write records the relevant
     before/after values in the same database transaction as the task change. There is deliberately
     no edit or delete endpoint for activities, which preserves a useful audit record.

10. “How should overdue-alert dismissal work when several people are assigned to a task and its due
    date changes later?”
   - I used a task/user dismissal table with a uniqueness constraint, so acknowledgement is personal
     and one assignee's dismissal cannot hide the alert for another. When a due date changes, the
     application clears that task's existing dismissal rows, allowing every assignee to see the
     revised deadline if it is overdue again.

## Frontend and deployment review

11. “The frontend is dependency-free, but the rendering functions are becoming hard to scan. Can
    you suggest a refactor that preserves behaviour?”
   - I replaced dense inline templates with named rendering, payload-building, downloading, and
     event-binding functions while leaving the behaviour and API contract intact. This made state
     transitions and DOM updates easier to inspect during review. I syntax-checked the browser
     script and reran the backend suite after the refactor.

12. “I want a project board without creating another way to bypass task lifecycle rules. How can
    native drag-and-drop reuse the existing API?”
   - I use the API-provided legal next statuses to mark eligible board columns during a drag and
     send the resulting change through the existing status endpoint. This gives the board the same
     dependency and lifecycle validation as the list view, rather than duplicating policy in
     JavaScript. The normal task-list buttons remain as a clear keyboard-friendly alternative.

13. “Can this FastAPI app run on Vercel, and what needs to change so the local SQLite database is
    not used for deployed data?”
   - I added a Vercel ASGI entrypoint and rewrite configuration so one FastAPI application serves
     both its JSON routes and the browser client. SQLite remains the local default, while
     `NORTHSTAR_DATABASE_URL` switches SQLAlchemy to Supabase Postgres in production. I also
     disabled psycopg prepared statements for Supabase's transaction pooler after production logs
     showed duplicate prepared-statement failures, and verified that credentials were not committed.

## Verification approach

For generated code, I did not treat a successful response as proof of correctness. I checked the
routes, data model, and responses against the brief; wrote or expanded `unittest` coverage around
the server rules; and ran the full suite after substantive changes. I also exercised the normal UI
flows with the seeded manager and member accounts, reviewed deployment runtime logs, and verified
the live health endpoint after deployment.
