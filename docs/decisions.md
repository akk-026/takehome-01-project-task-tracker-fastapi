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
