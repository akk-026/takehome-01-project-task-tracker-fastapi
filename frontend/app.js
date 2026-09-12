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

function showHome(user) {
  root.innerHTML = `<div class="brand">✦ NORTHSTAR</div><h1>Welcome, ${user.name.split(' ')[0]}.</h1><span class="role">${user.role === 'MANAGER' ? 'Manager' : 'Member'}</span><p>Your identity and role are read from the FastAPI server. Project controls will be added in the next feature.</p><button id="logout">Sign out</button>`;
  document.querySelector('#logout').onclick = async () => { await api('/api/auth/logout', { method: 'POST' }); localStorage.removeItem(tokenKey); showLogin(); };
}

(async () => { try { showHome(await api('/api/auth/me')); } catch { showLogin(); } })();
