
const STATUS_LABELS = {
  pending_prep: 'Pending Library Prep',
  prepped:      'Library Prepped',
  pending_qc:   'Pending Library QC',
  qc_pass:      'Library QC: Pass',
  qc_caution:   'Library QC: Caution',
  qc_fail:      'Library QC: Fail',
  skipped:      'Skipped',
  control:      'Control',
};
const STATUS_BADGE_CLASS = {
  pending_prep: 'status-pending_prep',
  prepped:      'status-pending_qc', // unreachable in practice, see note below
  pending_qc:   'status-pending_qc',
  qc_pass:      'status-qc_pass',
  qc_caution:   'status-qc_caution',
  qc_fail:      'status-qc_fail',
  skipped:      'status-skipped',
  control:      'status-control',
};

let activeWell = null;

function selectWell(btn) {
  // Deselect previous
  if (activeWell) activeWell.classList.remove('well-selected');

  if (activeWell === btn) {
    // Toggle off
    activeWell = null;
    document.getElementById('detailEmpty').style.display   = '';
    document.getElementById('detailContent').style.display = 'none';
    return;
  }

  activeWell = btn;
  btn.classList.add('well-selected');

  const isEmpty = !btn.classList.contains('well-occupied');
  document.getElementById('detailEmpty').style.display   = isEmpty ? '' : 'none';
  document.getElementById('detailContent').style.display = isEmpty ? 'none' : '';

  if (isEmpty) return;

  // Populate panel
  const d = btn.dataset;

  document.getElementById('dPos').textContent  = d.pos  || '—';
  document.getElementById('dName').textContent = d.sampleName || '—';

  // Badge
  const badge = document.getElementById('dBadge');
  badge.textContent = d.statusLabel || STATUS_LABELS[d.status] || '—';
  badge.className = 'detail-badge ' + (STATUS_BADGE_CLASS[d.status] || '');
  
  // Volume
  set('dConc',       d.conc       ? d.conc + ' ng/µL' : '—');
  set('dVolSample',  d.volSample  ? d.volSample + ' µL' : '—');
  set('dVolDiluent', d.volDiluent ? d.volDiluent + ' µL' : '—');
  set('dActualInput',d.actualInput? d.actualInput + ' ng' : '—');

  const svRow = document.getElementById('dSpeedVacRow');
  if (d.speedvac === 'true') {
    svRow.style.display = '';
    set('dSpeedVac', '<span style="color:var(--warning);font-weight:600;">⚠ Required</span>');
  } else {
    svRow.style.display = 'none';
  }

  // Index
  set('dUDI',        d.indexUdi       || '—');
  set('dIndexSetWell', (d.indexSet && d.indexWell) ? `Set ${d.indexSet.toUpperCase()} / ${d.indexWell}` : '—');
  set('dI7',         d.indexI7  || '—');
  set('dI5',         d.indexI5  || '—');
  set('dPCR',        d.pcr      ? d.pcr + ' cycles' : '—');
}

function set(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}

/*  TAB SWITCHING */
function showLibprepTab(name, btnEl) {
  document.querySelectorAll('.libprep-pane').forEach(p => p.style.display = 'none');
  document.getElementById('libprep-tab-' + name).style.display = '';

  document.querySelectorAll('.libprep-tab').forEach(t => t.classList.remove('active'));
  btnEl.classList.add('active');

  if (name === 'table') buildLibprepTable();
}

/* WELL DATA TABLE (built from the plate's own well buttons)  */
let libprepTableBuilt = false;

function parsePos(pos) {
  // e.g. "A01" -> { rowLetter: "A", col: 1 }
  const m = pos.match(/^([A-Za-z]+)(\d+)$/);
  if (!m) return { rowLetter: pos, col: 0 };
  return { rowLetter: m[1], col: parseInt(m[2], 10) };
}


function getLibprepColumns() {
  const cfg = (typeof WORKFLOW_CONFIG !== 'undefined') ? WORKFLOW_CONFIG : {};

  const cols = [
    { key: 'well',   label: 'Well',   get: d => d.pos || '' },
    { key: 'status', label: 'Status', get: d => d.statusLabel || '' },
    { key: 'sample', label: 'Sample', get: d => d.sampleName || '' },
    { key: 'conc',   label: 'Conc. (ng/uL)', get: d => d.conc || '', unit: '' },
    { key: 'volSample',  label: `${cfg.sampleType || 'Sample'} (uL)`, get: d => d.volSample || '' },
    { key: 'volDiluent', label: `${cfg.diluentName || 'Diluent'} (uL)`, get: d => d.volDiluent || '' },
  ];

  if (cfg.usesQiaSpike) {
    cols.push({ key: 'qiaSpike', label: 'QIA Spike (uL)', get: d => d.qiaSpike || '' });
  }

  cols.push({ key: 'actualInput', label: 'Actual Input (ng)', get: d => d.actualInput || '' });

  if (cfg.logsPlateAndWell) {
    cols.push({ key: 'plateSet',  label: 'Plate Set',  get: d => d.indexSet  || '', editable: true });
    cols.push({ key: 'indexWell', label: 'Index Well', get: d => d.indexWell || '', editable: true });
    cols.push({ key: 'udi',       label: 'UDI',         get: d => d.indexUdi  || '' }); // computed, not imported
  } else {
    cols.push({ key: 'udi', label: 'UDI', get: d => d.indexUdi || '', editable: true });
  }

  if (cfg.requiresPcr) {
    cols.push({ key: 'pcrCycles', label: 'PCR Cycles', get: d => d.pcr || '', editable: true });
  }

  cols.push({ key: 'qubit', label: 'Qubit (ng/uL)', get: d => d.qubit || '', editable: true });
  cols.push({ key: 'nm',    label: 'in nM',          get: d => d.nm    || '' }); // computed, not imported

  if (cfg.usesTapestation) {
    cols.push({ key: 'avgLibSize', label: 'Avg Lib Size',   get: d => d.avgLibSize || '', editable: true });
    cols.push({ key: 'dimerPeak',  label: 'Dimer Peak %',   get: d => d.dimerPeak  || '', editable: true });
    cols.push({ key: 'regionPct',  label: 'Region %',       get: d => d.regionPct  || '', editable: true });
    cols.push({ key: 'regionNm',   label: 'Region nM',      get: d => d.regionNm   || '', editable: true });
  }

  cols.push({ key: 'qc', label: 'QC', get: d => d.libqcStatus || '' }); // computed, not imported

  return cols;
}

function buildLibprepTableHead() {
  const headRow = document.getElementById('libprepTableHeadRow');
  if (!headRow) return;
  headRow.innerHTML = getLibprepColumns().map(c => `<th>${c.label}</th>`).join('');
}

function buildLibprepTable() {
  if (libprepTableBuilt) return; // build once; plate wells don't change after page load
  libprepTableBuilt = true;

  buildLibprepTableHead();

  const wells = Array.from(document.querySelectorAll('#libprep-tab-plate .well.well-occupied'));

  // Order by column first (01, 02, 03 …), then by row letter within each column (A, B, C …)
  wells.sort((a, b) => {
    const pa = parsePos(a.dataset.pos);
    const pb = parsePos(b.dataset.pos);
    if (pa.col !== pb.col) return pa.col - pb.col;
    return pa.rowLetter.localeCompare(pb.rowLetter);
  });

  const columns = getLibprepColumns();
  const tbody = document.getElementById('libprepTableBody');
  tbody.innerHTML = '';

  if (wells.length === 0) {
    tbody.innerHTML = `<tr><td colspan="${columns.length}" class="text-center py-5 text-muted">No samples assigned to this plate yet.</td></tr>`;
    return;
  }

  wells.forEach(w => {
    const d = w.dataset;
    const isControl = w.classList.contains('well-control');
    const sampleName = d.sampleName || 'Control';

    const tr = document.createElement('tr');
    tr.className = 'libprep-row';
    tr.dataset.search = (d.pos + ' ' + sampleName).toLowerCase();

    if (isControl) {
      tr.innerHTML = `
        <td><span class="sample-id">${d.pos}</span></td>
        <td style="font-weight:600;font-size:0.875rem;">${sampleName}</td>
        <td colspan="${columns.length - 2}" class="text-muted">No prep calculation, control well.</td>
      `;
      tbody.appendChild(tr);
      return;
    }

    tr.innerHTML = columns.map(c => {
      const raw = c.get(d);
      if (c.key === 'well') return `<td><span class="sample-id">${raw}</span></td>`;
      if (c.key === 'sample') return `<td style="font-weight:600;font-size:0.875rem;">${raw}</td>`;
      if (c.key === 'qc') {
        if (!raw) return `<td><span class="null-val">—</span></td>`;
        const qcClass = { pass: 'badge-pass', fail: 'badge-fail', caution: 'badge-caution', pending: 'badge-pending' }[raw] || 'badge-pending';
        return `<td><span class="lims-badge ${qcClass}">${raw.charAt(0).toUpperCase() + raw.slice(1)}</span></td>`;
      }
      if (c.key === 'status') {
        if (!raw) return `<td><span class="null-val">—</span></td>`;
        const cls = STATUS_BADGE_CLASS[d.status] || 'status-pending_prep';
        return `<td><span class="lims-badge ${cls}">${raw}</span></td>`;
      }
      return `<td class="mono">${raw ? raw : '<span class="null-val">—</span>'}</td>`;
    }).join('');

    tbody.appendChild(tr);
  });
}

function filterLibprepTable() {
  const q = document.getElementById('libprepTableSearch').value.toLowerCase().trim();
  document.querySelectorAll('#libprepTable tbody tr.libprep-row').forEach(row => {
    row.style.display = row.dataset.search.includes(q) ? '' : 'none';
  });
}

/*  EXPORT CSV (client-side, from the currently built table) */
function exportLibprepCSV() {
  buildLibprepTable(); // make sure it's populated even if user hasn't opened the tab yet

  const columns = getLibprepColumns();
  const headers = columns.map(c => c.label);
  const rows = [headers];

  const wells = Array.from(document.querySelectorAll('#libprep-tab-plate .well.well-occupied'));
  wells.sort((a, b) => {
    const pa = parsePos(a.dataset.pos);
    const pb = parsePos(b.dataset.pos);
    if (pa.col !== pb.col) return pa.col - pb.col;
    return pa.rowLetter.localeCompare(pb.rowLetter);
  });

  wells.forEach(w => {
    const d = w.dataset;
    rows.push(columns.map(c => c.get(d) || ''));
  });

  const csv = rows.map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\r\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${LIBPREP_PLATE_NAME || 'libprep_batch'}_well_data.csv`;
  a.click();
  URL.revokeObjectURL(url);
  showToast('CSV exported, fill in the blanks and re-import when done', 'success');
}

/* IMPORT RESULTS MODAL */
let selectedImportFile = null;

function openImportModal() {
  selectedImportFile = null;
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

document.getElementById('csvInput').addEventListener('change', e => {
  const file = e.target.files[0];
  if (file) setImportFile(file);
});

const importDropZone = document.getElementById('dropZone');
importDropZone.addEventListener('dragover', e => { e.preventDefault(); importDropZone.classList.add('dragover'); });
importDropZone.addEventListener('dragleave', () => importDropZone.classList.remove('dragover'));
importDropZone.addEventListener('drop', e => {
  e.preventDefault();
  importDropZone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) setImportFile(file);
});

function setImportFile(file) {
  if (!file.name.endsWith('.csv')) {
    showToast('Please select a .csv file', 'error');
    return;
  }
  selectedImportFile = file;
  const display = document.getElementById('fileNameDisplay');
  display.textContent = file.name;
  display.style.display = 'block';
  document.getElementById('btnDoImport').disabled = false;
  document.getElementById('importResult').style.display = 'none';
  document.getElementById('importResult').innerHTML     = '';
}

async function doImport() {
  if (!selectedImportFile) return;

  const btn = document.getElementById('btnDoImport');
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Importing…';

  const formData = new FormData();
  formData.append('csv_file', selectedImportFile);

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
      <div class="result-section-title r-skip"><i class="fas fa-exclamation-triangle"></i> Skipped, well not found in this batch (${data.skipped.length})</div>
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
    html = '<div style="color:var(--text-muted);font-size:.83rem;">Nothing was changed, the file may be empty or no wells matched.</div>';
  }

  el.innerHTML = html;
}

/* TOAST */
function showToast(msg, type = '') {
  const wrap = document.getElementById('toastWrap');
  if (!wrap) return;
  const el   = document.createElement('div');
  el.className = `toast ${type}`;
  const icon = type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-times-circle' : 'fa-info-circle';
  el.innerHTML = `<i class="fas ${icon}"></i> ${msg}`;
  wrap.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

let mmSavedReactionCount = null; // set on first paint / after a successful save
let mmSaveInFlight = false;

// Mirrors WorkflowStepRowOrder.ethanol_dilution_volumes() in models.py —
// keep these two in sync if the rounding convention ever changes.
const ETOH_ROUND_INCREMENT_UL  = 5000;
const ETOH_BUFFER_THRESHOLD_UL = 1700;
const ETOH_PERCENT             = 0.8;

function ethanolDilutionVolumes(perRxn, extra, n) {
  const rawTotal = perRxn * (n + extra);
  let rounded = Math.ceil(rawTotal / ETOH_ROUND_INCREMENT_UL) * ETOH_ROUND_INCREMENT_UL;
  if (rawTotal >= rounded - ETOH_BUFFER_THRESHOLD_UL) {
    rounded += ETOH_ROUND_INCREMENT_UL;
  }
  const ethanol = rounded * ETOH_PERCENT;
  const waterBatch = Math.ceil(ethanol / ETOH_ROUND_INCREMENT_UL) * ETOH_ROUND_INCREMENT_UL;
  const water = waterBatch - ethanol;
  return [ethanol, water];
}

function mmRecomputeAll() { const input = document.getElementById('mmReactionCount');
  if (!input) return;

  const n = parseInt(input.value, 10);
  if (isNaN(n) || n < 0) return;

  document.querySelectorAll('.mm-step-card').forEach(card => {
    let stepTotal = 0;
    let anyValue = false;

    card.querySelectorAll('.mm-row').forEach(row => {
      const perRxn   = parseFloat(row.dataset.perRxn);
      const extra    = parseInt(row.dataset.extra, 10) || 0;
      const constant = row.dataset.constant === '0' ? 0 : (row.dataset.constant === '2' ? 2 : 1);

      if (isNaN(perRxn)) {
        const volCell = row.querySelector('.mm-vol');
        if (volCell) volCell.textContent = '—';
        return;
      }

      if (constant === 2) {
        // Ethanol Dilution Pair, this row + its water sibling row.
        const [ethanol, water] = ethanolDilutionVolumes(perRxn, extra, n);
        const ethanolCell = row.querySelector('.mm-vol-ethanol');
        if (ethanolCell) ethanolCell.textContent = ethanol.toFixed(2);

        const waterRow = row.nextElementSibling;
        const waterCell = waterRow ? waterRow.querySelector('.mm-vol-water') : null;
        if (waterCell) waterCell.textContent = water.toFixed(2);

        stepTotal += ethanol + water;
        anyValue = true;
        return;
      }

      const volCell = row.querySelector('.mm-vol');
      const volume = constant === 0 ? perRxn : perRxn * (n + extra);
      volCell.textContent = volume.toFixed(2);
      stepTotal += volume;
      anyValue = true;
    });

    const totalCell = card.querySelector('.mm-step-total');
    if (totalCell) totalCell.textContent = anyValue ? stepTotal.toFixed(2) : '—';
  });
}

function onMastermixReactionCountChange() {
  mmRecomputeAll();
  mmSetSaveStatus('dirty', 'Unsaved changes');
}

function mmSetSaveStatus(state, text) {
  const el = document.getElementById('mmSaveStatus');
  if (!el) return;
  el.className = 'mm-save-status' + (state ? ' ' + state : '');
  el.innerHTML = state === 'saved'
    ? `<i class="fas fa-check-circle"></i> ${text}`
    : state === 'error'
      ? `<i class="fas fa-exclamation-circle"></i> ${text}`
      : state === 'dirty'
        ? `<i class="fas fa-circle"></i> ${text}`
        : text || '';
}

async function saveMastermixReactionCount() {
  const input = document.getElementById('mmReactionCount');
  if (!input || mmSaveInFlight) return;

  const n = parseInt(input.value, 10);
  if (isNaN(n) || n < 0) {
    mmSetSaveStatus('error', 'Enter a valid, non-negative number');
    return;
  }

  mmSaveInFlight = true;
  mmSetSaveStatus('', 'Saving…');

  try {
    const resp = await fetch(MASTERMIX_SAVE_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': CSRF_TOKEN,
      },
      body: `reaction_count=${encodeURIComponent(n)}`,
    });
    const data = await resp.json();

    if (resp.ok && data.ok) {
      mmSavedReactionCount = data.reaction_count;
      mmSetSaveStatus('saved', 'Saved');
    } else {
      mmSetSaveStatus('error', data.error || 'Could not save');
    }
  } catch (err) {
    mmSetSaveStatus('error', 'Network error could not save');
  } finally {
    mmSaveInFlight = false;
  }
}

async function printMastermixSheet() {
  // Save first so the print sheet (a separate page/request) reflects
  // whatever reaction count is currently on screen.
  await saveMastermixReactionCount();
  window.open(MASTERMIX_PRINT_URL, '_blank');
}

// Recompute once on load in case the server-rendered value and the
// input's default value ever drift (defensive they should match).
document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('mmReactionCount')) {
    mmRecomputeAll();
  }
});

function filterLibraryQcTable() {
  const q = document.getElementById('libraryQcSearch').value.toLowerCase().trim();
  document.querySelectorAll('#libraryQcTable tbody tr.libraryqc-row').forEach(row => {
    row.style.display = row.dataset.search.includes(q) ? '' : 'none';
  });
}

function exportLibraryQcCSV() {
  const headers = ['Well','Status','Sample','Qubit','In nM','Avg Lib Size','Dimer Peak %','Region %','Region nM','QC'];
  const rows = [headers];
  document.querySelectorAll('#libraryQcTable tbody tr.libraryqc-row').forEach(tr => {
    rows.push(Array.from(tr.children).map(td => td.textContent.trim()));
  });
  const csv = rows.map(r => r.map(v => `"${v.replace(/"/g,'""')}"`).join(',')).join('\r\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${LIBPREP_PLATE_NAME || 'libprep_batch'}_library_qc.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function openQcGatesModal()  { document.getElementById('lqGatesModal').classList.add('open'); }
function closeQcGatesModal() { document.getElementById('lqGatesModal').classList.remove('open'); }

async function saveQcGates() {
  const btn = document.getElementById('btnSaveLqGates');
  const msg = document.getElementById('lqGatesSaveMsg');
  const inputs = document.querySelectorAll('#lqGatesModal input[type="number"]');

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



