# Schema

The SQLite database is managed by SQLAlchemy.

- `users`: integer `id`, name, unique email, password hash, role, and creation timestamp.
- `projects`: integer `id`, unique short key, name, description, owner ID, archived flag, and
  creation/update timestamps.
- `project_members`: composite primary key of project ID and user ID; this is the project membership
  many-to-many table.
- `tasks`: integer `id`, project ID, title, description, priority enum, optional due date, lifecycle
  status enum, optional `blocked_from` status, soft-delete flag, and creation/update timestamps.
- `task_assignees`: composite primary key of task ID and user ID; this is task assignment's
  many-to-many table.
- `task_blockers`: composite primary key of task ID and blocking task ID; this is the self-referential
  task dependency many-to-many table.

A project owns many tasks and has one owner. A task belongs to exactly one project. Membership,
assignment, and blockers are many-to-many relationships expressed with junction tables and database
foreign keys. Project keys and junction-table pairs are unique at the database level. The application
enforces role permissions, project visibility, same-project blockers, project-membership assignment,
legal lifecycle moves, and the rule that unfinished blockers prevent completion.

The finder queries tasks with joins only for project visibility, and filters, sorts, counts, paginates,
and exports on the server. At 100× the data, the first improvements would be database indexes for
task project/status/due date/updated time plus indexes supporting membership and assignment lookups.
