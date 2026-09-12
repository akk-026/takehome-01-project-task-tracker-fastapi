const root = document.querySelector('#app');
const tokenKey = 'northstar-token';
const apiBaseUrl = window.location.port === '8000' ? '' : 'http://localhost:8000';

async function api(path, options = {}) {
  const token = localStorage.getItem(tokenKey);
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers: { 'content-type': 'application/json', ...(token ? { authorization: `Bearer ${token}` } : {}) }
  });
  const contentType = response.headers.get('content-type') || '';
  const body = response.status === 204 ? null : contentType.includes('application/json')
    ? await response.json()
    : { detail: 'The app could not reach the FastAPI API. Start it on http://localhost:8000.' };
  if (!response.ok) throw new Error(body.detail || 'Request failed.');
  return body;
}

function showLogin(error = '') {
  root.innerHTML = `<div class="brand">✦ NORTHSTAR</div><h1>Make work visible.</h1><p>Sign in to the project tracker.</p><form id="login"><label>Email</label><input name="email" type="email" value="alice@northstar.test" required><label>Password</label><input name="password" type="password" value="manager123" required><button>Sign in</button></form>${error ? `<div class="error">${error}</div>` : ''}<div class="demo"><b>Demo accounts</b><br>Manager: alice@northstar.test / manager123<br>Member: dan@northstar.test / member123</div>`;
  document.querySelector('#login').onsubmit = async event => {
    event.preventDefault();
    try {
      const result = await api('/api/auth/login', { method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(event.currentTarget))) });
      localStorage.setItem(tokenKey, result.token);
      showHome(result.user);
    } catch (reason) { showLogin(reason.message); }
  };
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character]);
}

function memberChoices(users, selectedIds, name = 'memberIds') {
  return users.map(person => `<label class="member"><input type="checkbox" name="${name}" value="${person.id}" ${selectedIds.includes(person.id) ? 'checked' : ''}> ${escapeHtml(person.name)}</label>`).join('');
}

function taskChoices(tasks, selectedIds = [], currentTaskId = null) {
  const availableTasks = tasks.filter(task => task.id !== currentTaskId);
  return availableTasks.length
    ? availableTasks.map(task => `<label class="member"><input type="checkbox" name="blockerIds" value="${task.id}" ${selectedIds.includes(task.id) ? 'checked' : ''}> ${escapeHtml(task.title)}</label>`).join('')
    : '<p class="hint">No other tasks are available as blockers.</p>';
}

function statusLabel(status) {
  return status.split('_').map(word => word[0] + word.slice(1).toLowerCase()).join(' ');
}

function statusControls(task) {
  if (!task.available_statuses.length) return '<p class="hint">No status moves are available.</p>';
  return `<div class="status-actions">${task.available_statuses.map(nextStatus => `<button class="status-move secondary" data-task-id="${task.id}" data-status="${nextStatus}">Move to ${escapeHtml(statusLabel(nextStatus))}</button>`).join('')}</div>`;
}

function projectCard(project, isManager, users) {
  const memberNames = project.members.map(member => escapeHtml(member.name)).join(', ') || 'No members';
  const ownerOptions = users.map(person => `<option value="${person.id}" ${person.id === project.owner.id ? 'selected' : ''}>${escapeHtml(person.name)}</option>`).join('');
  const archiveControl = project.archived
    ? `<button class="restore" data-project-id="${project.id}">Restore project</button>`
    : `<button class="archive" data-project-id="${project.id}">Archive project</button>`;
  const controls = isManager ? `<details><summary>Manage project</summary><form class="edit-project-form" data-project-id="${project.id}"><label>Key</label><input name="key" maxlength="12" value="${escapeHtml(project.key)}" required><label>Name</label><input name="name" maxlength="160" value="${escapeHtml(project.name)}" required><label>Description</label><input name="description" maxlength="2000" value="${escapeHtml(project.description)}"><label>Owner</label><select name="ownerId">${ownerOptions}</select><button>Save project</button></form><form class="members-form" data-project-id="${project.id}"><fieldset><legend>Project members</legend>${memberChoices(users, project.members.map(member => member.id))}</fieldset><button>Save members</button></form>${archiveControl}</details>` : '';
  return `<article class="project"><div><span class="project-key">${escapeHtml(project.key)}</span>${project.archived ? '<span class="archived">Archived</span>' : ''}</div><h2>${escapeHtml(project.name)}</h2><p>${escapeHtml(project.description || 'No description yet.')}</p><small><b>Owner:</b> ${escapeHtml(project.owner.name)} · <b>Members:</b> ${memberNames}</small><button class="open-project secondary" data-project-id="${project.id}">Open project</button>${controls}</article>`;
}

function assignedTaskCard(task) {
  return `<article class="task assigned-task"><div class="task-heading"><div><span class="project-key">${escapeHtml(task.project_key)}</span><h3>${escapeHtml(task.title)}</h3></div><span class="task-status ${task.status.toLowerCase()}">${escapeHtml(statusLabel(task.status))}</span></div><p>${escapeHtml(task.project_name)}</p><small><b>Due:</b> ${task.due_date || 'No due date'}</small><button class="open-project secondary" data-project-id="${task.project_id}">Open project</button></article>`;
}

function taskCard(task, tasks, isManager, projectMembers) {
  const blockerNames = task.blocker_ids.map(id => tasks.find(candidate => candidate.id === id)?.title || `Task #${id}`).map(escapeHtml).join(', ');
  const assigneeNames = task.assignee_ids.map(id => projectMembers.find(member => member.id === id)?.name || `User #${id}`).map(escapeHtml).join(', ');
  const deleteControl = isManager ? `<button class="delete-task" data-task-id="${task.id}">Delete task</button>` : '';
  return `<article class="task"><div class="task-heading"><h3>${escapeHtml(task.title)}</h3><div class="task-badges"><span class="task-status ${task.status.toLowerCase()}">${escapeHtml(statusLabel(task.status))}</span><span class="priority ${task.priority.toLowerCase()}">${escapeHtml(task.priority)}</span></div></div><p>${escapeHtml(task.description || 'No description yet.')}</p><small><b>Due:</b> ${task.due_date || 'No due date'} · <b>Blocked by:</b> ${blockerNames || 'Nothing'} · <b>Assigned:</b> ${assigneeNames || 'Nobody'}</small>${statusControls(task)}<details><summary>Edit task</summary><form class="edit-task-form" data-task-id="${task.id}"><label>Title</label><input name="title" maxlength="300" value="${escapeHtml(task.title)}" required><label>Description</label><textarea name="description" maxlength="4000">${escapeHtml(task.description)}</textarea><label>Priority</label><select name="priority">${['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map(priority => `<option value="${priority}" ${priority === task.priority ? 'selected' : ''}>${priority}</option>`).join('')}</select><label>Due date</label><input name="dueDate" type="date" value="${task.due_date || ''}"><fieldset><legend>Blocked by</legend>${taskChoices(tasks, task.blocker_ids, task.id)}</fieldset><fieldset><legend>Assignees</legend>${memberChoices(projectMembers, task.assignee_ids, 'assigneeIds')}</fieldset><button>Save task</button></form>${deleteControl}</details></article>`;
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

async function showProjectDetail(user, projectId, showArchived = false, error = '') {
  try {
    const [project, tasks] = await Promise.all([
      api(`/api/projects/${projectId}`),
      api(`/api/tasks/projects/${projectId}`)
    ]);
    const isManager = user.role === 'MANAGER';
    root.innerHTML = `<div class="topbar"><div><div class="brand">✦ NORTHSTAR</div><h1>${escapeHtml(project.name)}</h1><p>${escapeHtml(project.description || 'No description yet.')}</p></div><button id="back-to-projects" class="secondary">← Projects</button></div>${error ? `<div class="error">${escapeHtml(error)}</div>` : ''}<section class="panel"><h2>Create task</h2><form id="create-task"><label>Title</label><input name="title" maxlength="300" required><label>Description</label><textarea name="description" maxlength="4000"></textarea><label>Priority</label><select name="priority"><option value="LOW">Low</option><option value="MEDIUM" selected>Medium</option><option value="HIGH">High</option><option value="CRITICAL">Critical</option></select><label>Due date</label><input name="dueDate" type="date"><fieldset><legend>Blocked by</legend>${taskChoices(tasks)}</fieldset><fieldset><legend>Assignees</legend>${memberChoices(project.members, [], 'assigneeIds')}</fieldset><button>Create task</button></form></section><section><h2>Tasks</h2><div class="tasks">${tasks.length ? tasks.map(task => taskCard(task, tasks, isManager, project.members)).join('') : '<p class="hint">No tasks in this project yet.</p>'}</div></section>`;
    document.querySelector('#back-to-projects').onclick = () => showHome(user, '', showArchived);
    document.querySelector('#create-task').onsubmit = async event => {
      event.preventDefault();
      try {
        await api(`/api/tasks/projects/${projectId}`, { method: 'POST', body: JSON.stringify(taskPayload(new FormData(event.currentTarget))) });
        showProjectDetail(user, projectId, showArchived);
      } catch (reason) { showProjectDetail(user, projectId, showArchived, reason.message); }
    };
    document.querySelectorAll('.edit-task-form').forEach(form => {
      form.onsubmit = async event => {
        event.preventDefault();
        try {
          await api(`/api/tasks/${form.dataset.taskId}`, { method: 'PUT', body: JSON.stringify(taskPayload(new FormData(form))) });
          showProjectDetail(user, projectId, showArchived);
        } catch (reason) { showProjectDetail(user, projectId, showArchived, reason.message); }
      };
    });
    document.querySelectorAll('.status-move').forEach(button => {
      button.onclick = async () => {
        try {
          await api(`/api/tasks/${button.dataset.taskId}/status`, { method: 'POST', body: JSON.stringify({ status: button.dataset.status }) });
          showProjectDetail(user, projectId, showArchived);
        } catch (reason) { showProjectDetail(user, projectId, showArchived, reason.message); }
      };
    });
    document.querySelectorAll('.delete-task').forEach(button => {
      button.onclick = async () => {
        try {
          await api(`/api/tasks/${button.dataset.taskId}`, { method: 'DELETE' });
          showProjectDetail(user, projectId, showArchived);
        } catch (reason) { showProjectDetail(user, projectId, showArchived, reason.message); }
      };
    });
  } catch (reason) {
    showHome(user, reason.message, showArchived);
  }
}

async function showHome(user, error = '', showArchived = false) {
  try {
    const isManager = user.role === 'MANAGER';
    const [projects, users, assignedTasks] = await Promise.all([
      api(isManager && showArchived ? '/api/projects?include_archived=true' : '/api/projects'),
      isManager ? api('/api/users') : Promise.resolve([]),
      api('/api/tasks/assigned')
    ]);
    const activeProjects = projects.filter(project => !project.archived);
    const archivedProjects = projects.filter(project => project.archived);
    const createProject = isManager ? `<section class="panel"><h2>Create project</h2><form id="create-project"><label>Key</label><input name="key" maxlength="12" placeholder="OPS" required><label>Name</label><input name="name" maxlength="160" required><label>Description</label><input name="description" maxlength="2000"><label>Owner</label><select name="ownerId">${users.map(person => `<option value="${person.id}">${escapeHtml(person.name)}</option>`).join('')}</select><fieldset><legend>Project members</legend>${memberChoices(users, [])}</fieldset><button>Create project</button></form></section>` : '<p class="hint">You only see projects where you are a member.</p>';
    const archiveToggle = isManager ? `<button id="toggle-archived" class="secondary">${showArchived ? 'Hide archived projects' : 'Show archived projects'}</button>` : '';
    const archivedSection = showArchived ? `<section><h2>Archived projects</h2><div class="projects">${archivedProjects.length ? archivedProjects.map(project => projectCard(project, true, users)).join('') : '<p class="hint">No archived projects.</p>'}</div></section>` : '';
    root.innerHTML = `<div class="topbar"><div><div class="brand">✦ NORTHSTAR</div><h1>Welcome, ${escapeHtml(user.name.split(' ')[0])}.</h1><span class="role">${isManager ? 'Manager' : 'Member'}</span></div><div class="header-actions">${archiveToggle}<button id="logout" class="secondary">Sign out</button></div></div>${error ? `<div class="error">${escapeHtml(error)}</div>` : ''}<section><h2>Assigned to you</h2><div class="tasks">${assignedTasks.length ? assignedTasks.map(assignedTaskCard).join('') : '<p class="hint">No tasks are assigned to you.</p>'}</div></section>${createProject}<section><h2>${isManager ? 'All active projects' : 'Your projects'}</h2><div class="projects">${activeProjects.length ? activeProjects.map(project => projectCard(project, isManager, users)).join('') : '<p class="hint">No active projects yet.</p>'}</div></section>${archivedSection}`;
    document.querySelector('#logout').onclick = async () => { await api('/api/auth/logout', { method: 'POST' }); localStorage.removeItem(tokenKey); showLogin(); };
    document.querySelectorAll('.open-project').forEach(button => {
      button.onclick = () => showProjectDetail(user, button.dataset.projectId, showArchived);
    });
    if (isManager) bindManagerControls(user, showArchived);
  } catch (reason) {
    localStorage.removeItem(tokenKey);
    showLogin(reason.message);
  }
}

function bindManagerControls(user, showArchived) {
  document.querySelector('#toggle-archived').onclick = () => showHome(user, '', !showArchived);
  document.querySelector('#create-project').onsubmit = async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    try {
      await api('/api/projects', { method: 'POST', body: JSON.stringify({ key: values.get('key'), name: values.get('name'), description: values.get('description'), owner_id: Number(values.get('ownerId')), member_ids: values.getAll('memberIds').map(Number) }) });
      showHome(user, '', showArchived);
    } catch (reason) { showHome(user, reason.message, showArchived); }
  };
  document.querySelectorAll('.edit-project-form').forEach(form => {
    form.onsubmit = async event => {
      event.preventDefault();
      const values = new FormData(form);
      try {
        await api(`/api/projects/${form.dataset.projectId}`, { method: 'PUT', body: JSON.stringify({ key: values.get('key'), name: values.get('name'), description: values.get('description'), owner_id: Number(values.get('ownerId')) }) });
        showHome(user, '', showArchived);
      } catch (reason) { showHome(user, reason.message, showArchived); }
    };
  });
  document.querySelectorAll('.members-form').forEach(form => {
    form.onsubmit = async event => {
      event.preventDefault();
      const values = new FormData(form);
      try {
        await api(`/api/projects/${form.dataset.projectId}/members`, { method: 'PUT', body: JSON.stringify({ member_ids: values.getAll('memberIds').map(Number) }) });
        showHome(user, '', showArchived);
      } catch (reason) { showHome(user, reason.message, showArchived); }
    };
  });
  document.querySelectorAll('.archive').forEach(button => {
    button.onclick = async () => {
      try {
        await api(`/api/projects/${button.dataset.projectId}/archive`, { method: 'POST' });
        showHome(user, '', showArchived);
      } catch (reason) { showHome(user, reason.message, showArchived); }
    };
  });
  document.querySelectorAll('.restore').forEach(button => {
    button.onclick = async () => {
      try {
        await api(`/api/projects/${button.dataset.projectId}/restore`, { method: 'POST' });
        showHome(user, '', showArchived);
      } catch (reason) { showHome(user, reason.message, showArchived); }
    };
  });
}

(async () => { try { showHome(await api('/api/auth/me')); } catch { showLogin(); } })();
