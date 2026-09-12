// Frontend logic for the Document Intelligence dashboard + result pages.
// Talks to the backend REST API (same origin) under /api/v1.

async function handleUpload(e) {
  e.preventDefault();
  const btn = document.getElementById('submit-btn');
  const statusEl = document.getElementById('status-msg');
  const fileInput = document.getElementById('file');
  const docType = document.getElementById('document_type').value;

  if (!fileInput.files.length || !docType) {
    statusEl.textContent = 'Select a document type and a file.';
    return;
  }

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  formData.append('document_type', docType);

  btn.disabled = true;
  statusEl.textContent = 'Processing... (OCR + AI extraction can take a few seconds)';

  try {
    const res = await fetch('/api/v1/documents/process', { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) {
      const msg = (data.error && data.error.message) || 'Processing failed.';
      statusEl.textContent = `❌ ${msg}`;
    } else {
      statusEl.textContent = `✅ Processed with status: ${data.processing_status}`;
      fileInput.value = '';
      loadDashboard();
    }
  } catch (err) {
    statusEl.textContent = `❌ Request failed: ${err}`;
  } finally {
    btn.disabled = false;
  }
}

async function loadDashboard() {
  const tbody = document.getElementById('doc-table-body');
  if (!tbody) return;
  try {
    const res = await fetch('/api/v1/documents');
    const docs = await res.json();
    if (!docs.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="muted">No documents processed yet.</td></tr>';
      return;
    }
    tbody.innerHTML = docs.map(d => `
      <tr>
        <td><a class="row-link" href="/document/${encodeURIComponent(d.document_name)}">${d.document_name}</a></td>
        <td>${d.document_type}</td>
        <td><span class="badge ${d.processing_status}">${d.processing_status}</span></td>
        <td>${d.overall_confidence ?? '—'}</td>
        <td>${new Date(d.created_at).toLocaleString()}</td>
      </tr>
    `).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="muted">Failed to load documents: ${err}</td></tr>`;
  }
}

function fieldRow(name, field) {
  const val = (field && typeof field === 'object' && 'value' in field) ? field.value : field;
  const missing = val === null || val === undefined || val === '';
  const evidence = (field && typeof field === 'object' && field.source_text)
    ? `<div class="evidence">"${field.source_text}"${field.page_number ? ' — p.' + field.page_number : ''}</div>`
    : '';
  return `
    <div class="field-row">
      <div class="field-name">${name}</div>
      <div class="field-value ${missing ? 'missing' : ''}">${missing ? 'MISSING' : val}</div>
      ${evidence}
    </div>`;
}

function renderValidation(validation) {
  if (!validation || !validation.checks || !validation.checks.length) {
    return '<p class="muted">No financial validation checks were applicable for this document.</p>';
  }
  const rows = validation.checks.map(c => `
    <tr>
      <td>${c.name}</td>
      <td class="muted">${c.formula}</td>
      <td>${c.calculated_value ?? '—'}</td>
      <td>${c.reported_value ?? '—'}</td>
      <td>${c.variance ?? '—'}</td>
      <td><span class="badge ${c.status}">${c.status}</span></td>
    </tr>
  `).join('');
  return `
    <p>Overall: <span class="badge ${validation.overall_status}">${validation.overall_status}</span></p>
    <table>
      <thead><tr><th>Check</th><th>Formula</th><th>Calculated</th><th>Reported</th><th>Variance</th><th>Status</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function renderTables(tables) {
  if (!tables || !Object.keys(tables).length) return '<p class="muted">No line-item tables extracted.</p>';
  return Object.entries(tables).map(([name, rows]) => {
    if (!Array.isArray(rows) || !rows.length) return `<p class="muted">${name}: empty</p>`;
    const cols = Object.keys(rows[0]);
    const head = cols.map(c => `<th>${c}</th>`).join('');
    const body = rows.map(r => `<tr>${cols.map(c => `<td>${r[c] ?? '—'}</td>`).join('')}</tr>`).join('');
    return `<h3 style="font-size:13px;color:var(--muted);text-transform:uppercase">${name}</h3>
      <table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  }).join('');
}

async function loadDocumentResult(documentName) {
  const container = document.getElementById('result-content');
  try {
    const res = await fetch(`/api/v1/documents/${encodeURIComponent(documentName)}`);
    const data = await res.json();
    if (!res.ok) {
      container.innerHTML = `<div class="panel">❌ ${(data.error && data.error.message) || 'Not found'}</div>`;
      return;
    }

    const fields = Object.entries(data.extracted_data || {}).map(([k, v]) => fieldRow(k, v)).join('');

    container.innerHTML = `
      <div class="panel">
        <h2>Overview</h2>
        <p><strong>${data.document_name}</strong> — ${data.document_type}
           &nbsp; <span class="badge ${data.processing_status}">${data.processing_status}</span>
           ${data.overall_confidence != null ? `&nbsp; confidence: ${data.overall_confidence}` : ''}</p>
        <p class="muted">Processed at ${data.processing_metadata?.processed_at ?? '—'}
           · OCR used: ${data.processing_metadata?.ocr_used ?? '—'}
           · ${data.processing_metadata?.processing_time_ms ?? '—'} ms</p>
        ${data.error ? `<p style="color:var(--fail)">Error: ${data.error.message}</p>` : ''}
      </div>

      <div class="panel">
        <div class="tabs">
          <button class="tab-btn active" onclick="showTab('fields')">Extracted Fields</button>
          <button class="tab-btn" onclick="showTab('tables')">Tables / Line Items</button>
          <button class="tab-btn" onclick="showTab('validation')">Financial Validation</button>
          <button class="tab-btn" onclick="showTab('raw')">Raw JSON</button>
        </div>
        <div id="tab-fields" class="tab-panel"><div class="grid-fields">${fields || '<p class="muted">No fields extracted.</p>'}</div></div>
        <div id="tab-tables" class="tab-panel" style="display:none">${renderTables(data.tables)}</div>
        <div id="tab-validation" class="tab-panel" style="display:none">${renderValidation(data.validation)}</div>
        <div id="tab-raw" class="tab-panel" style="display:none"><pre class="json-view">${JSON.stringify(data, null, 2)}</pre></div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div class="panel">❌ Failed to load result: ${err}</div>`;
  }
}

function showTab(name) {
  ['fields', 'tables', 'validation', 'raw'].forEach(t => {
    document.getElementById(`tab-${t}`).style.display = (t === name) ? 'block' : 'none';
  });
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
}
