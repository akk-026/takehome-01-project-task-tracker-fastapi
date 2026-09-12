const root = document.querySelector('#app');
const tokenKey = 'northstar-token';

async function api(path, options = {}) {
  const token = localStorage.getItem(tokenKey);
  const response = await fetch(path, {
    ...options,
    headers: { 'content-type': 'application/json', ...(token ? { authorization: `Bearer ${token}` } : {}) }
  });
  const body = response.status === 204 ? null : await response.json();
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

function projectCard(project, isManager, users) {
  const memberNames = project.members.map(member => escapeHtml(member.name)).join(', ') || 'No members';
  const controls = isManager ? `<details><summary>Manage members</summary><form class="members-form" data-project-id="${project.id}">${memberChoices(users, project.members.map(member => member.id))}<button>Save members</button></form><button class="archive" data-project-id="${project.id}" ${project.archived ? 'disabled' : ''}>${project.archived ? 'Archived' : 'Archive project'}</button></details>` : '';
  return `<article class="project"><div><span class="project-key">${escapeHtml(project.key)}</span>${project.archived ? '<span class="archived">Archived</span>' : ''}</div><h2>${escapeHtml(project.name)}</h2><p>${escapeHtml(project.description || 'No description yet.')}</p><small><b>Owner:</b> ${escapeHtml(project.owner.name)} · <b>Members:</b> ${memberNames}</small>${controls}</article>`;
}

async function showHome(user, error = '') {
  try {
    const isManager = user.role === 'MANAGER';
    const [projects, users] = await Promise.all([
      api('/api/projects'),
      isManager ? api('/api/users') : Promise.resolve([])
    ]);
    const createProject = isManager ? `<section class="panel"><h2>Create project</h2><form id="create-project"><label>Key</label><input name="key" maxlength="12" placeholder="OPS" required><label>Name</label><input name="name" maxlength="160" required><label>Description</label><input name="description" maxlength="2000"><label>Owner</label><select name="ownerId">${users.map(person => `<option value="${person.id}">${escapeHtml(person.name)}</option>`).join('')}</select><fieldset><legend>Project members</legend>${memberChoices(users, [])}</fieldset><button>Create project</button></form></section>` : '<p class="hint">You only see projects where you are a member.</p>';
    root.innerHTML = `<div class="topbar"><div><div class="brand">✦ NORTHSTAR</div><h1>Welcome, ${escapeHtml(user.name.split(' ')[0])}.</h1><span class="role">${isManager ? 'Manager' : 'Member'}</span></div><button id="logout" class="secondary">Sign out</button></div>${error ? `<div class="error">${escapeHtml(error)}</div>` : ''}${createProject}<section><h2>${isManager ? 'All active projects' : 'Your projects'}</h2><div class="projects">${projects.length ? projects.map(project => projectCard(project, isManager, users)).join('') : '<p class="hint">No active projects yet.</p>'}</div></section>`;
    document.querySelector('#logout').onclick = async () => { await api('/api/auth/logout', { method: 'POST' }); localStorage.removeItem(tokenKey); showLogin(); };
    if (isManager) bindManagerControls(user);
  } catch (reason) {
    localStorage.removeItem(tokenKey);
    showLogin(reason.message);
  }
}

function bindManagerControls(user) {
  document.querySelector('#create-project').onsubmit = async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    try {
      await api('/api/projects', { method: 'POST', body: JSON.stringify({ key: values.get('key'), name: values.get('name'), description: values.get('description'), owner_id: Number(values.get('ownerId')), member_ids: values.getAll('memberIds').map(Number) }) });
      showHome(user);
    } catch (reason) { showHome(user, reason.message); }
  };
  document.querySelectorAll('.members-form').forEach(form => {
    form.onsubmit = async event => {
      event.preventDefault();
      const values = new FormData(form);
      try {
        await api(`/api/projects/${form.dataset.projectId}/members`, { method: 'PUT', body: JSON.stringify({ member_ids: values.getAll('memberIds').map(Number) }) });
        showHome(user);
      } catch (reason) { showHome(user, reason.message); }
    };
  });
  document.querySelectorAll('.archive').forEach(button => {
    button.onclick = async () => {
      try {
        await api(`/api/projects/${button.dataset.projectId}/archive`, { method: 'POST' });
        showHome(user);
      } catch (reason) { showHome(user, reason.message); }
    };
  });
}

(async () => { try { showHome(await api('/api/auth/me')); } catch { showLogin(); } })();
