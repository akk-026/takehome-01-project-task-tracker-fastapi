# Schema

The database is managed by SQLAlchemy: SQLite is used locally and PostgreSQL is used for a hosted
deployment. The table structure is the same in both environments.

- `users`: integer `id`, name, unique email, password hash, role, and creation timestamp.
- `projects`: integer `id`, unique short key, name, description, owner ID, archived flag, and
  creation/update timestamps.
- `project_members`: composite primary key of project ID and user ID; this is the project membership
  many-to-many table.
- `tasks`: integer `id`, project ID, title, description, priority enum, optional due date, lifecycle
  status enum, optional `blocked_from` status, soft-delete flag, creation/update timestamps, and an
  optional `completed_at` timestamp set only while the task is Done.
- `task_assignees`: composite primary key of task ID and user ID; this is task assignment's
  many-to-many table.
- `task_blockers`: composite primary key of task ID and blocking task ID; this is the self-referential
  task dependency many-to-many table.
- `task_activities`: integer `id`, task ID, actor ID, event action, optional changed-field name,
  old/new display values, optional comment text, and immutable creation timestamp. It represents the
  task timeline; comments are activity rows rather than a separately editable resource.
- `task_alert_dismissals`: integer `id`, task ID, user ID, and dismissal timestamp. A unique task/user
  pair makes dismissing an alert idempotent; rows are deleted when that task's due date changes.

A project owns many tasks and has one owner. A task belongs to exactly one project. Membership,
assignment, and blockers are many-to-many relationships expressed with junction tables and database
foreign keys. Project keys and junction-table pairs are unique at the database level. The application
enforces role permissions, project visibility, same-project blockers, project-membership assignment,
legal lifecycle moves, and the rule that unfinished blockers prevent completion.

Task activity rows are write-once application records: no API endpoint updates or deletes them.
The database stores the foreign key relationships, while application write paths consistently append
the actor and before/after values in the transaction that changes a task.

Overdue alert eligibility is calculated from task status and due date rather than stored as a second
task state. The dismissal table is intentionally per user because every assignee controls their own
alert, while a revised deadline clears all earlier dismissals.

The finder queries tasks with joins only for project visibility, and filters, sorts, counts, paginates,
and exports on the server. At 100× the data, the first improvements would be database indexes for
task project/status/due date/updated time plus indexes supporting membership and assignment lookups.
The dashboard would also benefit from indexes for active task status and completion timestamps.
