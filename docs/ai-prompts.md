# AI prompts

These notes record the prompts used while building this implementation and the checks made on the
result.

## Foundation and access control

### Prompt

“Build the first features of this project tracker with FastAPI, SQLAlchemy, SQLite, and a small
JavaScript frontend. Enforce roles and project membership on the server.”

### Result and review

This produced the application foundation, authentication, roles, projects, tasks, lifecycle rules,
and assignment relationships. I verified the routes with FastAPI tests and added explicit tests that
members cannot access projects outside their membership.

## Finder

### Prompt

“Implement Feature 6: a server-side cross-project task finder with text search, all required filters,
sorting, pagination, totals, and visibility checks. Do not fetch all tasks to the browser.”

### Result and review

The API now returns one page and its total, while the browser submits only filter parameters. I added
tests for text search, each filter, sorting, paging, member visibility, and archived-project hiding.

## Bulk actions and export

### Prompt

“Implement Feature 7 with bulk status, assignee, and due-date changes. Preserve successful items
when other selected tasks are illegal, explain every rejection, and export the currently filtered
list as CSV from the server.”

### Result and review

The first pass considered one database transaction for the entire selection. That was wrong because
one invalid lifecycle move would roll back valid tasks. I changed it to a nested transaction per task
and verified partial success, invalid assignment membership, due-date changes, and filter-matched CSV
content in the automated test suite.

## Frontend readability

### Prompt

“Refactor the dependency-free frontend so its templates, request payloads, downloads, and event
handlers are readable without changing the existing product behavior.”

### Result and review

The compact single-line view functions were replaced with named functions and formatted templates.
I checked the file with Node's syntax checker and ran the complete backend test suite afterward.
