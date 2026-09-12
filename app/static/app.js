// ── DOM Elements ──────────────────────────────────────
const statusBox = document.getElementById('statusBox');
const configForm = document.getElementById('configForm');
const runBtn = document.getElementById('runBtn');
const reprocessBtn = document.getElementById('reprocessBtn');
const downloadExcelBtn = document.getElementById('downloadExcelBtn');
const refreshAllBtn = document.getElementById('refreshAllBtn');
const testConfigBtn = document.getElementById('testConfigBtn');
const clearStatusBtn = document.getElementById('clearStatusBtn');
const loadingModal = document.getElementById('loadingModal');
const loadingText = document.getElementById('loadingText');

let allTasks = [];
let allMessages = [];
let lastRunTime = null;

// ── Config Management ─────────────────────────────────
async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    const data = await res.json();
    document.getElementById('groupName').value = data.whatsapp_group_name || '';
    document.getElementById('dryRun').value = data.dry_run ? 'true' : 'false';
    document.getElementById('modelName').value = data.llm_model || 'mistral-small-latest';
    document.getElementById('statGroup').textContent = data.whatsapp_group_name || 'Not Set';
    document.getElementById('statGroupDetail').textContent = 
      data.whatsapp_group_name ? 'Configured and ready' : 'Set group name to enable';
    updateStatus('✅ Configuration loaded', 'info');
  } catch (err) {
    console.error('Failed to load config:', err);
    updateStatus(`❌ Failed to load config: ${err.message}`, 'error');
  }
}

configForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  updateStatus('💾 Saving configuration...', 'info');
  showLoading(true, 'Saving...');
  try {
    const res = await fetch('/api/config', { method: 'POST', body: new FormData(configForm) });
    const result = await res.json();
    updateStatus(`✅ Configuration saved successfully!\nGroup: ${result.group_name}\nDry Run: ${result.dry_run}`, 'success');
    document.getElementById('statGroup').textContent = result.group_name || '—';
    await loadConfig();
  } catch (err) {
    updateStatus(`❌ Error saving config: ${err.message}`, 'error');
  } finally {
    showLoading(false);
  }
});

testConfigBtn.addEventListener('click', async () => {
  updateStatus('🧪 Testing connection to LLM...', 'info');
  showLoading(true, 'Testing connection...');
  try {
    const res = await fetch('/api/db/messages');
    if (res.ok) {
      updateStatus('✅ Connection successful! System is ready.', 'success');
    } else {
      updateStatus('⚠️ Connection issue. Check configuration.', 'warning');
    }
  } catch (err) {
    updateStatus(`❌ Connection failed: ${err.message}`, 'error');
  } finally {
    showLoading(false);
  }
});

// ── Pipeline Execution ────────────────────────────────
runBtn.addEventListener('click', async () => {
  if (!document.getElementById('groupName').value.trim()) {
    updateStatus('❌ Error: WhatsApp group name is required!\nPlease configure the group name first.', 'error');
    return;
  }
  
  updateStatus('🔄 Opening WhatsApp browser...\nThis may take 2-5 minutes depending on message volume.', 'info');
  showLoading(true, 'Opening WhatsApp...');
  runBtn.disabled = true;
  
  try {
    const res = await fetch('/api/run', { method: 'POST' });
    const result = await res.json();
    
    if (result.status === 'completed') {
      lastRunTime = new Date().toLocaleString();
      document.getElementById('statLastRun').textContent = lastRunTime;
      document.getElementById('statLastRunDetail').textContent = 'Just now';
      
      updateStatus(
        `✅ Pipeline completed successfully!\n\n` +
        `📦 Tasks extracted: ${result.task_count}\n` +
        `💬 Messages collected: ${result.messages_seen}\n` +
        `⏱️ Completed at: ${lastRunTime}`,
        'success'
      );
      
      setTimeout(() => { 
        loadTasks(); 
        loadMessages(); 
      }, 1000);
    } else {
      updateStatus(`❌ Pipeline failed: ${result.detail || 'Unknown error'}`, 'error');
    }
  } catch (err) {
    updateStatus(`❌ Error: ${err.message}`, 'error');
  } finally {
    runBtn.disabled = false;
    showLoading(false);
  }
});

reprocessBtn.addEventListener('click', async () => {
  updateStatus('🔄 Reprocessing messages from database...\nNo WhatsApp browser needed.', 'info');
  showLoading(true, 'Reprocessing...');
  reprocessBtn.disabled = true;
  
  try {
    const res = await fetch('/api/reprocess', { method: 'POST' });
    const result = await res.json();
    
    if (result.status === 'completed') {
      lastRunTime = new Date().toLocaleString();
      document.getElementById('statLastRun').textContent = lastRunTime;
      
      updateStatus(
        `✅ Reprocessing completed!\n\n` +
        `📦 Tasks extracted: ${result.task_count}\n` +
        `💬 Messages processed: ${result.messages_seen}\n` +
        `📝 Note: ${result.note}`,
        'success'
      );
      
      setTimeout(() => { loadTasks(); loadMessages(); }, 500);
    } else if (result.status === 'rate_limited') {
      updateStatus(
        `⚠️ Rate limit reached!\n\nWait a few minutes before trying again.\n\n${result.detail}`,
        'warning'
      );
    } else {
      updateStatus(`❌ Error: ${result.detail || 'Unknown error'}`, 'error');
    }
  } catch (err) {
    updateStatus(`❌ Error: ${err.message}`, 'error');
  } finally {
    reprocessBtn.disabled = false;
    showLoading(false);
  }
});

downloadExcelBtn.addEventListener('click', () => {
  const link = document.createElement('a');
  link.href = '/data/tasks.xlsx';
  link.download = `tasks_export_${new Date().toISOString().split('T')[0]}.xlsx`;
  link.click();
  updateStatus('✅ Excel file downloaded successfully!', 'success');
});

refreshAllBtn.addEventListener('click', async () => {
  updateStatus('🔃 Refreshing all data...', 'info');
  showLoading(true, 'Refreshing...');
  try {
    await loadConfig();
    await loadTasks();
    await loadMessages();
    updateStatus('✅ All data refreshed successfully!', 'success');
  } catch (err) {
    updateStatus(`❌ Refresh failed: ${err.message}`, 'error');
  } finally {
    showLoading(false);
  }
});

clearStatusBtn.addEventListener('click', () => {
  statusBox.textContent = 'Status cleared.';
  statusBox.style.color = '#94a3b8';
});

// ── Tab Switching ─────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
    btn.classList.add('active');
    const tabName = btn.dataset.tab;
    document.getElementById('tab-' + tabName).style.display = 'block';
    if (tabName === 'tasks') loadTasks();
    if (tabName === 'messages') loadMessages();
  });
});

// ── Tasks Management ──────────────────────────────────
async function loadTasks() {
  try {
    const res = await fetch('/api/db/tasks');
    const data = await res.json();
    allTasks = data.tasks || [];
    document.getElementById('tasksCount').textContent = `${data.count} tasks`;
    document.getElementById('statTasks').textContent = data.count;
    document.getElementById('statTasksDetail').textContent = 
      data.count > 0 ? `Last updated: ${new Date().toLocaleTimeString()}` : 'No tasks collected yet';
    renderTasks(allTasks);
    populateTaskFilter();
  } catch (err) {
    console.error('Failed to load tasks:', err);
    updateStatus(`❌ Failed to load tasks: ${err.message}`, 'error');
  }
}

function renderTasks(tasks) {
  const tbody = document.getElementById('tasksBody');
  tbody.innerHTML = '';
  
  if (!tasks.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;color:#888">No tasks yet. Run extraction to populate.</td></tr>';
    return;
  }
  
  tasks.forEach(t => {
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
      <td><small>${esc(t.source_sender || '—')}</small></td>
      <td><small>${esc((t.message_timestamp || '—').substring(0, 16))}</small></td>
      <td>${t.confidence ? (t.confidence * 100).toFixed(0) + '%' : '—'}</td>
    `;
    tbody.appendChild(tr);
  });
}

function populateTaskFilter() {
  const uniqueStatuses = [...new Set(allTasks.map(t => t.status).filter(Boolean))];
}

document.getElementById('taskSearch').addEventListener('input', (e) => {
  const search = e.target.value.toLowerCase();
  const filtered = allTasks.filter(t => 
    (t.assignee || '').toLowerCase().includes(search) ||
    (t.task || '').toLowerCase().includes(search)
  );
  renderTasks(filtered);
});

document.getElementById('taskFilter').addEventListener('change', (e) => {
  const status = e.target.value;
  const filtered = status ? allTasks.filter(t => t.status === status) : allTasks;
  renderTasks(filtered);
});

document.getElementById('refreshTasksBtn').addEventListener('click', loadTasks);

// ── Messages Management ───────────────────────────────
async function loadMessages() {
  try {
    const res = await fetch('/api/db/messages');
    const data = await res.json();
    allMessages = data.messages || [];
    document.getElementById('msgsCount').textContent = `${data.count} messages`;
    document.getElementById('statMessages').textContent = data.count;
    document.getElementById('statMessagesDetail').textContent = 
      data.count > 0 ? `Last updated: ${new Date().toLocaleTimeString()}` : 'No messages collected yet';
    renderMessages(allMessages);
    populateMessageFilter();
  } catch (err) {
    console.error('Failed to load messages:', err);
    updateStatus(`❌ Failed to load messages: ${err.message}`, 'error');
  }
}

function renderMessages(messages) {
  const tbody = document.getElementById('msgsBody');
  tbody.innerHTML = '';
  
  if (!messages.length) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:20px;color:#888">No messages yet. Run extraction to populate.</td></tr>';
    return;
  }
  
  messages.forEach(m => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${esc(m.sender || '—')}</strong></td>
      <td class="cell-task">${esc(m.message_text_normalized || '—')}</td>
      <td><small>${esc((m.message_timestamp || '—').substring(0, 16))}</small></td>
      <td><small>${esc((m.processed_at || '—').replace('T', ' ').substring(0, 16))}</small></td>
    `;
    tbody.appendChild(tr);
  });
}

function populateMessageFilter() {
  const uniqueSenders = [...new Set(allMessages.map(m => m.sender).filter(Boolean))];
  const filterSelect = document.getElementById('msgFilter');
  const currentValue = filterSelect.value;
  filterSelect.innerHTML = '<option value="">All Senders</option>';
  uniqueSenders.forEach(sender => {
    const opt = document.createElement('option');
    opt.value = sender;
    opt.textContent = sender;
    filterSelect.appendChild(opt);
  });
  filterSelect.value = currentValue;
}

document.getElementById('msgSearch').addEventListener('input', (e) => {
  const search = e.target.value.toLowerCase();
  const filtered = allMessages.filter(m => 
    (m.sender || '').toLowerCase().includes(search) ||
    (m.message_text_normalized || '').toLowerCase().includes(search)
  );
  renderMessages(filtered);
});

document.getElementById('msgFilter').addEventListener('change', (e) => {
  const sender = e.target.value;
  const filtered = sender ? allMessages.filter(m => m.sender === sender) : allMessages;
  renderMessages(filtered);
});

document.getElementById('refreshMsgsBtn').addEventListener('click', loadMessages);

// ── Utilities ─────────────────────────────────────────
function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function updateStatus(message, type = 'info') {
  statusBox.textContent = message;
  statusBox.style.color = type === 'success' ? '#86efac' 
    : type === 'error' ? '#fca5a5' 
    : type === 'warning' ? '#fde047' 
    : '#94a3b8';
}

function showLoading(show, text = 'Processing...') {
  loadingModal.style.display = show ? 'flex' : 'none';
  if (show) loadingText.textContent = text;
}

function updateFooter() {
  document.getElementById('footerTime').textContent = new Date().toLocaleString();
  document.getElementById('serverTime').textContent = new Date().toLocaleTimeString();
}

// ── Initialization ────────────────────────────────────
async function init() {
  updateStatus('⏳ Loading system...', 'info');
  showLoading(true, 'Initializing...');
  
  try {
    await loadConfig();
    await loadTasks();
    await loadMessages();
    updateStatus('✅ System ready. Configure WhatsApp group and click "Run Task Extraction" to start.', 'success');
    updateFooter();
    setInterval(updateFooter, 60000);
  } catch (err) {
    updateStatus(`❌ Initialization failed: ${err.message}`, 'error');
  } finally {
    showLoading(false);
  }
}

// Start the app
window.addEventListener('load', init);
