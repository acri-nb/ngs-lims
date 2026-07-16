// STATUS COUNTS 
const rows = document.querySelectorAll('#qcTbody tr');
const counts = { Pass:0, Fail:0, Caution:0, Pending:0 };
rows.forEach(row => {
  const badge = row.querySelector('.status-badge');
  if (!badge) return;
  const cls = [...badge.classList].find(c => c.startsWith('status-') && c !== 'status-badge');
  if (cls) {
    const key = cls.replace('status-','');
    if (key in counts) counts[key]++;
  }
});
document.getElementById('cnt-pass').textContent    = counts.Pass;
document.getElementById('cnt-fail').textContent    = counts.Fail;
document.getElementById('cnt-caution').textContent = counts.Caution;
document.getElementById('cnt-pending').textContent = counts.Pending;

// TABLE SEARCH 
const tableSearch = document.getElementById('tableSearch');
if (tableSearch) {
  tableSearch.addEventListener('input', () => {
    const q = tableSearch.value.toLowerCase();
    rows.forEach(row => {
      row.style.display = row.dataset.search.includes(q) ? '' : 'none';
    });
  });
}

//  EXPORT CSV 
// Reads sample data directly from the table row data-* attributes.
function exportCSV() {
  let headers, rows_data = [];

  if (BATCH_TYPE === 'DNA') {
    headers = ['sample_id', 'qubit(ng/uL)', 'nanodrop(260/280)', 'nanodrop(260/230)'];
  } else if (BATCH_TYPE === 'RNA') {
    headers = ['sample_id', 'qubit(ng/uL)', 'RIN', 'dv200'];
  } else {
    headers = ['sample_id', 'qubit(ng/uL)', 'RIN', 'dv200', 'nanodrop(260/280)', 'nanodrop(260/230)'];
  }

  document.querySelectorAll('#qcTbody tr').forEach(row => {
    const sampleId = row.dataset.sample || '';
    const qubitNM  = row.dataset.qubit;

    // Convert nM back to ng/µL for the export (what the instrument shows)
    let qubitNgUl = '';
    if (qubitNM !== '') {
      const factor = BATCH_TYPE === 'RNA' ? 40 : 100;
      qubitNgUl = (parseFloat(qubitNM) * factor).toFixed(3);
    }

    let rowData;
    if (BATCH_TYPE === 'DNA') {
      rowData = [
        sampleId,
        qubitNgUl,
        row.dataset.nd280 || '',
        row.dataset.nd230 || '',
      ];
    } else if (BATCH_TYPE === 'RNA') {
      rowData = [
        sampleId,
        qubitNgUl,
        row.dataset.rin   || '',
        row.dataset.dv200 || '',
      ];
    } else {
      rowData = [
        sampleId,
        qubitNgUl,
        row.dataset.rin   || '',
        row.dataset.dv200 || '',
        row.dataset.nd280 || '',
        row.dataset.nd230 || '',
      ];
    }
    rows_data.push(rowData);
  });

  const csvContent = [
    headers.join(','),
    ...rows_data.map(r => r.map(v => `"${v}"`).join(','))
  ].join('\r\n');

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `${BATCH_NAME}_QC_template.csv`;
  a.click();
  URL.revokeObjectURL(url);
  showToast('CSV exported, fill in the values and import when done', 'success');
}

//  IMPORT MODAL 
let selectedFile = null;

function openImportModal() {
  selectedFile = null;
  document.getElementById('fileNameDisplay').style.display = 'none';
  document.getElementById('fileNameDisplay').textContent   = '';
  document.getElementById('csvInput').value = '';
  document.getElementById('btnDoImport').disabled = true;
  document.getElementById('importResult').style.display    = 'none';
  document.getElementById('importResult').innerHTML        = '';
  document.getElementById('importModal').classList.add('open');
}
function closeImportModal() {
  document.getElementById('importModal').classList.remove('open');
}
document.getElementById('importModal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeImportModal();
});

// File picker
document.getElementById('csvInput').addEventListener('change', e => {
  const file = e.target.files[0];
  if (file) setFile(file);
});

// Drag-and-drop on the drop zone
const dropZone = document.getElementById('dropZone');
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', ()  => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) setFile(file);
});

function setFile(file) {
  if (!file.name.endsWith('.csv')) {
    showToast('Please select a .csv file', 'error');
    return;
  }
  selectedFile = file;
  const display = document.getElementById('fileNameDisplay');
  display.textContent = file.name;
  display.style.display = 'block';
  document.getElementById('btnDoImport').disabled = false;
  // Clear any previous result
  document.getElementById('importResult').style.display = 'none';
  document.getElementById('importResult').innerHTML     = '';
}

async function doImport() {
  if (!selectedFile) return;

  const btn = document.getElementById('btnDoImport');
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Importing…';

  const formData = new FormData();
  formData.append('csv_file', selectedFile);

  try {
    const res  = await fetch(IMPORT_URL, {
      method: 'POST',
      headers: { 'X-CSRFToken': CSRF_TOKEN },
      body: formData,
    });
    const data = await res.json();

    if (!data.ok) {
      showToast(data.error || 'Import failed', 'error');
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-upload"></i> Upload & Import';
      return;
    }

    renderImportResult(data);
    btn.innerHTML = '<i class="fas fa-check"></i> Done';

    if (data.updated.length > 0) {
      showToast(`${data.updated.length} record${data.updated.length > 1 ? 's' : ''} updated, reloading…`, 'success');
      setTimeout(() => location.reload(), 1800);
    }

  } catch (err) {
    showToast('Network error, please try again', 'error');
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-upload"></i> Upload & Import';
  }
}

function renderImportResult(data) {
  const el = document.getElementById('importResult');
  el.style.display = 'block';
  let html = '';

  if (data.updated.length > 0) {
    html += `<div class="result-section">
      <div class="result-section-title r-ok"><i class="fas fa-check-circle"></i> Updated (${data.updated.length})</div>
      <ul class="result-list">
        ${data.updated.map(n => `<li class="r-ok"><i class="fas fa-check" style="font-size:.7rem;"></i>${n}</li>`).join('')}
      </ul>
    </div>`;
  }

  if (data.skipped.length > 0) {
    html += `<div class="result-section">
      <div class="result-section-title r-skip"><i class="fas fa-exclamation-triangle"></i> Skipped, not in batch (${data.skipped.length})</div>
      <ul class="result-list">
        ${data.skipped.map(n => `<li class="r-skip"><i class="fas fa-minus" style="font-size:.7rem;"></i>${n}</li>`).join('')}
      </ul>
    </div>`;
  }

  if (data.errors.length > 0) {
    html += `<div class="result-section">
      <div class="result-section-title r-err"><i class="fas fa-times-circle"></i> Errors (${data.errors.length})</div>
      <ul class="result-list">
        ${data.errors.map(e => `<li class="r-err"><i class="fas fa-times" style="font-size:.7rem;"></i>${e}</li>`).join('')}
      </ul>
    </div>`;
  }

  if (!html) {
    html = '<div style="color:var(--text-muted);font-size:.83rem;">Nothing was changed, the file may be empty or all samples were unrecognised.</div>';
  }

  el.innerHTML = html;
}

// TOAST 
function showToast(msg, type='') {
  const wrap = document.getElementById('toastWrap');
  const el   = document.createElement('div');
  el.className = `toast ${type}`;
  const icon = type==='success'?'fa-check-circle':type==='error'?'fa-times-circle':'fa-info-circle';
  el.innerHTML = `<i class="fas ${icon}"></i> ${msg}`;
  wrap.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function openGatesModal()  { document.getElementById('gatesModal').classList.add('open'); }
function closeGatesModal() { document.getElementById('gatesModal').classList.remove('open'); }
function openRulesModal()  { document.getElementById('rulesModal').classList.add('open'); }
function closeRulesModal() { document.getElementById('rulesModal').classList.remove('open'); }

async function saveGates() {
  const btn = document.getElementById('btnSaveGates');
  const msg = document.getElementById('gatesSaveMsg');
  const inputs = document.querySelectorAll('#gatesModal input[type="number"]');

  const body = new URLSearchParams();
  inputs.forEach(inp => body.append(inp.id, inp.value));

  btn.disabled = true;
  msg.textContent = 'Saving…';
  msg.style.color = 'var(--text-muted)';

  try {
    const resp = await fetch(GATES_SAVE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': CSRF_TOKEN },
      body: body.toString(),
    });
    const data = await resp.json();

    if (resp.ok && data.ok) {
      msg.style.color = 'var(--success)';
      msg.textContent = `Saved, ${data.recalculated} sample(s) recalculated. Reloading…`;
      setTimeout(() => location.reload(), 700);
    } else {
      msg.style.color = 'var(--danger)';
      msg.textContent = data.error || 'Could not save gates.';
      btn.disabled = false;
    }
  } catch (err) {
    msg.style.color = 'var(--danger)';
    msg.textContent = 'Network error, could not save.';
    btn.disabled = false;
  }
}