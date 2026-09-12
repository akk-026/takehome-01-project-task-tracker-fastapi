# Decisions

## 1. Use FastAPI with SQLAlchemy and SQLite

- **Chose:** FastAPI for the API, SQLAlchemy for persistence, and SQLite for local development.
- **Rejected:** A file-backed JSON store and client-owned state.
- **Why:** Relational membership, assignments, and blockers map directly to junction tables, while
  SQLite keeps the take-home runnable without an external service.

## 2. Enforce permissions and visibility on the server

- **Chose:** Every task/project route derives visibility from the authenticated user.
- **Rejected:** Hiding controls in the browser as the permission boundary.
- **Why:** Browser requests can be changed, so membership and manager checks must be made by FastAPI.

## 3. Reuse lifecycle validation for single and bulk actions

- **Chose:** The bulk endpoint calls the same task transition and assignment helpers as individual
  task actions.
- **Rejected:** A separate, simplified bulk validation path.
- **Why:** A batch action must not bypass blockers, legal moves, or project-membership assignment.

## 4. Use a savepoint per selected task

- **Chose:** Each bulk item runs in its own SQLAlchemy nested transaction.
- **Rejected:** One all-or-nothing transaction or a separate request per task from the browser.
- **Why:** The brief requires partial success with an explanation for each rejection; savepoints keep
  valid sibling changes while rolling back only an invalid item.

## 5. Treat assignee bulk changes as replacement

- **Chose:** A bulk assignee action replaces each selected task's assignee set, including allowing an
  empty set to unassign everyone.
- **Rejected:** An ambiguous add/remove toggle.
- **Why:** One explicit operation is predictable across tasks; invalid project members are rejected
  per task rather than silently ignored.

## 6. Share finder logic with CSV export

- **Chose:** Finder and export use common server-side filtering and ordering helpers.
- **Rejected:** Exporting the current browser page or reimplementing filters in the client.
- **Why:** The downloaded CSV accurately represents every matching visible task, not only a page or
  a potentially divergent client-side result.

## 7. Reverse the compact frontend style

- **Initially chose:** Small, dependency-free JavaScript written as compact inline templates.
- **Changed to:** Named template, payload, download, and event-binding functions.
- **Why:** The compact version was quick to begin with but had long lines that made Feature 7 harder
  to extend and review. The refactor keeps the no-build frontend while making responsibilities clear.

## 8. Store completion time separately from update time

- **Chose:** Set `completed_at` when a task enters Done and clear it if the task is reopened.
- **Rejected:** Treating `updated_at` as a completion timestamp.
- **Why:** Finished tasks can be edited after completion. A separate timestamp makes the eight-week
  completion chart and completed-this-week total stable and truthful.

## 9. Return one visibility-scoped dashboard summary

- **Chose:** Calculate dashboard totals, breakdowns, and calendar-week buckets in one authenticated
  API response using only active projects the viewer can access.
- **Rejected:** Loading every task in the browser and aggregating there, or exposing manager-wide
  figures to regular members.
- **Why:** It protects project visibility, keeps the dashboard compact, and makes all displayed
  values come from a single consistent server-side snapshot.

## 10. Make timeline events append-only records

- **Chose:** Store task activity and comments in one table, with no API operation to update or delete
  a row.
- **Rejected:** Editable comment records alongside a separate audit log, or allowing managers to
  clean up history.
- **Why:** A single chronological feed is straightforward to inspect, and treating comments as
  immutable events satisfies the requirement that the complete task history cannot be rewritten.

## 11. Make alert dismissals personal and deadline-specific

- **Chose:** Show overdue alerts only to assignees, store their dismissals separately, and clear all
  dismissals as soon as a task's due date changes.
- **Rejected:** A global task-level dismissal, or retaining a dismissal if a deadline is revised.
- **Why:** Each assignee needs independent control over their alert. A changed due date represents a
  new commitment, so the alert must reliably return for everyone rather than being hidden by stale state.

## 12. Build the board on the existing lifecycle endpoint

- **Chose:** Native browser drag-and-drop in the project view, using the API-provided legal next
  statuses to highlight valid columns and the existing single-task status endpoint for the drop.
- **Rejected:** A board-specific status endpoint or client-side transition rules.
- **Why:** The board stays a small presentation layer. It cannot bypass the server's permission,
  blocker, and lifecycle validation, and the detailed list keeps explicit button controls for
  keyboard users.
