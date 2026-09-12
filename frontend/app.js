const root = document.querySelector('#app');
const tokenKey = 'northstar-token';
const apiBaseUrl = window.location.port === '8000' ? '' : 'http://localhost:8000';

const statuses = ['BACKLOG', 'IN_PROGRESS', 'IN_REVIEW', 'BLOCKED', 'DONE'];
const priorities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
const defaultTaskFilters = { page: 1, page_size: 10, sort_by: 'updated_at', sort_direction: 'desc' };

function authHeaders() {
  const token = localStorage.getItem(tokenKey);
  return token ? { authorization: `Bearer ${token}` } : {};
}

async function api(path, options = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers: { 'content-type': 'application/json', ...authHeaders(), ...options.headers }
  });
  const contentType = response.headers.get('content-type') || '';
  const body = response.status === 204 ? null : contentType.includes('application/json')
    ? await response.json()
    : { detail: 'The app could not reach the FastAPI API. Start it on http://localhost:8000.' };
  if (!response.ok) throw new Error(body.detail || 'Request failed.');
  return body;
}

function escapeHtml(value) {
  const entities = { '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' };
  return String(value).replace(/[&<>'"]/g, character => entities[character]);
}

function errorMessage(error) {
  return error ? `<div class="error">${escapeHtml(error)}</div>` : '';
}

function statusLabel(status) {
  return status.split('_').map(word => word[0] + word.slice(1).toLowerCase()).join(' ');
}

function selected(value, current) {
  return String(value) === String(current ?? '') ? 'selected' : '';
}

function optionList(values, current, label = value => value) {
  return values.map(value => `<option value="${value}" ${selected(value, current)}>${escapeHtml(label(value))}</option>`).join('');
}

function memberChoices(users, selectedIds = [], name = 'memberIds') {
  return users.map(person => `
    <label class="member">
      <input type="checkbox" name="${name}" value="${person.id}" ${selectedIds.includes(person.id) ? 'checked' : ''}>
      ${escapeHtml(person.name)}
    </label>
  `).join('');
}

function taskChoices(tasks, selectedIds = [], currentTaskId = null) {
  const availableTasks = tasks.filter(task => task.id !== currentTaskId);
  if (!availableTasks.length) return '<p class="hint">No other tasks are available as blockers.</p>';
  return availableTasks.map(task => `
    <label class="member">
      <input type="checkbox" name="blockerIds" value="${task.id}" ${selectedIds.includes(task.id) ? 'checked' : ''}>
      ${escapeHtml(task.title)}
    </label>
  `).join('');
}

function taskPayload(values) {
  return {
    title: values.get('title'),
    description: values.get('description'),
    priority: values.get('priority'),
    due_date: values.get('dueDate') || null,
    blocker_ids: values.getAll('blockerIds').map(Number),
    assignee_ids: values.getAll('assigneeIds').map(Number)
  };
}

function taskSearchPath(filters, endpoint = '/api/tasks') {
  const entries = Object.entries(filters).filter(([, value]) => value !== '' && value !== null && value !== undefined);
  return `${endpoint}?${new URLSearchParams(entries)}`;
}

function filterUsers(projects, users) {
  const people = new Map(users.map(person => [person.id, person]));
  projects.flatMap(project => project.members).forEach(person => people.set(person.id, person));
  return [...people.values()].sort((first, second) => first.name.localeCompare(second.name));
}

function statusBadge(task) {
  return `<span class="task-status ${task.status.toLowerCase()}">${escapeHtml(statusLabel(task.status))}</span>`;
}

function priorityBadge(task) {
  return `<span class="priority ${task.priority.toLowerCase()}">${escapeHtml(task.priority)}</span>`;
}

function projectCard(project, isManager, users) {
  const members = project.members.map(member => escapeHtml(member.name)).join(', ') || 'No members';
  const owners = users.map(person => `
    <option value="${person.id}" ${person.id === project.owner.id ? 'selected' : ''}>${escapeHtml(person.name)}</option>
  `).join('');
  const controls = isManager ? `
    <details>
      <summary>Manage project</summary>
      <form class="edit-project-form" data-project-id="${project.id}">
        <label>Key</label><input name="key" maxlength="12" value="${escapeHtml(project.key)}" required>
        <label>Name</label><input name="name" maxlength="160" value="${escapeHtml(project.name)}" required>
        <label>Description</label><input name="description" maxlength="2000" value="${escapeHtml(project.description)}">
        <label>Owner</label><select name="ownerId">${owners}</select>
        <button>Save project</button>
      </form>
      <form class="members-form" data-project-id="${project.id}">
        <fieldset><legend>Project members</legend>${memberChoices(users, project.members.map(member => member.id))}</fieldset>
        <button>Save members</button>
      </form>
      <button class="${project.archived ? 'restore' : 'archive'}" data-project-id="${project.id}">
        ${project.archived ? 'Restore project' : 'Archive project'}
      </button>
    </details>
  ` : '';
  return `
    <article class="project">
      <div><span class="project-key">${escapeHtml(project.key)}</span>${project.archived ? '<span class="archived">Archived</span>' : ''}</div>
      <h2>${escapeHtml(project.name)}</h2>
      <p>${escapeHtml(project.description || 'No description yet.')}</p>
      <small><b>Owner:</b> ${escapeHtml(project.owner.name)} · <b>Members:</b> ${members}</small>
      <button class="open-project secondary" data-project-id="${project.id}">Open project</button>
      ${controls}
    </article>
  `;
}

function assignedTaskCard(task) {
  return `
    <article class="task assigned-task">
      <div class="task-heading"><div><span class="project-key">${escapeHtml(task.project_key)}</span><h3>${escapeHtml(task.title)}</h3></div>${statusBadge(task)}</div>
      <p>${escapeHtml(task.project_name)}</p>
      <small><b>Due:</b> ${task.due_date || 'No due date'}</small>
      <button class="open-project secondary" data-project-id="${task.project_id}">Open project</button>
    </article>
  `;
}

function taskSearchCard(task) {
  return `
    <article class="task assigned-task">
      <div class="task-heading">
        <div><span class="project-key">${escapeHtml(task.project_key)}</span><h3>${escapeHtml(task.title)}</h3></div>
        <div class="task-badges">${statusBadge(task)}${priorityBadge(task)}</div>
      </div>
      <p>${escapeHtml(task.project_name)} · ${escapeHtml(task.description || 'No description')}</p>
      <small><b>Due:</b> ${task.due_date || 'No due date'} · <b>Assignees:</b> ${task.assignee_ids.length}</small>
      <label class="select-task"><input type="checkbox" name="taskIds" value="${task.id}"> Select for bulk action</label>
      <button class="open-project secondary" data-project-id="${task.project_id}">Open project</button>
    </article>
  `;
}

function statusControls(task) {
  if (!task.available_statuses.length) return '<p class="hint">No status moves are available.</p>';
  const buttons = task.available_statuses.map(nextStatus => `
    <button class="status-move secondary" data-task-id="${task.id}" data-status="${nextStatus}">
      Move to ${escapeHtml(statusLabel(nextStatus))}
    </button>
  `).join('');
  return `<div class="status-actions">${buttons}</div>`;
}

function taskCard(task, tasks, isManager, members) {
  const blockers = task.blocker_ids.map(id => tasks.find(candidate => candidate.id === id)?.title || `Task #${id}`).map(escapeHtml).join(', ');
  const assignees = task.assignee_ids.map(id => members.find(member => member.id === id)?.name || `User #${id}`).map(escapeHtml).join(', ');
  const deleteControl = isManager ? `<button class="delete-task" data-task-id="${task.id}">Delete task</button>` : '';
  return `
    <article class="task">
      <div class="task-heading"><h3>${escapeHtml(task.title)}</h3><div class="task-badges">${statusBadge(task)}${priorityBadge(task)}</div></div>
      <p>${escapeHtml(task.description || 'No description yet.')}</p>
      <small><b>Due:</b> ${task.due_date || 'No due date'} · <b>Blocked by:</b> ${blockers || 'Nothing'} · <b>Assigned:</b> ${assignees || 'Nobody'}</small>
      ${statusControls(task)}
      <details>
        <summary>Edit task</summary>
        <form class="edit-task-form" data-task-id="${task.id}">
          <label>Title</label><input name="title" maxlength="300" value="${escapeHtml(task.title)}" required>
          <label>Description</label><textarea name="description" maxlength="4000">${escapeHtml(task.description)}</textarea>
          <label>Priority</label><select name="priority">${optionList(priorities, task.priority)}</select>
          <label>Due date</label><input name="dueDate" type="date" value="${task.due_date || ''}">
          <fieldset><legend>Blocked by</legend>${taskChoices(tasks, task.blocker_ids, task.id)}</fieldset>
          <fieldset><legend>Assignees</legend>${memberChoices(members, task.assignee_ids, 'assigneeIds')}</fieldset>
          <button>Save task</button>
        </form>
        ${deleteControl}
      </details>
    </article>
  `;
}

function taskSearchForm(projects, people, filters) {
  const projectOptions = projects.map(project => `
    <option value="${project.id}" ${selected(project.id, filters.project_id)}>${escapeHtml(project.key)} · ${escapeHtml(project.name)}</option>
  `).join('');
  const personOptions = people.map(person => `
    <option value="${person.id}" ${selected(person.id, filters.assignee_id)}>${escapeHtml(person.name)}</option>
  `).join('');
  return `
    <form id="task-search" class="search-controls">
      <label>Search</label>
      <input name="q" value="${escapeHtml(filters.q || '')}" placeholder="Title or description">
      <label>Project</label>
      <select name="project_id"><option value="">All visible projects</option>${projectOptions}</select>
      <label>Status</label>
      <select name="status"><option value="">Any status</option>${optionList(statuses, filters.status, statusLabel)}</select>
      <label>Assignee</label>
      <select name="assignee_id"><option value="">Anyone</option>${personOptions}</select>
      <label>Priority</label>
      <select name="priority"><option value="">Any priority</option>${optionList(priorities, filters.priority)}</select>
      <label>Due date</label>
      <select name="overdue"><option value="">Any</option><option value="true" ${selected('true', filters.overdue)}>Overdue</option></select>
      <label>Sort by</label>
      <select name="sort_by">
        <option value="updated_at" ${selected('updated_at', filters.sort_by)}>Last updated</option>
        <option value="due_date" ${selected('due_date', filters.sort_by)}>Due date</option>
        <option value="priority" ${selected('priority', filters.sort_by)}>Priority</option>
      </select>
      <label>Direction</label>
      <select name="sort_direction">
        <option value="desc" ${selected('desc', filters.sort_direction)}>Descending</option>
        <option value="asc" ${selected('asc', filters.sort_direction)}>Ascending</option>
      </select>
      <button>Apply filters</button>
    </form>
  `;
}

function bulkActionForm(people) {
  return `
    <form id="bulk-update" class="bulk-controls">
      <h3>Bulk action</h3>
      <p class="hint">Choose tasks above, then apply one change. Every task reports its own result.</p>
      <label>Change</label>
      <select name="action">
        <option value="status">Move status</option>
        <option value="assignees">Replace assignees</option>
        <option value="due_date">Set due date</option>
      </select>
      <div data-bulk-value="status">
        <label>New status</label>
        <select name="status">${optionList(statuses, 'BACKLOG', statusLabel)}</select>
      </div>
      <div data-bulk-value="assignees" hidden>
        <fieldset><legend>New assignees</legend>${memberChoices(people, [], 'assigneeIds') || '<p class="hint">No available assignees.</p>'}</fieldset>
      </div>
      <div data-bulk-value="due_date" hidden>
        <label>New due date</label>
        <input name="dueDate" type="date">
      </div>
      <button>Apply to selected tasks</button>
    </form>
  `;
}

function bulkResultPanel(result, tasks) {
  if (!result) return '';
  const titles = new Map(tasks.map(task => [task.id, task.title]));
  const rows = result.results.map(item => {
    const title = item.task?.title || titles.get(item.task_id) || `Task #${item.task_id}`;
    return `
      <li class="bulk-result ${item.succeeded ? 'succeeded' : 'rejected'}">
        <b>${item.succeeded ? 'Succeeded' : 'Rejected'}:</b> ${escapeHtml(title)} — ${escapeHtml(item.detail)}
      </li>
    `;
  }).join('');
  return `<section class="bulk-results"><h3>Bulk update results</h3><p class="hint">${result.succeeded} succeeded · ${result.rejected} rejected</p><ul>${rows}</ul></section>`;
}

function taskSearchPanel(result, projects, people, filters, bulkResult) {
  const pageStart = result.total ? (result.page - 1) * result.page_size + 1 : 0;
  const pageEnd = Math.min(result.page * result.page_size, result.total);
  const cards = result.items.length ? result.items.map(taskSearchCard).join('') : '<p class="hint">No tasks match these filters.</p>';
  const pagination = result.total_pages > 1 ? `
    <div class="pagination">
      <button class="task-page secondary" data-task-page="${result.page - 1}" ${result.page === 1 ? 'disabled' : ''}>Previous</button>
      <span>Page ${result.page} of ${result.total_pages}</span>
      <button class="task-page secondary" data-task-page="${result.page + 1}" ${result.page === result.total_pages ? 'disabled' : ''}>Next</button>
    </div>
  ` : '';
  return `
    <section class="panel">
      <div class="section-heading"><h2>Find tasks</h2><button id="export-tasks" class="secondary">Export filtered CSV</button></div>
      ${taskSearchForm(projects, people, filters)}
      <p class="hint">Showing ${pageStart}–${pageEnd} of ${result.total} matching tasks.</p>
      <div class="tasks">${cards}</div>
      ${pagination}
      ${result.items.length ? bulkActionForm(people) : ''}
      ${bulkResultPanel(bulkResult, result.items)}
    </section>
  `;
}

function createProjectPanel(users) {
  return `
    <section class="panel">
      <h2>Create project</h2>
      <form id="create-project">
        <label>Key</label><input name="key" maxlength="12" placeholder="OPS" required>
        <label>Name</label><input name="name" maxlength="160" required>
        <label>Description</label><input name="description" maxlength="2000">
        <label>Owner</label><select name="ownerId">${users.map(person => `<option value="${person.id}">${escapeHtml(person.name)}</option>`).join('')}</select>
        <fieldset><legend>Project members</legend>${memberChoices(users)}</fieldset>
        <button>Create project</button>
      </form>
    </section>
  `;
}

function createTaskPanel(project, tasks) {
  return `
    <section class="panel">
      <h2>Create task</h2>
      <form id="create-task">
        <label>Title</label><input name="title" maxlength="300" required>
        <label>Description</label><textarea name="description" maxlength="4000"></textarea>
        <label>Priority</label>
        <select name="priority">
          <option value="LOW">Low</option>
          <option value="MEDIUM" selected>Medium</option>
          <option value="HIGH">High</option>
          <option value="CRITICAL">Critical</option>
        </select>
        <label>Due date</label><input name="dueDate" type="date">
        <fieldset><legend>Blocked by</legend>${taskChoices(tasks)}</fieldset>
        <fieldset><legend>Assignees</legend>${memberChoices(project.members, [], 'assigneeIds')}</fieldset>
        <button>Create task</button>
      </form>
    </section>
  `;
}

function homeFilters(values) {
  return {
    q: values.get('q'), project_id: values.get('project_id'), status: values.get('status'),
    assignee_id: values.get('assignee_id'), priority: values.get('priority'), overdue: values.get('overdue'),
    sort_by: values.get('sort_by'), sort_direction: values.get('sort_direction'), page: 1, page_size: 10
  };
}

function bulkPayload(values, taskIds) {
  const action = values.get('action');
  return {
    task_ids: taskIds,
    action,
    status: action === 'status' ? values.get('status') : null,
    assignee_ids: action === 'assignees' ? values.getAll('assigneeIds').map(Number) : [],
    due_date: action === 'due_date' ? values.get('dueDate') || null : null
  };
}

function updateBulkInputs(form) {
  const action = new FormData(form).get('action');
  form.querySelectorAll('[data-bulk-value]').forEach(element => {
    element.hidden = element.dataset.bulkValue !== action;
  });
}

async function downloadTaskExport(filters) {
  const response = await fetch(taskSearchPath(filters, `${apiBaseUrl}/api/tasks/export`), { headers: authHeaders() });
  if (!response.ok) {
    const body = await response.json();
    throw new Error(body.detail || 'Could not export tasks.');
  }
  const link = document.createElement('a');
  link.href = URL.createObjectURL(await response.blob());
  link.download = 'northstar-tasks.csv';
  link.click();
  URL.revokeObjectURL(link.href);
}

function showLogin(error = '') {
  root.innerHTML = `
    <div class="brand">✦ NORTHSTAR</div>
    <h1>Make work visible.</h1>
    <p>Sign in to the project tracker.</p>
    <form id="login">
      <label>Email</label>
      <input name="email" type="email" value="alice@northstar.test" required>
      <label>Password</label>
      <input name="password" type="password" value="manager123" required>
      <button>Sign in</button>
    </form>
    ${errorMessage(error)}
    <div class="demo"><b>Demo accounts</b><br>Manager: alice@northstar.test / manager123<br>Member: dan@northstar.test / member123</div>
  `;
  document.querySelector('#login').onsubmit = async event => {
    event.preventDefault();
    try {
      const credentials = Object.fromEntries(new FormData(event.currentTarget));
      const result = await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify(credentials)
      });
      localStorage.setItem(tokenKey, result.token);
      showHome(result.user);
    } catch (reason) {
      showLogin(reason.message);
    }
  };
}

async function showProjectDetail(user, projectId, options = {}) {
  const { showArchived = false, error = '' } = options;
  try {
    const [project, tasks] = await Promise.all([
      api(`/api/projects/${projectId}`),
      api(`/api/tasks/projects/${projectId}`)
    ]);
    root.innerHTML = `
      <div class="topbar">
        <div><div class="brand">✦ NORTHSTAR</div><h1>${escapeHtml(project.name)}</h1><p>${escapeHtml(project.description || 'No description yet.')}</p></div>
        <button id="back-to-projects" class="secondary">← Projects</button>
      </div>
      ${errorMessage(error)}
      ${createTaskPanel(project, tasks)}
      <section>
        <h2>Tasks</h2>
        <div class="tasks">${tasks.length ? tasks.map(task => taskCard(task, tasks, user.role === 'MANAGER', project.members)).join('') : '<p class="hint">No tasks in this project yet.</p>'}</div>
      </section>
    `;
    bindProjectEvents(user, projectId, showArchived);
  } catch (reason) {
    showHome(user, { error: reason.message, showArchived });
  }
}

function bindProjectEvents(user, projectId, showArchived) {
  document.querySelector('#back-to-projects').onclick = () => showHome(user, { showArchived });
  document.querySelector('#create-task').onsubmit = async event => {
    event.preventDefault();
    try {
      await api(`/api/tasks/projects/${projectId}`, { method: 'POST', body: JSON.stringify(taskPayload(new FormData(event.currentTarget))) });
      showProjectDetail(user, projectId, { showArchived });
    } catch (reason) {
      showProjectDetail(user, projectId, { showArchived, error: reason.message });
    }
  };
  document.querySelectorAll('.edit-task-form').forEach(form => {
    form.onsubmit = async event => {
      event.preventDefault();
      try {
        await api(`/api/tasks/${form.dataset.taskId}`, { method: 'PUT', body: JSON.stringify(taskPayload(new FormData(form))) });
        showProjectDetail(user, projectId, { showArchived });
      } catch (reason) {
        showProjectDetail(user, projectId, { showArchived, error: reason.message });
      }
    };
  });
  document.querySelectorAll('.status-move').forEach(button => {
    button.onclick = async () => {
      try {
        await api(`/api/tasks/${button.dataset.taskId}/status`, { method: 'POST', body: JSON.stringify({ status: button.dataset.status }) });
        showProjectDetail(user, projectId, { showArchived });
      } catch (reason) {
        showProjectDetail(user, projectId, { showArchived, error: reason.message });
      }
    };
  });
  document.querySelectorAll('.delete-task').forEach(button => {
    button.onclick = async () => {
      try {
        await api(`/api/tasks/${button.dataset.taskId}`, { method: 'DELETE' });
        showProjectDetail(user, projectId, { showArchived });
      } catch (reason) {
        showProjectDetail(user, projectId, { showArchived, error: reason.message });
      }
    };
  });
}

async function showHome(user, options = {}) {
  const { error = '', showArchived = false, searchFilters = {}, bulkResult = null } = options;
  try {
    const isManager = user.role === 'MANAGER';
    const taskFilters = { ...defaultTaskFilters, ...searchFilters };
    const [projects, users, assignedTasks, taskSearch] = await Promise.all([
      api(isManager && showArchived ? '/api/projects?include_archived=true' : '/api/projects'),
      isManager ? api('/api/users') : Promise.resolve([]),
      api('/api/tasks/assigned'),
      api(taskSearchPath(taskFilters))
    ]);
    const activeProjects = projects.filter(project => !project.archived);
    const archivedProjects = projects.filter(project => project.archived);
    const people = filterUsers(activeProjects, users);
    const archiveToggle = isManager ? `<button id="toggle-archived" class="secondary">${showArchived ? 'Hide archived projects' : 'Show archived projects'}</button>` : '';
    const projectCreation = isManager ? createProjectPanel(users) : '<p class="hint">You only see projects where you are a member.</p>';
    const archivedSection = showArchived ? `<section><h2>Archived projects</h2><div class="projects">${archivedProjects.length ? archivedProjects.map(project => projectCard(project, true, users)).join('') : '<p class="hint">No archived projects.</p>'}</div></section>` : '';
    root.innerHTML = `
      <div class="topbar"><div><div class="brand">✦ NORTHSTAR</div><h1>Welcome, ${escapeHtml(user.name.split(' ')[0])}.</h1><span class="role">${isManager ? 'Manager' : 'Member'}</span></div><div class="header-actions">${archiveToggle}<button id="logout" class="secondary">Sign out</button></div></div>
      ${errorMessage(error)}
      ${taskSearchPanel(taskSearch, activeProjects, people, taskFilters, bulkResult)}
      <section><h2>Assigned to you</h2><div class="tasks">${assignedTasks.length ? assignedTasks.map(assignedTaskCard).join('') : '<p class="hint">No tasks are assigned to you.</p>'}</div></section>
      ${projectCreation}
      <section><h2>${isManager ? 'All active projects' : 'Your projects'}</h2><div class="projects">${activeProjects.length ? activeProjects.map(project => projectCard(project, isManager, users)).join('') : '<p class="hint">No active projects yet.</p>'}</div></section>
      ${archivedSection}
    `;
    bindHomeEvents(user, { showArchived, taskFilters, isManager });
  } catch (reason) {
    localStorage.removeItem(tokenKey);
    showLogin(reason.message);
  }
}

function bindHomeEvents(user, state) {
  const { showArchived, taskFilters, isManager } = state;
  document.querySelector('#logout').onclick = async () => {
    await api('/api/auth/logout', { method: 'POST' });
    localStorage.removeItem(tokenKey);
    showLogin();
  };
  document.querySelector('#task-search').onsubmit = event => {
    event.preventDefault();
    showHome(user, { showArchived, searchFilters: homeFilters(new FormData(event.currentTarget)) });
  };
  document.querySelectorAll('.task-page').forEach(button => {
    button.onclick = () => showHome(user, { showArchived, searchFilters: { ...taskFilters, page: Number(button.dataset.taskPage) } });
  });
  document.querySelectorAll('.open-project').forEach(button => {
    button.onclick = () => showProjectDetail(user, button.dataset.projectId, { showArchived });
  });
  document.querySelector('#export-tasks').onclick = async () => {
    try {
      await downloadTaskExport(taskFilters);
    } catch (reason) {
      showHome(user, { error: reason.message, showArchived, searchFilters: taskFilters });
    }
  };
  const bulkForm = document.querySelector('#bulk-update');
  if (bulkForm) {
    bulkForm.querySelector('[name="action"]').onchange = () => updateBulkInputs(bulkForm);
    bulkForm.onsubmit = async event => {
      event.preventDefault();
      const taskIds = [...document.querySelectorAll('input[name="taskIds"]:checked')].map(input => Number(input.value));
      const payload = bulkPayload(new FormData(bulkForm), taskIds);
      if (!payload.task_ids.length) {
        showHome(user, { error: 'Select at least one task for the bulk action.', showArchived, searchFilters: taskFilters });
        return;
      }
      try {
        const bulkResult = await api('/api/tasks/bulk', { method: 'POST', body: JSON.stringify(payload) });
        showHome(user, { showArchived, searchFilters: taskFilters, bulkResult });
      } catch (reason) {
        showHome(user, { error: reason.message, showArchived, searchFilters: taskFilters });
      }
    };
  }
  if (isManager) bindManagerControls(user, { showArchived, taskFilters });
}

function bindManagerControls(user, state) {
  const { showArchived, taskFilters } = state;
  document.querySelector('#toggle-archived').onclick = () => showHome(user, { showArchived: !showArchived, searchFilters: taskFilters });
  document.querySelector('#create-project').onsubmit = async event => {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    try {
      await api('/api/projects', { method: 'POST', body: JSON.stringify({ key: values.get('key'), name: values.get('name'), description: values.get('description'), owner_id: Number(values.get('ownerId')), member_ids: values.getAll('memberIds').map(Number) }) });
      showHome(user, { showArchived, searchFilters: taskFilters });
    } catch (reason) {
      showHome(user, { error: reason.message, showArchived, searchFilters: taskFilters });
    }
  };
  document.querySelectorAll('.edit-project-form').forEach(form => {
    form.onsubmit = async event => {
      event.preventDefault();
      const values = new FormData(form);
      try {
        await api(`/api/projects/${form.dataset.projectId}`, { method: 'PUT', body: JSON.stringify({ key: values.get('key'), name: values.get('name'), description: values.get('description'), owner_id: Number(values.get('ownerId')) }) });
        showHome(user, { showArchived, searchFilters: taskFilters });
      } catch (reason) {
        showHome(user, { error: reason.message, showArchived, searchFilters: taskFilters });
      }
    };
  });
  document.querySelectorAll('.members-form').forEach(form => {
    form.onsubmit = async event => {
      event.preventDefault();
      try {
        await api(`/api/projects/${form.dataset.projectId}/members`, { method: 'PUT', body: JSON.stringify({ member_ids: new FormData(form).getAll('memberIds').map(Number) }) });
        showHome(user, { showArchived, searchFilters: taskFilters });
      } catch (reason) {
        showHome(user, { error: reason.message, showArchived, searchFilters: taskFilters });
      }
    };
  });
  document.querySelectorAll('.archive, .restore').forEach(button => {
    button.onclick = async () => {
      const action = button.classList.contains('archive') ? 'archive' : 'restore';
      try {
        await api(`/api/projects/${button.dataset.projectId}/${action}`, { method: 'POST' });
        showHome(user, { showArchived, searchFilters: taskFilters });
      } catch (reason) {
        showHome(user, { error: reason.message, showArchived, searchFilters: taskFilters });
      }
    };
  });
}

(async () => {
  try {
    showHome(await api('/api/auth/me'));
  } catch {
    showLogin();
  }
})();
