# AI prompts

I used AI as a pair-programming and review tool while building the application. These are the
substantive prompts in the order I used them; I have kept the wording close to the original working
questions rather than rewriting them as a project specification. I read the changes, adjusted the
approach where needed, and verified the resulting behaviour with the test suite and the browser.

## Foundation and data model

1. “I want a small FastAPI task tracker with a plain JavaScript frontend. What tables do I need for
   projects, users, project membership, tasks, assignees and blockers?”
   - I used the suggested junction-table shape, then kept ownership as a direct project foreign key
     and added composite keys for membership, assignment and blocker relationships.

2. “Can you help me make a simple seeded login flow without adding a full auth provider? I need the
   manager/member distinction to be checked by API routes, not only hidden in the page.”
   - This led to the seeded demo users, hashed passwords and bearer session tokens. I added route
     dependencies for authentication, manager checks and project visibility, then tested that a
     member cannot call manager routes directly.

3. “What is a clear way to model the allowed task status changes, including Blocked returning to
   whichever state it came from?”
   - I kept the transition map in the task model and added `blocked_from`. The API returns the
     currently legal moves so the UI can avoid offering impossible actions, but the server remains
     the authority.

## Building and correcting task behaviour

4. “A task should not be marked Done if one of its blockers is unfinished. Where should I validate
   that so normal edits, buttons and any later UI all behave consistently?”
   - I placed the check in the shared status-transition service rather than in the frontend or a
     particular route. I covered direct illegal jumps, blocked/unblocked transitions and unfinished
     blockers in tests.

5. “When a person is removed from a project, how can I also remove their assignments on that
   project’s tasks and leave an audit trail?”
   - I used the project update transaction to remove the assignments and append one timeline event
     per automatic unassignment. I reviewed the generated relationship changes to make sure the
     removal was limited to that project.

6. “I need a task finder that searches and filters on the server. Can you suggest a query structure
   that lets the list endpoint and CSV export use exactly the same filters?”
   - I extracted shared visibility, filter and ordering helpers. I added tests for pagination,
     total count, every filter, ordering, member visibility and CSV output.

7. “For a multi-select status update, should I use one transaction for every selected task?”
   - The first suggestion was an all-or-nothing transaction. That was wrong for this brief: one
     invalid lifecycle move would also undo valid selections. I changed the implementation to use a
     savepoint per task, return a success or rejection reason for each selected ID, and tested a
     mixed valid/invalid batch.

## Dashboard, history and alerts

8. “If a completed task is edited later, how should the dashboard still know when it was completed
   for an eight-week completion chart?”
   - I added `completed_at`, set it on transition to Done, and clear it on reopening. This avoids
     incorrectly treating a later title or due-date edit as a new completion.

9. “I need comments and field changes in one immutable task timeline. Is it better to have separate
   comments and audit tables?”
   - I chose one append-only activity table after reviewing the trade-off. Comments are activity
     rows, writes add before/after values in the same database transaction, and there is deliberately
     no edit or delete endpoint for either kind of event.

10. “How should overdue-alert dismissal work when several people are assigned to a task and its due
    date changes later?”
    - I used a task/user dismissal table with a uniqueness constraint. Dismissal is personal; a due
      date change clears the task’s old dismissals so each assignee sees the revised deadline again.

## Frontend and deployment review

11. “The frontend is dependency-free, but the rendering functions are becoming hard to scan. Can
    you suggest a refactor that preserves behaviour?”
    - I replaced compact inline templates with named render, payload, download and event-binding
      functions. I syntax-checked the script and reran the backend tests afterward.

12. “I want a project board without creating another way to bypass task lifecycle rules. How can
    native drag-and-drop reuse the existing API?”
    - I used the API-provided legal next statuses to highlight valid board columns and sent a drop
      through the existing status endpoint. I kept the normal buttons in the task list for an
      explicit, keyboard-friendly alternative.

13. “Can this FastAPI app run on Vercel, and what needs to change so the local SQLite database is
    not used for deployed data?”
    - I added a Vercel ASGI entrypoint and configuration, retained SQLite only for local work, and
      made `NORTHSTAR_DATABASE_URL` select hosted Postgres via SQLAlchemy. I reviewed the generated
      configuration to ensure no credentials were committed.

## Verification approach

For generated code, I did not treat a successful response as proof of correctness. I checked the
routes and schema against the brief, wrote or expanded the `unittest` coverage around the server
rules, ran the full suite after the changes, and exercised the normal UI flows with the seeded
manager and member accounts.
