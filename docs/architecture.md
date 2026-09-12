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

I deliberately have not built invitations, password reset, real-time collaboration, dashboard
analytics, immutable task history, alerts, or deployment yet. Those cover later requirements and
are kept out of the current scope while the first seven features are completed and tested.
