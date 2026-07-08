
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
  const actionLabels = { prep: 'Prepped', skip: 'Skipped', requeue: 'Requeued' };
  const actionClasses = { prep: 'badge-pass', skip: 'badge-fail', requeue: 'badge-caution' };
  badge.textContent  = actionLabels[d.action] || d.wellType || '—';
  badge.className    = 'detail-badge ' + (actionClasses[d.action] || '');

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

function buildLibprepTable() {
  if (libprepTableBuilt) return; // build once; plate wells don't change after page load
  libprepTableBuilt = true;

  const wells = Array.from(document.querySelectorAll('#libprep-tab-plate .well.well-occupied'));

  // Order by column first (01, 02, 03 …), then by row letter within each column (A, B, C …)
  wells.sort((a, b) => {
    const pa = parsePos(a.dataset.pos);
    const pb = parsePos(b.dataset.pos);
    if (pa.col !== pb.col) return pa.col - pb.col;
    return pa.rowLetter.localeCompare(pb.rowLetter);
  });

  const actionLabels  = { prep: 'Prepped', skip: 'Skipped', requeue: 'Requeued' };
  const actionClasses = { prep: 'badge-pass', skip: 'badge-fail', requeue: 'badge-caution' };

  const tbody = document.getElementById('libprepTableBody');
  tbody.innerHTML = '';

  if (wells.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-5 text-muted">No samples assigned to this plate yet.</td></tr>`;
    return;
  }

  wells.forEach(w => {
    const d = w.dataset;
    const isControl = w.classList.contains('well-control');
    const sampleName = d.sampleName || 'Control';
    const statusLabel = isControl ? 'Control' : (actionLabels[d.action] || d.wellType || '—');
    const statusClass = isControl ? 'badge-pending' : (actionClasses[d.action] || 'badge-pending');

    const tr = document.createElement('tr');
    tr.className = 'libprep-row';
    tr.dataset.search = (d.pos + ' ' + sampleName).toLowerCase();

    tr.innerHTML = `
      <td><span class="sample-id">${d.pos}</span></td>
      <td style="font-weight:600;font-size:0.875rem;">${sampleName}</td>
      <td><span class="lims-badge ${statusClass}">${statusLabel}</span></td>
      <td class="mono">${d.conc        ? d.conc + ' ng/µL' : '<span class="null-val">—</span>'}</td>
      <td class="mono">${d.volSample   ? d.volSample + ' µL' : '<span class="null-val">—</span>'}</td>
      <td class="mono">${d.volDiluent  ? d.volDiluent + ' µL' : '<span class="null-val">—</span>'}</td>
      <td class="mono">${d.actualInput ? d.actualInput + ' ng' : '<span class="null-val">—</span>'}</td>
    `;
    tbody.appendChild(tr);
  });
}

function filterLibprepTable() {
  const q = document.getElementById('libprepTableSearch').value.toLowerCase().trim();
  document.querySelectorAll('#libprepTable tbody tr.libprep-row').forEach(row => {
    row.style.display = row.dataset.search.includes(q) ? '' : 'none';
  });
}

