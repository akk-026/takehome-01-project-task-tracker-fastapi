# Architecture

Northstar is a small FastAPI application backed by SQLAlchemy and SQLite. FastAPI serves the JSON
API and the dependency-free browser client from the same local process. The browser stores a bearer
session token in local storage and sends it with each request. The API loads the authenticated user,
applies role and project-visibility rules, changes the database in a transaction, then returns JSON
or a CSV download.

For example, a bulk status update begins when someone selects finder results and chooses a target
status. The browser sends one `POST /api/tasks/bulk` request containing the selected task IDs and
the requested change. The server loads each visible task in a savepoint, applies the normal lifecycle
validator, and records either a success or a rejection with its reason. A rejected task rolls back
only its own savepoint; successful siblings are committed together. The response lets the browser
show a result row for every selected task.

The task finder and CSV export use the same server-side filter, visibility, and ordering helpers.
The browser receives a single page of JSON for the finder, while CSV export creates every currently
filtered visible result on the server. No browser-side filtering of a full task collection is used.

The dashboard is another authenticated server-side summary. It scopes active tasks to the current
user's visible projects, calculates headline totals and status/assignee breakdowns, then returns
eight calendar-week completion buckets. A task records `completed_at` whenever it enters Done, so
completion reporting does not change when a finished task is later edited.

Task history is an append-only `task_activities` table. Each write route adds activity rows in the
same transaction as the task change, so a successful task update and its audit trail cannot diverge.
The timeline and comment endpoints are visibility-checked reads/creates only: there is no update or
delete route for an activity, including comments.

The overdue alert endpoint is scoped to the current user's assigned tasks. It filters active tasks
that are past due and unfinished, excluding that user's dismissal records. A due-date write deletes
all dismissal records for the task in the same transaction, making its revised deadline visible again.

I deliberately have not built invitations, password reset, real-time collaboration, or deployment
yet. Those are kept out of the current scope while all ten required features are completed and tested.
