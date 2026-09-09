const statusBox = document.getElementById('statusBox');
const configForm = document.getElementById('configForm');
const runBtn = document.getElementById('runBtn');
const reprocessBtn = document.getElementById('reprocessBtn');

// ── Config ──────────────────────────────────────────────
async function loadConfig() {
  const res = await fetch('/api/config');
  const data = await res.json();
  document.getElementById('groupName').value = data.whatsapp_group_name || '';
  document.getElementById('dryRun').value = data.dry_run ? 'true' : 'false';
  document.getElementById('modelName').value = data.llm_model || 'mistral-small-latest';
}

configForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  statusBox.textContent = 'Saving...';
  const res = await fetch('/api/config', { method: 'POST', body: new FormData(configForm) });
  const result = await res.json();
  statusBox.textContent = JSON.stringify(result, null, 2);
});

// ── Run pipeline ─────────────────────────────────────────
runBtn.addEventListener('click', async () => {
  statusBox.textContent = 'Opening WhatsApp and extracting tasks...';
  runBtn.disabled = true;
  try {
    const res = await fetch('/api/run', { method: 'POST' });
    const result = await res.json();
    statusBox.textContent = JSON.stringify(result, null, 2);
    loadTasks();
    loadMessages();
  } catch (err) {
    statusBox.textContent = 'Error: ' + err.message;
  } finally {
    runBtn.disabled = false;
  }
});

// ── Reprocess from DB ────────────────────────────────────
reprocessBtn.addEventListener('click', async () => {
  statusBox.textContent = 'Reprocessing messages from DB (no WhatsApp needed)...';
  reprocessBtn.disabled = true;
  try {
    const res = await fetch('/api/reprocess', { method: 'POST' });
    const result = await res.json();
    if (res.status === 429) {
      statusBox.textContent = '⚠️ Mistral rate limit. Wait a few minutes and try again.\n\n' + JSON.stringify(result, null, 2);
    } else {
      statusBox.textContent = JSON.stringify(result, null, 2);
      loadTasks();
    }
  } catch (err) {
    statusBox.textContent = 'Error: ' + err.message;
  } finally {
    reprocessBtn.disabled = false;
  }
});

// ── Tab switching ─────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).style.display = 'block';
  });
});

// ── Tasks table ───────────────────────────────────────────
async function loadTasks() {
  const res = await fetch('/api/db/tasks');
  const data = await res.json();
  document.getElementById('tasksCount').textContent = data.count + ' tasks';
  const tbody = document.getElementById('tasksBody');
  tbody.innerHTML = '';
  if (!data.tasks.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#888">No tasks yet</td></tr>';
    return;
  }
  data.tasks.forEach(t => {
    const tr = document.createElement('tr');
    const statusClass = {
      completed: 'badge-green', in_progress: 'badge-blue',
      open: 'badge-gray', blocked: 'badge-red', review: 'badge-yellow'
    }[t.status] || 'badge-gray';
    const priorityClass = {
      urgent: 'badge-red', high: 'badge-orange',
      medium: 'badge-blue', low: 'badge-gray'
    }[t.priority] || 'badge-gray';
    tr.innerHTML = `
      <td><strong>${esc(t.assignee || '—')}</strong></td>
      <td class="cell-task">${esc(t.task || '—')}</td>
      <td><span class="badge ${statusClass}">${esc(t.status || '—')}</span></td>
      <td><span class="badge ${priorityClass}">${esc(t.priority || '—')}</span></td>
      <td>${esc(t.deadline || '—')}</td>
      <td>${esc(t.source_sender || '—')}</td>
      <td>${esc(t.message_timestamp || '—')}</td>
      <td>${t.confidence ? (t.confidence * 100).toFixed(0) + '%' : '—'}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ── Messages table ────────────────────────────────────────
async function loadMessages() {
  const res = await fetch('/api/db/messages');
  const data = await res.json();
  document.getElementById('msgsCount').textContent = data.count + ' messages';
  const tbody = document.getElementById('msgsBody');
  tbody.innerHTML = '';
  if (!data.messages.length) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#888">No messages yet</td></tr>';
    return;
  }
  data.messages.forEach(m => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${esc(m.sender || '—')}</strong></td>
      <td class="cell-task">${esc(m.message_text_normalized || '—')}</td>
      <td>${esc(m.message_timestamp || '—')}</td>
      <td>${esc((m.processed_at || '').replace('T', ' '))}</td>
    `;
    tbody.appendChild(tr);
  });
}

function esc(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

document.getElementById('refreshTasksBtn').addEventListener('click', loadTasks);
document.getElementById('refreshMsgsBtn').addEventListener('click', loadMessages);

// ── Init ──────────────────────────────────────────────────
loadConfig();
loadTasks();
loadMessages();
