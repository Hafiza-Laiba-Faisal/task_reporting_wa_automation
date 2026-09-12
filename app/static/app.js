// ── LLM Provider metadata ─────────────────────────────────────────────────────
const LLM_PROVIDERS = {
  openrouter: {
    label:    "OpenRouter (Free Models)",
    keyLabel: "OpenRouter API Key",
    urlLabel: "Base URL",
    urlDefault: "https://openrouter.ai/api/v1",
    models: [
      { value: "nvidia/nemotron-3-super-120b-a12b:free", label: "NVIDIA Nemotron Super (Free)" },
      { value: "nvidia/nemotron-3-ultra-550b-a55b:free", label: "NVIDIA Nemotron Ultra (Free)" },
      { value: "google/gemma-4-31b-it:free",             label: "Google Gemma 4 31B (Free)" },
      { value: "meta-llama/llama-3.1-8b-instruct:free",  label: "Meta Llama 3.1 8B (Free)" },
      { value: "anthropic/claude-3-sonnet",              label: "Claude 3 Sonnet (Paid)" },
      { value: "openai/gpt-4-turbo",                     label: "GPT-4 Turbo (Paid)" },
    ],
  },
  nvidia: {
    label:    "NVIDIA NIM",
    keyLabel: "NVIDIA API Key",
    urlLabel: "Base URL",
    urlDefault: "https://integrate.api.nvidia.com/v1",
    models: [
      { value: "mistralai/mistral-large-2-instruct", label: "Mistral Large 2 (Instruct)" },
      { value: "meta/llama-3.1-70b-instruct",        label: "Llama 3.1 70B" },
      { value: "nvidia/nemotron-4-340b-instruct",    label: "Nemotron 4 340B" },
    ],
  },
  mistral: {
    label:    "Mistral",
    keyLabel: "Mistral API Key",
    urlLabel: "Base URL",
    urlDefault: "",
    models: [
      { value: "mistral-small-latest",  label: "Mistral Small (Fast)" },
      { value: "mistral-medium-latest", label: "Mistral Medium" },
      { value: "mistral-large-latest",  label: "Mistral Large (Accurate)" },
    ],
  },
  openai: {
    label:    "OpenAI",
    keyLabel: "OpenAI API Key",
    urlLabel: "Base URL",
    urlDefault: "",
    models: [
      { value: "gpt-4o-mini", label: "GPT-4o Mini (Cheap)" },
      { value: "gpt-4o",      label: "GPT-4o" },
      { value: "gpt-4-turbo", label: "GPT-4 Turbo" },
    ],
  },
  ollama: {
    label:    "Ollama (Local)",
    keyLabel: "API Key (not needed)",
    urlLabel: "Ollama Base URL",
    urlDefault: "http://localhost:11434",
    models: [
      { value: "mistral",          label: "Mistral 7B" },
      { value: "llama3",           label: "Llama 3 8B" },
      { value: "qwen2:0.5b",       label: "Qwen 2 0.5B (Tiny, Fast)" },
      { value: "neural-chat",      label: "Neural Chat" },
      { value: "phi3",             label: "Phi-3 Mini" },
    ],
  },
};

// ── DOM refs ──────────────────────────────────────────────────────────────────
const statusBox    = document.getElementById('statusBox');
const loadingModal = document.getElementById('loadingModal');
const loadingText  = document.getElementById('loadingText');

let allTasks    = [];
let allMessages = [];
let sheetsUrl   = '';

// ── Utilities ─────────────────────────────────────────────────────────────────
function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

function updateStatus(msg, type = 'info') {
  statusBox.textContent = msg;
  statusBox.style.color = type === 'success' ? '#86efac'
    : type === 'error'   ? '#fca5a5'
    : type === 'warning' ? '#fde047'
    : '#94a3b8';
}

function showLoading(show, text = 'Processing...') {
  loadingModal.style.display = show ? 'flex' : 'none';
  if (show) loadingText.textContent = text;
}

// ── Provider Selector ─────────────────────────────────────────────────────────
function onProviderChange() {
  const provider = document.getElementById('llmProvider').value;
  const meta     = LLM_PROVIDERS[provider] || LLM_PROVIDERS.openrouter;

  // Update model dropdown
  const modelSel = document.getElementById('llmModel');
  modelSel.innerHTML = '';
  meta.models.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m.value;
    opt.textContent = m.label;
    modelSel.appendChild(opt);
  });

  // Labels
  document.getElementById('apiKeyLabel').textContent  = meta.keyLabel;
  document.getElementById('baseUrlLabel').textContent = meta.urlLabel;
  document.getElementById('llmBaseUrl').placeholder   = meta.urlDefault || 'Default URL';
  document.getElementById('baseUrlHelp').textContent  =
    meta.urlDefault ? `Default: ${meta.urlDefault}` : 'Leave blank for default';

  // Hide API key for Ollama (not needed)
  document.getElementById('apiKeyGroup').style.display = provider === 'ollama' ? 'none' : '';
}

// ── Load Config ───────────────────────────────────────────────────────────────
async function loadConfig() {
  try {
    const res  = await fetch('/api/config');
    const data = await res.json();

    document.getElementById('groupName').value = data.whatsapp_group_name || '';
    document.getElementById('dryRun').value    = data.dry_run ? 'true' : 'false';

    const provider = data.llm_provider || 'openrouter';
    const provSel  = document.getElementById('llmProvider');
    if ([...provSel.options].some(o => o.value === provider)) {
      provSel.value = provider;
    }
    onProviderChange();

    // Set model if it exists in dropdown
    const modelMap = {
      openrouter: data.openrouter_model,
      nvidia:     data.nvidia_model,
      mistral:    data.mistral_model,
      ollama:     data.ollama_model,
      openai:     null,
    };
    const currentModel = modelMap[provider] || data.llm_model || '';
    const modelSel     = document.getElementById('llmModel');
    const found        = [...modelSel.options].some(o => o.value === currentModel);
    if (found) modelSel.value = currentModel;

    // Base URL
    const urlMap = {
      openrouter: data.openrouter_base_url,
      nvidia:     data.nvidia_base_url,
      ollama:     data.ollama_base_url,
    };
    document.getElementById('llmBaseUrl').value = urlMap[provider] || '';

    // Dashboard
    document.getElementById('statGroup').textContent       = data.whatsapp_group_name || 'Not Set';
    document.getElementById('statGroupDetail').textContent =
      data.whatsapp_group_name ? 'Configured ✅' : 'Set group name to enable';

  } catch (err) {
    updateStatus(`❌ Failed to load config: ${err.message}`, 'error');
  }
}

// ── Load Google Sheets Config ─────────────────────────────────────────────────
async function loadSheetsConfig() {
  try {
    const res  = await fetch('/api/google-sheets/config');
    const data = await res.json();
    const cb   = document.getElementById('gsEnabled');
    cb.checked = !!data.enabled;
    document.getElementById('gsEnabledLabel').textContent = data.enabled ? 'Enabled' : 'Disabled';
    document.getElementById('gsSheetId').value      = data.sheet_id || '';
    document.getElementById('gsCredentials').value  = data.credentials_path || '';
    document.getElementById('gsShareWith').value    = data.share_with || '';
    document.getElementById('gsSheetName').value    = data.sheet_name || 'Task Summary';
    if (data.sheet_id) {
      sheetsUrl = `https://docs.google.com/spreadsheets/d/${data.sheet_id}/edit`;
      showSheetLink(sheetsUrl);
    }
  } catch (err) {
    console.warn('Failed to load sheets config:', err);
  }
}

function showSheetLink(url) {
  if (!url) return;
  const box  = document.getElementById('gsSheetLinkBox');
  const link = document.getElementById('gsSheetLink');
  box.style.display  = '';
  link.href          = url;
  link.textContent   = 'Open Google Sheet ↗';
}

// ── General Config Form ───────────────────────────────────────────────────────
document.getElementById('configForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  showLoading(true, 'Saving...');
  try {
    const body = {
      whatsapp_group_name: document.getElementById('groupName').value.trim(),
      dry_run:             document.getElementById('dryRun').value,
    };
    const res    = await fetch('/api/config', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const result = await res.json();
    updateStatus(`✅ Configuration saved!\nGroup: ${result.group_name}`, 'success');
    document.getElementById('statGroup').textContent = result.group_name || '—';
  } catch (err) {
    updateStatus(`❌ Error: ${err.message}`, 'error');
  } finally {
    showLoading(false);
  }
});

// ── LLM Config Form ───────────────────────────────────────────────────────────
document.getElementById('llmForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  showLoading(true, 'Saving LLM config...');
  try {
    const provider = document.getElementById('llmProvider').value;
    const model    = document.getElementById('llmModel').value;
    const apiKey   = document.getElementById('llmApiKey').value.trim();
    const baseUrl  = document.getElementById('llmBaseUrl').value.trim();

    const body = { llm_provider: provider, llm_model: model };
    if (apiKey) {
      const keyFieldMap = {
        openrouter: 'openrouter_api_key',
        nvidia:     'nvidia_api_key',
        mistral:    'mistral_api_key',
        openai:     'openai_api_key',
      };
      if (keyFieldMap[provider]) body[keyFieldMap[provider]] = apiKey;
    }
    if (baseUrl) {
      const urlFieldMap = {
        openrouter: 'openrouter_base_url',
        nvidia:     'nvidia_base_url',
        ollama:     'ollama_base_url',
      };
      if (urlFieldMap[provider]) body[urlFieldMap[provider]] = baseUrl;
    }

    const res    = await fetch('/api/config', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const result = await res.json();
    updateStatus(
      `✅ LLM config saved!\nProvider: ${result.llm_provider}\nModel: ${result.llm_model}`,
      'success'
    );
  } catch (err) {
    updateStatus(`❌ Error: ${err.message}`, 'error');
  } finally {
    showLoading(false);
  }
});

// ── LLM Test ──────────────────────────────────────────────────────────────────
document.getElementById('testLlmBtn').addEventListener('click', async () => {
  updateStatus('🧪 Testing connection...', 'info');
  showLoading(true, 'Testing...');
  try {
    const res = await fetch('/api/db/tasks');
    if (res.ok) {
      updateStatus('✅ Backend is reachable and database is online!', 'success');
    } else {
      updateStatus('⚠️ Backend responded with an error.', 'warning');
    }
  } catch (err) {
    updateStatus(`❌ Connection failed: ${err.message}`, 'error');
  } finally {
    showLoading(false);
  }
});

// ── Google Sheets Form ────────────────────────────────────────────────────────
document.getElementById('gsEnabled').addEventListener('change', function () {
  document.getElementById('gsEnabledLabel').textContent = this.checked ? 'Enabled' : 'Disabled';
});

document.getElementById('googleSheetsForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  showLoading(true, 'Saving Google Sheets config...');
  try {
    const body = {
      enabled:          document.getElementById('gsEnabled').checked,
      sheet_id:         document.getElementById('gsSheetId').value.trim(),
      credentials_path: document.getElementById('gsCredentials').value.trim(),
      share_with:       document.getElementById('gsShareWith').value.trim(),
      sheet_name:       document.getElementById('gsSheetName').value.trim() || 'Task Summary',
    };
    const res    = await fetch('/api/google-sheets/config', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const result = await res.json();
    updateStatus(
      `✅ Google Sheets config saved!\nEnabled: ${result.enabled}\nSheet: ${result.sheet_id}`,
      'success'
    );
    if (body.sheet_id) {
      sheetsUrl = `https://docs.google.com/spreadsheets/d/${body.sheet_id}/edit`;
      showSheetLink(sheetsUrl);
    }
  } catch (err) {
    updateStatus(`❌ Error: ${err.message}`, 'error');
  } finally {
    showLoading(false);
  }
});

document.getElementById('testSheetsBtn').addEventListener('click', async () => {
  updateStatus('🧪 Testing Google Sheets connection...', 'info');
  showLoading(true, 'Testing Google Sheets...');
  try {
    const res    = await fetch('/api/google-sheets/test', { method: 'POST' });
    const result = await res.json();
    if (result.status === 'ok') {
      updateStatus(`✅ Google Sheets connected!\nSheet: "${result.title}"\n${result.url}`, 'success');
      showSheetLink(result.url);
    } else {
      updateStatus(`❌ Google Sheets error: ${result.detail}`, 'error');
    }
  } catch (err) {
    updateStatus(`❌ Test failed: ${err.message}`, 'error');
  } finally {
    showLoading(false);
  }
});

// ── Pipeline Actions ──────────────────────────────────────────────────────────
document.getElementById('runBtn').addEventListener('click', async () => {
  const group = document.getElementById('groupName').value.trim();
  if (!group) {
    updateStatus('❌ WhatsApp group name is required! Configure it above first.', 'error');
    return;
  }
  updateStatus('🔄 Opening WhatsApp browser...\nThis may take 2–5 minutes.', 'info');
  showLoading(true, 'Running pipeline...');
  document.getElementById('runBtn').disabled = true;
  try {
    const res    = await fetch('/api/run', { method: 'POST' });
    const result = await res.json();
    if (result.status === 'completed') {
      const now = new Date().toLocaleString();
      document.getElementById('statLastRun').textContent      = now;
      document.getElementById('statLastRunDetail').textContent = 'Just now ✅';
      let msg = `✅ Pipeline completed!\n\n📦 Tasks: ${result.task_count}\n💬 Messages: ${result.messages_seen}`;
      if (result.sheets_url) {
        msg += `\n🔗 Google Sheet updated: ${result.sheets_url}`;
        sheetsUrl = result.sheets_url;
        showSheetLink(sheetsUrl);
      }
      updateStatus(msg, 'success');
      setTimeout(() => { loadTasks(); loadMessages(); }, 800);
    } else {
      updateStatus(`❌ Pipeline failed: ${result.detail || 'Unknown error'}`, 'error');
    }
  } catch (err) {
    updateStatus(`❌ Error: ${err.message}`, 'error');
  } finally {
    document.getElementById('runBtn').disabled = false;
    showLoading(false);
  }
});

document.getElementById('reprocessBtn').addEventListener('click', async () => {
  updateStatus('🔄 Reprocessing messages from DB (no WhatsApp needed)...', 'info');
  showLoading(true, 'Reprocessing...');
  document.getElementById('reprocessBtn').disabled = true;
  try {
    const res    = await fetch('/api/reprocess', { method: 'POST' });
    const result = await res.json();
    if (result.status === 'completed') {
      const now = new Date().toLocaleString();
      document.getElementById('statLastRun').textContent = now;
      let msg = `✅ Reprocessing done!\n\n📦 Tasks: ${result.task_count}\n💬 Messages: ${result.messages_seen}\n${result.note}`;
      if (result.sheets_url) {
        msg += `\n🔗 Google Sheet updated: ${result.sheets_url}`;
        sheetsUrl = result.sheets_url;
        showSheetLink(sheetsUrl);
      }
      updateStatus(msg, 'success');
      setTimeout(() => { loadTasks(); loadMessages(); }, 500);
    } else if (result.status === 'rate_limited') {
      updateStatus(`⚠️ Rate limit reached. Wait a few minutes.\n${result.detail}`, 'warning');
    } else {
      updateStatus(`❌ Error: ${result.detail || 'Unknown error'}`, 'error');
    }
  } catch (err) {
    updateStatus(`❌ Error: ${err.message}`, 'error');
  } finally {
    document.getElementById('reprocessBtn').disabled = false;
    showLoading(false);
  }
});

document.getElementById('downloadExcelBtn').addEventListener('click', async () => {
  const link = document.createElement('a');
  link.href     = '/api/download/excel';
  link.download = `tenbit_tasks_${new Date().toISOString().split('T')[0]}.xlsx`;
  link.click();
  updateStatus('✅ Excel file download started!', 'success');
});

document.getElementById('syncSheetsBtn').addEventListener('click', async () => {
  updateStatus('🔗 Syncing tasks to Google Sheets...', 'info');
  showLoading(true, 'Syncing Google Sheets...');
  try {
    const res    = await fetch('/api/google-sheets/sync', { method: 'POST' });
    const result = await res.json();
    if (result.status === 'ok' && result.url) {
      sheetsUrl = result.url;
      showSheetLink(sheetsUrl);
      updateStatus(`✅ Google Sheets synced!\n${result.url}`, 'success');
    } else if (result.status === 'error') {
      updateStatus(`❌ Sync failed: ${result.detail}`, 'error');
    } else {
      updateStatus('⚠️ Google Sheets not enabled. Configure it above.', 'warning');
    }
  } catch (err) {
    updateStatus(`❌ Error: ${err.message}`, 'error');
  } finally {
    showLoading(false);
  }
});

document.getElementById('refreshAllBtn').addEventListener('click', async () => {
  showLoading(true, 'Refreshing...');
  try {
    await loadConfig();
    await loadSheetsConfig();
    await loadTasks();
    await loadMessages();
    updateStatus('✅ All data refreshed!', 'success');
  } catch (err) {
    updateStatus(`❌ Refresh failed: ${err.message}`, 'error');
  } finally {
    showLoading(false);
  }
});

document.getElementById('clearStatusBtn').addEventListener('click', () => {
  statusBox.textContent  = 'Status cleared.';
  statusBox.style.color  = '#94a3b8';
});

// ── Tabs ──────────────────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
    btn.classList.add('active');
    const tab = btn.dataset.tab;
    document.getElementById('tab-' + tab).style.display = 'block';
    if (tab === 'tasks')    loadTasks();
    if (tab === 'messages') loadMessages();
  });
});

// ── Tasks Table ───────────────────────────────────────────────────────────────
async function loadTasks() {
  try {
    const res  = await fetch('/api/db/tasks');
    const data = await res.json();
    allTasks   = data.tasks || [];
    document.getElementById('tasksCount').textContent      = `${data.count} tasks`;
    document.getElementById('statTasks').textContent       = data.count;
    document.getElementById('statTasksDetail').textContent =
      data.count > 0 ? `Updated: ${new Date().toLocaleTimeString()}` : 'No tasks yet';
    renderTasks(allTasks);
  } catch (err) {
    console.error('loadTasks error:', err);
  }
}

function renderTasks(tasks) {
  const tbody = document.getElementById('tasksBody');
  tbody.innerHTML = '';
  if (!tasks.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-row">No tasks yet. Run extraction to populate.</td></tr>';
    return;
  }
  tasks.forEach(t => {
    const tr = document.createElement('tr');
    const statusClass = { completed:'badge-green', in_progress:'badge-blue', open:'badge-gray', blocked:'badge-red', review:'badge-yellow' }[t.status] || 'badge-gray';
    const prioClass   = { urgent:'badge-red', high:'badge-orange', medium:'badge-blue', low:'badge-gray' }[t.priority] || 'badge-gray';
    tr.innerHTML = `
      <td><strong>${esc(t.assignee||'—')}</strong></td>
      <td class="cell-task">${esc(t.task||'—')}</td>
      <td><span class="badge ${statusClass}">${esc(t.status||'—')}</span></td>
      <td><span class="badge ${prioClass}">${esc(t.priority||'—')}</span></td>
      <td>${esc(t.deadline||'—')}</td>
      <td><small>${esc(t.source_sender||'—')}</small></td>
      <td><small>${esc((t.message_timestamp||'—').substring(0,16))}</small></td>
      <td>${t.confidence?(t.confidence*100).toFixed(0)+'%':'—'}</td>
    `;
    tbody.appendChild(tr);
  });
}

document.getElementById('taskSearch').addEventListener('input', e => {
  const q = e.target.value.toLowerCase();
  renderTasks(allTasks.filter(t =>
    (t.assignee||'').toLowerCase().includes(q) || (t.task||'').toLowerCase().includes(q)
  ));
});

document.getElementById('taskFilter').addEventListener('change', e => {
  const s = e.target.value;
  renderTasks(s ? allTasks.filter(t => t.status === s) : allTasks);
});

document.getElementById('refreshTasksBtn').addEventListener('click', loadTasks);

// ── Messages Table ────────────────────────────────────────────────────────────
async function loadMessages() {
  try {
    const res  = await fetch('/api/db/messages');
    const data = await res.json();
    allMessages = data.messages || [];
    document.getElementById('msgsCount').textContent      = `${data.count} messages`;
    document.getElementById('statMessages').textContent   = data.count;
    document.getElementById('statMessagesDetail').textContent =
      data.count > 0 ? `Updated: ${new Date().toLocaleTimeString()}` : 'No messages yet';
    renderMessages(allMessages);
    populateSenderFilter();
  } catch (err) {
    console.error('loadMessages error:', err);
  }
}

function renderMessages(messages) {
  const tbody = document.getElementById('msgsBody');
  tbody.innerHTML = '';
  if (!messages.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty-row">No messages yet. Run extraction to populate.</td></tr>';
    return;
  }
  messages.forEach(m => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${esc(m.sender||'—')}</strong></td>
      <td class="cell-task">${esc(m.message_text_normalized||'—')}</td>
      <td><small>${esc((m.message_timestamp||'—').substring(0,16))}</small></td>
      <td><small>${esc((m.processed_at||'—').replace('T',' ').substring(0,16))}</small></td>
    `;
    tbody.appendChild(tr);
  });
}

function populateSenderFilter() {
  const sel     = document.getElementById('msgFilter');
  const current = sel.value;
  const senders = [...new Set(allMessages.map(m => m.sender).filter(Boolean))];
  sel.innerHTML = '<option value="">All Senders</option>';
  senders.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s; opt.textContent = s;
    sel.appendChild(opt);
  });
  sel.value = current;
}

document.getElementById('msgSearch').addEventListener('input', e => {
  const q = e.target.value.toLowerCase();
  renderMessages(allMessages.filter(m =>
    (m.sender||'').toLowerCase().includes(q) ||
    (m.message_text_normalized||'').toLowerCase().includes(q)
  ));
});

document.getElementById('msgFilter').addEventListener('change', e => {
  const s = e.target.value;
  renderMessages(s ? allMessages.filter(m => m.sender === s) : allMessages);
});

document.getElementById('refreshMsgsBtn').addEventListener('click', loadMessages);

// ── Footer ────────────────────────────────────────────────────────────────────
function updateFooter() {
  const el = document.getElementById('footerTime');
  if (el) el.textContent = new Date().toLocaleString();
}

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  updateStatus('⏳ Loading system...', 'info');
  showLoading(true, 'Initializing...');
  try {
    onProviderChange();          // populate default models first
    await loadConfig();
    await loadSheetsConfig();
    await loadTasks();
    await loadMessages();
    updateFooter();
    setInterval(updateFooter, 60000);
    updateStatus('✅ System ready. Configure settings and click "Run Task Extraction" to start.', 'success');
  } catch (err) {
    updateStatus(`❌ Init failed: ${err.message}`, 'error');
  } finally {
    showLoading(false);
  }
}

window.addEventListener('load', init);
