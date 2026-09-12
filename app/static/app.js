const statusBox = document.getElementById('statusBox');
const configForm = document.getElementById('configForm');
const runBtn = document.getElementById('runBtn');
const reprocessBtn = document.getElementById('reprocessBtn');
const downloadExcelBtn = document.getElementById('downloadExcelBtn');

let lastRunTime = null;

// ── Config ──────────────────────────────────────────────
async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    const data = await res.json();
    document.getElementById('groupName').value = data.whatsapp_group_name || '';
    document.getElementById('dryRun').value = data.dry_run ? 'true' : 'false';
    document.getElementById('modelName').value = data.llm_model || 'mistral-small-latest';
    document.getElementById('statGroup').textContent = data.whatsapp_group_name || 'Not configured';
  } catch (err) {
    console.error('Failed to load config:', err);
  }
}

configForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  updateStatus('Saving configuration...', 'info');
  try {
    const res = await fetch('/api/config', { method: 'POST', body: new FormData(configForm) });
    const result = await res.json();
    updateStatus(`✅ Configuration saved!\n${JSON.stringify(result, null, 2)}`, 'success');
    document.getElementById('statGroup').textContent = result.group_name || '—';
    loadConfig();
  } catch (err) {
    updateStatus(`❌ Error: ${err.message}`, 'error');
  }
});

// ── Run pipeline ─────────────────────────────────────────
runBtn.addEventListener('click', async () => {
  updateStatus('🔄 Opening WhatsApp and collecting messages...\nThis may take a few minutes...', 'info');
  runBtn.disabled = true;
  try {
    const res = await fetch('/api/run', { method: 'POST' });
    const result = await res.json();
    lastRunTime = new Date().toLocaleString();
    document.getElementById('statLastRun').textContent = lastRunTime;
    updateStatus(`✅ Pipeline completed!\n${JSON.stringify(result, null, 2)}`, 'success');
    setTimeout(() => { loadTasks(); loadMessages(); }, 1000);
  } catch (err) {
    updateStatus(`❌ Error: ${err.message}`, 'error');
  } finally {
    runBtn.disabled = false;
  }
});

// ── Reprocess from DB ────────────────────────────────────
reprocessBtn.addEventListener('click', async () => {
  updateStatus('🔄 Reprocessing messages from DB (no WhatsApp needed)...', 'info');
  reprocessBtn.disabled = true;
  try {
    const res = await fetch('/api/reprocess', { method: 'POST' });
    const result = await res.json();
    if (res.status === 429) {
      updateStatus(`⚠️ Rate limit exceeded. Wait a few minutes and try again.\n${JSON.stringify(result, null, 2)}`, 'warning');
    } else {
      lastRunTime = new Date().toLocaleString();
      document.getElementById('statLastRun').textContent = lastRunTime;
      updateStatus(`✅ Reprocessing completed!\n${JSON.stringify(result, null, 2)}`, 'success');
      setTimeout(() => { loadTasks(); loadMessages(); }, 500);
    }
  } catch (err) {
    updateStatus(`❌ Error: ${err.message}`, 'error');
  } finally {
    reprocessBtn.disabled = false;
  }
});

// ── Download Excel ──────────────────────────────────────
downloadExcelBtn.addEventListener('click', () => {
  const link = document.createElement('a');
  link.href = '/static/tasks_export.xlsx';
  link.download = `tasks_export_${new Date().toISOString().split('T')[0]}.xlsx`;
  link.click();
});

// ── Tab switching ─────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).style.display = 'block';
    if (btn.dataset.tab === 'tasks') loadTasks();
    if (btn.dataset.tab === 'messages') loadMessages();
  });
});

// ── Tasks table ───────────────────────────────────────────
async function loadTasks() {
  try {
    const res = await fetch('/api/db/tasks');
    const data = await res.json();
    document.getElementById('tasksCount').textContent = `${data.count} tasks`;
    document.getElementById('statTasks').textContent = data.count;
    const tbody = document.getElementById('tasksBody');
    tbody.innerHTML = '';
    if (!data.tasks.length) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;color:#888">No tasks yet. Run pipeline to collect tasks.</td></tr>';
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
  } catch (err) {
    console.error('Failed to load tasks:', err);
  }
}

// ── Messages table ────────────────────────────────────────
async function loadMessages() {
  try {
    const res = await fetch('/api/db/messages');
    const data = await res.json();
    document.getElementById('msgsCount').textContent = `${data.count} messages`;
    document.getElementById('statMessages').textContent = data.count;
    const tbody = document.getElementById('msgsBody');
    tbody.innerHTML = '';
    if (!data.messages.length) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:20px;color:#888">No messages yet. Run pipeline to collect messages.</td></tr>';
      return;
    }
    data.messages.forEach(m => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${esc(m.sender || '—')}</strong></td>
        <td class="cell-task">${esc(m.message_text_normalized || '—')}</td>
        <td>${esc(m.message_timestamp || '—')}</td>
        <td>${esc((m.processed_at || '').replace('T', ' ').substring(0, 19))}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Failed to load messages:', err);
  }
}

// ── Utilities ────────────────────────────────────────────
function esc(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function updateStatus(message, type = 'info') {
  statusBox.textContent = message;
  statusBox.style.color = type === 'success' ? '#86efac' : type === 'error' ? '#fca5a5' : type === 'warning' ? '#fde047' : '#94a3b8';
}

function updateFooter() {
  document.getElementById('footerTime').textContent = new Date().toLocaleString();
}

// ── Event Listeners ──────────────────────────────────────
document.getElementById('refreshTasksBtn').addEventListener('click', loadTasks);
document.getElementById('refreshMsgsBtn').addEventListener('click', loadMessages);

// ── Init ──────────────────────────────────────────────────
loadConfig();
loadTasks();
loadMessages();
updateFooter();
setInterval(updateFooter, 60000);
