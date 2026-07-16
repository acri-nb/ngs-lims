

//  VIRTUAL BATCH COUNTER (for temp IDs before save) 
let virtualCounter  = 0;
let isDirty         = false;
let draggingId      = null;

// DRAG 
function onDragStart(e) {
  draggingId = e.currentTarget.dataset.id;
  e.currentTarget.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'move';
}
function onDragEnd(e) {
  e.currentTarget.classList.remove('dragging');
  document.querySelectorAll('.drag-over,.drag-target').forEach(el => el.classList.remove('drag-over','drag-target'));
}
function onDragOver(e) {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  e.currentTarget.classList.add('drag-target');
  const card = e.currentTarget.closest('.batch-card');
  if (card) card.classList.add('drag-over');
}
function onDragLeave(e) {
  e.currentTarget.classList.remove('drag-target');
  const card = e.currentTarget.closest('.batch-card');
  if (card) card.classList.remove('drag-over');
}
function onDrop(e, target) {
  e.preventDefault();
  onDragLeave(e);
  if (!draggingId) return;
  const chip = document.getElementById(`chip-${draggingId}`);
  if (!chip) return;
  if (target === 'pool') {
    document.getElementById('pool').appendChild(chip);
  } else {
    const zone = document.getElementById(`zone-${target}`);
    if (zone) zone.appendChild(chip);
  }
  draggingId = null;
  updateAllCounters();
  markDirty();
}

// COUNTERS 
function updateAllCounters() {
  const poolChips = document.querySelectorAll('#pool .sample-chip');
  document.getElementById('poolCount').textContent = poolChips.length;

  document.querySelectorAll('.batch-card').forEach(card => {
    const bid   = card.dataset.batchId;
    const zone  = document.getElementById(`zone-${bid}`);
    if (!zone) return;
    const chips = zone.querySelectorAll('.sample-chip');
    const dna   = [...chips].filter(c => c.dataset.type === 'DNA').length;
    const rna   = [...chips].filter(c => c.dataset.type === 'RNA').length;
    const total = chips.length;

    document.getElementById(`dna-count-${bid}`).textContent   = `${dna} DNA`;
    document.getElementById(`rna-count-${bid}`).textContent   = `${rna} RNA`;
    document.getElementById(`total-count-${bid}`).textContent = `${total} / 60`;

    const hint = document.getElementById(`hint-${bid}`);
    if (hint) hint.style.display = total === 0 ? 'flex' : 'none';

    const meta = card.querySelector('.batch-meta');
    let warnEl = card.querySelector('.batch-pill-warn');
    if (total > 60) {
      if (!warnEl) { warnEl = document.createElement('span'); warnEl.className = 'batch-pill batch-pill-warn'; warnEl.textContent = 'Over 60'; meta.appendChild(warnEl); }
    } else if (warnEl) warnEl.remove();
  });
}

//  DIRTY 
function markDirty() {
  isDirty = true;
  document.getElementById('saveBar').classList.add('visible');
  document.getElementById('saveMsg').textContent = 'Unsaved changes';
  document.getElementById('saveMsg').className   = 'save-bar-msg dirty';
  document.getElementById('btnSave').disabled    = false;
}

//  ADD VIRTUAL BATCH 
// No API call, creates a card with a temporary negative ID.
// The real DB record is only created when the user saves.
document.getElementById('btnAddBatch').addEventListener('click', () => {
  virtualCounter++;
  const vid  = `v${virtualCounter}`;  // e.g. "v1", "v2" never a real PK
  const today = new Date().toISOString().slice(0,10);
  appendBatchCard(vid, `New Batch ${virtualCounter}`, today, true);
  markDirty();
});

function appendBatchCard(id, name, dateVal, isVirtual = false) {
  const grid = document.getElementById('batchesGrid');
  const card = document.createElement('div');
  card.className        = 'batch-card';
  card.id               = `batch-card-${id}`;
  card.dataset.batchId  = id;
  card.dataset.virtual  = isVirtual ? 'true' : 'false';
  card.innerHTML = `
    <div class="batch-card-header">
      <span class="batch-card-name${isVirtual ? ' virtual' : ''}" id="bname-${id}">
        ${isVirtual ? '⟳ ' + name : name}
      </span>
      <input type="date" class="batch-date-input" value="${dateVal}" onchange="markDirty()">
      <button class="batch-delete-btn" onclick="removeCard('${id}')" title="Remove batch">
        <i class="fas fa-trash-alt"></i>
      </button>
    </div>
    <div class="batch-meta">
      <span class="batch-pill batch-pill-dna"   id="dna-count-${id}">0 DNA</span>
      <span class="batch-pill batch-pill-rna"   id="rna-count-${id}">0 RNA</span>
      <span class="batch-pill batch-pill-total" id="total-count-${id}">0 / 60</span>
      ${isVirtual ? '<span class="batch-pill batch-pill-new">Unsaved</span>' : ''}
    </div>
    <div class="batch-drop-zone" id="zone-${id}" data-batch-id="${id}"
         ondragover="onDragOver(event)"
         ondrop="onDrop(event,'${id}')"
         ondragleave="onDragLeave(event)">
      <div class="drop-hint" id="hint-${id}">Drop samples here</div>
    </div>`;
  grid.appendChild(card);
}

//  REMOVE CARD (local only, no API) 
function removeCard(id) {
  const zone  = document.getElementById(`zone-${id}`);
  const chips = zone ? [...zone.querySelectorAll('.sample-chip')] : [];
  chips.forEach(chip => document.getElementById('pool').appendChild(chip));
  document.getElementById(`batch-card-${id}`)?.remove();
  updateAllCounters();
  markDirty();
}

// COLLECT STATE 
function collectBoardState() {
  const batches = [];
  document.querySelectorAll('.batch-card').forEach(card => {
    const bid     = card.dataset.batchId;
    const isVirt  = card.dataset.virtual === 'true';
    const dateInp = card.querySelector('.batch-date-input');
    const zone    = document.getElementById(`zone-${bid}`);
    const chips   = zone ? zone.querySelectorAll('.sample-chip') : [];
    batches.push({
      id:        isVirt ? null : parseInt(bid),
      date:      dateInp ? dateInp.value : new Date().toISOString().slice(0,10),
      sampleIds: [...chips].map(c => parseInt(c.dataset.id)),
    });
  });
  return batches;
}

//  DIFF MODAL 
async function openDiffModal() {
  document.getElementById('diffModal').classList.add('open');
  document.getElementById('diffContent').innerHTML =
    '<div style="text-align:center;padding:1.5rem;color:var(--text-muted);"><i class="fas fa-spinner fa-spin"></i> Calculating diff…</div>';
  document.getElementById('diffNotes').value = '';

  const res  = await fetch(DIFF_URL, {
    method: 'POST',
    headers: { 'Content-Type':'application/json', 'X-CSRFToken': CSRF_TOKEN },
    body: JSON.stringify({ batches: collectBoardState() }),
  });
  const data = await res.json();

  if (!data.ok) {
    document.getElementById('diffContent').innerHTML =
      `<div class="diff-empty">Could not calculate diff: ${data.error}</div>`;
    return;
  }

  renderDiff(data.changes);
}

function renderDiff(changes) {
  const el = document.getElementById('diffContent');
  if (!changes || changes.length === 0) {
    el.innerHTML = '<div class="diff-empty">No changes detected the board matches what\'s in the database.</div>';
    document.getElementById('btnConfirmSave').disabled = true;
    return;
  }
  document.getElementById('btnConfirmSave').disabled = false;

  const typeIcon = { create: '✦', modify: '✎', delete: '✕' };
  const typeColor = { create: 'var(--success)', modify: 'var(--accent)', delete: 'var(--danger)' };

  let html = '';
  changes.forEach(ch => {
    const icon  = typeIcon[ch.type]  || '·';
    const color = typeColor[ch.type] || 'var(--text-muted)';
    html += `<div class="diff-batch-block">
      <div class="diff-batch-name">
        <span style="color:${color};font-size:.9rem;">${icon}</span>
        ${ch.batch}
        ${ch.has_qc ? '<span class="batch-pill batch-pill-qc" style="font-size:.68rem;">Has QC</span>' : ''}
        ${ch.type === 'create' ? '<span class="batch-pill batch-pill-new" style="font-size:.68rem;">New</span>' : ''}
        ${ch.type === 'delete' ? '<span class="batch-pill" style="background:rgba(220,53,69,.1);color:var(--danger);font-size:.68rem;">Deleted</span>' : ''}
      </div>
      <div class="diff-rows">`;

    ch.added.forEach(name => {
      html += `<div class="diff-row diff-add"><i class="fas fa-plus" style="font-size:.68rem;width:10px;"></i> ${name}</div>`;
    });
    ch.removed.forEach(name => {
      html += `<div class="diff-row diff-rem"><i class="fas fa-minus" style="font-size:.68rem;width:10px;"></i> ${name}</div>`;
    });

    html += `</div></div>`;
  });

  el.innerHTML = html;
}

function closeDiffModal() {
  document.getElementById('diffModal').classList.remove('open');
}

async function confirmSave() {
  const btn = document.getElementById('btnConfirmSave');
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving…';

  const notes = document.getElementById('diffNotes').value.trim();

  try {
    const res  = await fetch(SAVE_URL, {
      method: 'POST',
      headers: { 'Content-Type':'application/json', 'X-CSRFToken': CSRF_TOKEN },
      body: JSON.stringify({ batches: collectBoardState(), notes }),
    });
    const data = await res.json();

    if (data.ok) {
      isDirty = false;
      closeDiffModal();
      document.getElementById('saveMsg').textContent = 'All changes saved';
      document.getElementById('saveMsg').className   = 'save-bar-msg saved';
      showToast('Board saved successfully', 'success');
      // Reload so batch names update from virtual → real
      setTimeout(() => location.reload(), 1200);
    } else {
      showToast(data.error || 'Save failed', 'error');
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-check"></i> Confirm & Save';
    }
  } catch (err) {
    showToast('Network error, please try again', 'error');
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-check"></i> Confirm & Save';
  }
}

document.getElementById('diffModal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeDiffModal();
});

// RECOMMEND MODAL 
document.getElementById('btnRecommend').addEventListener('click', () => {
  const list = document.getElementById('recList');
  list.innerHTML = '';
  if (RECOMMENDED.length === 0) {
    list.innerHTML = '<li style="color:var(--text-muted);font-size:.83rem;">No samples to split.</li>';
  } else {
    RECOMMENDED.forEach(rec => {
      const li = document.createElement('li');
      li.className = 'rec-item';
      li.innerHTML = `
        <span class="chip-type chip-type-${rec.type.toLowerCase()}">${rec.type}</span>
        <span class="rec-item-label">${rec.label}</span>
        <span class="rec-item-count">${rec.count} sample${rec.count!==1?'s':''}</span>`;
      list.appendChild(li);
    });
  }
  document.getElementById('recModal').classList.add('open');
});

function closeRecModal() { document.getElementById('recModal').classList.remove('open'); }

function applyRecommendation() {
  closeRecModal();
  // Return all chips to pool
  document.querySelectorAll('.batch-card').forEach(card => {
    const zone  = document.getElementById(`zone-${card.dataset.batchId}`);
    const chips = zone ? [...zone.querySelectorAll('.sample-chip')] : [];
    chips.forEach(chip => document.getElementById('pool').appendChild(chip));
    card.remove();
  });
  virtualCounter = 0;

  // Create virtual batches per recommendation
  RECOMMENDED.forEach((rec, idx) => {
    virtualCounter++;
    const vid   = `v${virtualCounter}`;
    const today = new Date().toISOString().slice(0,10);
    appendBatchCard(vid, rec.label, today, true);
    const zone  = document.getElementById(`zone-${vid}`);
    rec.sample_ids.forEach(sid => {
      const chip = document.getElementById(`chip-${sid}`);
      if (chip && zone) zone.appendChild(chip);
    });
  });

  updateAllCounters();
  markDirty();
  showToast('Recommendation applied, remember to Save', 'success');
}

document.getElementById('recModal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeRecModal();
});

// AUDIT LOG 
document.getElementById('btnAudit').addEventListener('click', async () => {
  const panel = document.getElementById('auditPanel');
  if (panel.style.display !== 'none') { panel.style.display = 'none'; return; }
  panel.style.display = 'block';
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });

  const res  = await fetch(AUDIT_URL);
  const data = await res.json();
  const cont = document.getElementById('auditEntries');

  if (!data.ok || data.log.length === 0) {
    cont.innerHTML = '<div style="padding:1.25rem;text-align:center;color:var(--text-muted);font-size:.83rem;">No audit entries yet.</div>';
    return;
  }

  cont.innerHTML = data.log.map((entry, i) => {
    const changes = entry.diff?.changes || [];
    const hasDetail = changes.length > 0;
    return `<div class="audit-entry">
      <div class="audit-meta">
        <span class="audit-action">${entry.action}</span>
        <span class="audit-user">${entry.performed_by}</span>
        <span class="audit-time">${entry.timestamp}</span>
        ${entry.notes ? `<span style="color:var(--text-muted);font-size:.75rem;font-style:italic;">"${entry.notes}"</span>` : ''}
        ${hasDetail ? `<span class="audit-diff-toggle" onclick="toggleDiff(${i})"><i class="fas fa-chevron-down"></i> Details</span>` : ''}
      </div>
      ${hasDetail ? `<div class="audit-diff-body" id="audit-diff-${i}">
        ${changes.map(ch => `
          <div style="margin-bottom:.5rem;">
            <strong>${ch.batch}</strong>
            ${ch.added?.map(n=>`<div style="color:var(--success);font-size:.76rem;">+ ${n}</div>`).join('')||''}
            ${ch.removed?.map(n=>`<div style="color:var(--danger);font-size:.76rem;">− ${n}</div>`).join('')||''}
          </div>`).join('')}
      </div>` : ''}
    </div>`;
  }).join('');
});

function toggleDiff(i) {
  const el = document.getElementById(`audit-diff-${i}`);
  el.classList.toggle('open');
}

//  POOL SEARCH & FILTER
const poolSearch = document.getElementById('poolSearch');
const filterBtns = document.querySelectorAll('.filter-btn');
let activeFilter = 'all';

poolSearch.addEventListener('input', applyPoolFilter);
filterBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    filterBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeFilter = btn.dataset.filter;
    applyPoolFilter();
  });
});

function applyPoolFilter() {
  const q = poolSearch.value.toLowerCase();
  document.querySelectorAll('#pool .sample-chip').forEach(chip => {
    const matchType = activeFilter === 'all' || chip.dataset.type === activeFilter;
    const matchText = chip.dataset.name.toLowerCase().includes(q) || chip.dataset.case.toLowerCase().includes(q);
    chip.classList.toggle('hidden', !(matchType && matchText));
  });
}

// TOAST 
function showToast(msg, type = '') {
  const wrap = document.getElementById('toastWrap');
  const el   = document.createElement('div');
  el.className = `toast ${type}`;
  const icon   = type==='success'?'fa-check-circle':type==='error'?'fa-times-circle':'fa-info-circle';
  el.innerHTML = `<i class="fas ${icon}"></i> ${msg}`;
  wrap.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function reloadPage() { location.reload(); }

// Init
updateAllCounters();