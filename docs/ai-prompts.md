# AI prompts

I used AI as a pair-programming and review tool while building the application. These are the
substantive prompts in the order I used them; I have kept the wording close to the original working
questions rather than rewriting them as a project specification. I read the changes, adjusted the
approach where needed, and verified the resulting behaviour with the test suite and the browser.

## Foundation and data model

1. “I want a small FastAPI task tracker with a plain JavaScript frontend. What tables do I need for
   projects, users, project membership, tasks, assignees and blockers?”
   - Use a normalized relational model: `projects` owns the work, `users` identifies people, and
     membership, assignment, and blocker junction tables represent the many-to-many relationships
     without duplicating data. Keep project ownership as a direct foreign key to simplify
     authorization, and give each junction table a composite primary key so duplicate memberships,
     assignments, and dependencies are impossible.

2. “Can you help me make a simple seeded login flow without adding a full auth provider? I need the
   manager/member distinction to be checked by API routes, not only hidden in the page.”
   - Seed demo accounts, hash passwords, and return an opaque bearer token after successful login.
     Create reusable route dependencies for authentication, manager-only operations, and project
     visibility. The UI may hide unavailable controls, but every API route must enforce the same
     authorization rule so a member cannot invoke manager actions directly.

3. “What is a clear way to model the allowed task status changes, including Blocked returning to
   whichever state it came from?”
   - Define an explicit transition map in the task model and store `blocked_from` when a task enters
     Blocked, so it can return to its prior working state when unblocked. Let the API return the
     legal next states to guide the interface, but keep shared server-side validation as the final
     authority for every endpoint and client.

## Building and correcting task behaviour

4. “A task should not be marked Done if one of its blockers is unfinished. Where should I validate
   that so normal edits, buttons and any later UI all behave consistently?”
   - Put this rule in the shared status-transition service, not in the frontend or a specific
     route. That way a future board, bulk action, or external API client cannot bypass it. Before
     allowing Done, inspect every blocker and return a clear validation error when any are still
     unfinished; cover illegal jumps, Blocked/Unblocked behaviour, and blockers in tests.

5. “When a person is removed from a project, how can I also remove their assignments on that
   project’s tasks and leave an audit trail?”
   - Perform the membership update and automatic unassignments in one transaction. Remove only the
     departing member's assignments from tasks in that project, then append one timeline event for
     each automatic unassignment. This avoids a partially updated project and leaves assignments in
     every other project untouched.

6. “I need a task finder that searches and filters on the server. Can you suggest a query structure
   that lets the list endpoint and CSV export use exactly the same filters?”
   - Start with a visibility-scoped query for the requesting user, then apply shared search text,
     status, assignee, priority, due-date, and ordering filters. Reuse these helpers for both the
     list endpoint and CSV export so an export always matches the filtered screen. Test pagination,
     totals, filters, ordering, member visibility, and CSV output against the shared query path.

7. “For a multi-select status update, should I use one transaction for every selected task?”
   - Use a savepoint for each selected task rather than an all-or-nothing transaction. This lets
     valid updates commit even if another selected task has an illegal lifecycle move, while still
     rolling back the failed task safely. Return a success or a clear rejection reason for every
     task ID, and test a deliberately mixed valid/invalid batch.

## Dashboard, history and alerts

8. “If a completed task is edited later, how should the dashboard still know when it was completed
   for an eight-week completion chart?”
   - Add a dedicated `completed_at` timestamp, set it only on the transition to Done, and clear it
     when the task is reopened. Build the eight-week completion series from that lifecycle event,
     not the generic update timestamp, so later title, assignee, or due-date edits cannot make an
     old completion appear new.

9. “I need comments and field changes in one immutable task timeline. Is it better to have separate
   comments and audit tables?”
   - Use one append-only activity table so comments, status changes, assignments, and field edits
     appear in a single correctly ordered timeline. Record relevant before/after values in the same
     transaction as the task change. Do not expose edit or delete endpoints for activity rows; that
     preserves a useful audit record.

10. “How should overdue-alert dismissal work when several people are assigned to a task and its due
    date changes later?”
   - Model dismissals with a task/user table and a uniqueness constraint, so acknowledgement is
     personal and one assignee cannot hide an alert for another. When a task's due date changes,
     clear its existing dismissal rows so each assignee can see the revised deadline if it is
     overdue again.

## Frontend and deployment review

11. “The frontend is dependency-free, but the rendering functions are becoming hard to scan. Can
    you suggest a refactor that preserves behaviour?”
   - Split dense inline templates into named rendering, payload-building, downloading, and
     event-binding functions without changing the API contract. This makes state transitions and
     DOM updates easier to inspect, test, and extend. Syntax-check the browser script and rerun the
     backend suite after the refactor.

12. “I want a project board without creating another way to bypass task lifecycle rules. How can
    native drag-and-drop reuse the existing API?”
   - Use the API-provided legal next statuses to mark eligible board columns during a drag, and send
     the resulting move through the existing status endpoint. This gives the board the same
     dependency and lifecycle validation as the list view instead of duplicating policy in
     JavaScript. Keep the normal task-list buttons as a clear keyboard-friendly alternative.

13. “Can this FastAPI app run on Vercel, and what needs to change so the local SQLite database is
    not used for deployed data?”
   - Add a Vercel ASGI entrypoint and rewrite configuration so one FastAPI application serves both
     JSON routes and the browser client. Keep SQLite as the local default, and use
     `NORTHSTAR_DATABASE_URL` to select Supabase Postgres in production. For Supabase's transaction
     pooler, disable psycopg prepared statements to avoid duplicate prepared-statement failures, and
     keep all database credentials in deployment environment variables rather than the repository.

## Implementation-level follow-ups

14. “Can you show me the SQLAlchemy pattern for a project query that managers can use for every
    project, but members can only use for projects where they are a member?”
   - Start with one reusable statement that eagerly loads the owner and members, then narrow it for
     non-managers. Keeping the visibility rule in one helper prevents different endpoints from
     gradually enforcing different policies. For example:

     ```python
     def visible_projects_statement(user: User):
         statement = select(Project).options(
             selectinload(Project.owner), selectinload(Project.members)
         )
         if user.role == UserRole.MANAGER:
             return statement
         return statement.join(Project.members).where(User.id == user.id)
     ```

     Use the same helper for the project list, task lookups, dashboard calculations, and export
     queries. At the single-project level, load the project through the scoped statement and return
     a 404 when it is absent; do not reveal whether an inaccessible project exists.

15. “Can you show the FastAPI dependency code that checks a bearer token once and lets route
    handlers receive the current user?”
   - Create one dependency that extracts the `Authorization: Bearer …` credential, resolves the
     session token, and loads the user from the database. Route handlers then declare a `User`
     parameter instead of repeating authentication logic:

     ```python
     bearer_scheme = HTTPBearer(auto_error=False)

     def get_current_user(
         credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
         session: Session = Depends(get_db),
     ) -> User:
         if not credentials or credentials.scheme.lower() != "bearer":
             raise HTTPException(status_code=401, detail="Please sign in to continue.")
         user_id = session_user_id(session, credentials.credentials)
         user = session.get(User, user_id) if user_id else None
         if not user:
             raise HTTPException(status_code=401, detail="Please sign in to continue.")
         return user
     ```

     Add a small `get_current_manager` dependency on top of this one for manager-only routes. This
     keeps role checks on the server even when a user manually calls an endpoint outside the UI.

16. “My login works locally, but Vercel sometimes says ‘Please sign in to continue’ immediately
    after login. What code should I change?”
   - Do not keep opaque tokens in a module-level dictionary: a Vercel request can run on a different
     serverless instance from the login request, so that dictionary is not shared. Store a hash of
     each generated token in Postgres instead, along with the user ID and expiry. On every request,
     hash the supplied token and look it up:

     ```python
     def session_user_id(session: Session, token: str) -> int | None:
         return session.scalar(
             select(UserSession.user_id).where(
                 UserSession.token_digest == sha256(token.encode()).hexdigest(),
                 UserSession.expires_at > datetime.now(timezone.utc),
             )
         )
     ```

     This keeps the raw token out of the database, makes sessions work across serverless instances,
     and still permits logout by deleting the matching hashed session row.

17. “The Vercel function is deployed, but `/api/health` returns FastAPI’s 404 while the function
    itself is ready. How can I preserve the original request path through a rewrite?”
   - A rewrite to `/api/index.py` can make FastAPI see the function-file path instead of the browser
     path. Pass the original path as a private rewrite query value, then restore it in lightweight
     middleware before routing:

     ```json
     { "source": "/(.*)", "destination": "/api/index.py?__northstar_path=$1" }
     ```

     ```python
     original_path = request.query_params.get("__northstar_path")
     if original_path is not None:
         request.scope["path"] = "/" + original_path.lstrip("/")
     ```

     Remove the private parameter from the forwarded query string as part of the middleware. That
     lets the same ASGI app route `/api/*` normally and serve the browser client’s root and static
     assets without changing their public URLs.

## Verification approach

For generated code, I did not treat a successful response as proof of correctness. I checked the
routes, data model, and responses against the brief; wrote or expanded `unittest` coverage around
the server rules; and ran the full suite after substantive changes. I also exercised the normal UI
flows with the seeded manager and member accounts, reviewed deployment runtime logs, and verified
the live health endpoint after deployment.
