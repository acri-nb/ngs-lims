// STATE
const placements = {};
let dragMeta     = null;
let selectedRackId   = null;
let selectedRackName = null;
let selectedSlot     = null;

// Workflow → hide/show controls 
const workflowSel = document.getElementById('workflowSelect');
const controlsBox = document.getElementById('controlsBox');
workflowSel.addEventListener('change', () => {
  const opt  = workflowSel.options[workflowSel.selectedIndex];
  const type = opt ? opt.dataset.type : '';
  controlsBox.style.display = type === 'DNA' ? 'none' : '';
});

// DRAG — SIDEBAR → WELL
function onDragStart(event) {
  const card = event.currentTarget;
  dragMeta = {
    source:     'sidebar',
    sourcePos:  null,
    qcId:       card.dataset.qcId,
    sampleName: card.dataset.sampleName,
    status:     card.dataset.status,
    isControl:  card.dataset.isControl === 'true',
    cardEl:     card,
  };
  event.dataTransfer.effectAllowed = 'move';
  event.dataTransfer.setData('text/plain', card.dataset.qcId);
  card.classList.add('nb-card-dragging');
}
document.addEventListener('dragend', () => {
  if (dragMeta?.cardEl) dragMeta.cardEl.classList.remove('nb-card-dragging');
});

// DRAG — WELL → WELL or WELL → SIDEBAR
function onWellDragStart(event) {
  const well = event.currentTarget;
  if (!well.classList.contains('nb-well-occupied')) { event.preventDefault(); return; }
  const pos  = well.dataset.pos;
  const info = placements[pos];
  if (!info) { event.preventDefault(); return; }
  dragMeta = {
    source: 'well', sourcePos: pos,
    qcId: info.qcId, sampleName: info.sampleName,
    status: info.status, isControl: info.isControl, cardEl: null,
  };
  event.dataTransfer.effectAllowed = 'move';
  event.dataTransfer.setData('text/plain', info.qcId);
  well.classList.add('nb-card-dragging');
}

// WELL DROP
function onDragOver(e)  { e.preventDefault(); e.currentTarget.classList.add('nb-well-dragover'); }
function onDragLeave(e) { e.currentTarget.classList.remove('nb-well-dragover'); }

function onDrop(event) {
  event.preventDefault();
  const targetWell = event.currentTarget;
  targetWell.classList.remove('nb-well-dragover');
  if (!dragMeta) return;

  const targetPos  = targetWell.dataset.pos;
  const isOccupied = targetWell.classList.contains('nb-well-occupied');

  // Well-to-well swap
  if (isOccupied && dragMeta.source === 'well' && dragMeta.sourcePos !== targetPos) {
    const displaced = { ...placements[targetPos] };
    _placeInWell(dragMeta.sourcePos, displaced);
    _placeInWell(targetPos, { qcId: dragMeta.qcId, sampleName: dragMeta.sampleName, status: dragMeta.status, isControl: dragMeta.isControl });
    document.querySelector(`.nb-well[data-pos="${dragMeta.sourcePos}"]`)?.classList.remove('nb-card-dragging');
    dragMeta = null;
    updateStats();
    return;
  }

  // From another well — vacate source
  if (dragMeta.source === 'well' && dragMeta.sourcePos) {
    const src = document.querySelector(`.nb-well[data-pos="${dragMeta.sourcePos}"]`);
    if (src) { src.classList.remove('nb-card-dragging'); _clearWellVisuals(src, true); }
    delete placements[dragMeta.sourcePos];
  } else if (dragMeta.source === 'sidebar' && !dragMeta.isControl) {
    // Remove from previous well if already placed
    const existing = Object.entries(placements).find(([,v]) => v.qcId === dragMeta.qcId);
    if (existing) {
      const old = document.querySelector(`.nb-well[data-pos="${existing[0]}"]`);
      if (old) _clearWellVisuals(old, true);
      delete placements[existing[0]];
    }
    if (dragMeta.cardEl) {
      dragMeta.cardEl.classList.add('nb-card-placed');
      dragMeta.cardEl.setAttribute('draggable', 'false');
    }
  }

  _placeInWell(targetPos, { qcId: dragMeta.qcId, sampleName: dragMeta.sampleName, status: dragMeta.status, isControl: dragMeta.isControl });
  dragMeta = null;
  updateStats();
}

// SIDEBAR DROP (drag back from well)
function onListDragOver(e)  { e.preventDefault(); e.currentTarget.classList.add('nb-list-dragover'); }
function onListDragLeave(e) { e.currentTarget.classList.remove('nb-list-dragover'); }
function onListDrop(event) {
  event.preventDefault();
  event.currentTarget.classList.remove('nb-list-dragover');
  if (!dragMeta || dragMeta.source !== 'well' || dragMeta.isControl) return;
  const src = document.querySelector(`.nb-well[data-pos="${dragMeta.sourcePos}"]`);
  if (src) _clearWellVisuals(src, true);
  delete placements[dragMeta.sourcePos];
  const card = document.getElementById('card-' + dragMeta.qcId);
  if (card) { card.classList.remove('nb-card-placed', 'nb-card-dragging'); card.setAttribute('draggable', 'true'); }
  dragMeta = null;
  updateStats();
}

// HELPERS
function _placeInWell(pos, info) {
  placements[pos] = info;
  const well = document.querySelector(`.nb-well[data-pos="${pos}"]`);
  if (!well) return;
  well.className = `nb-well nb-well-occupied nb-well-${info.status}`;
  well.setAttribute('draggable', 'true');
  well.querySelector('.nb-well-name').textContent = info.sampleName;
  well.dataset.qcId = info.qcId;
}

function _clearWellVisuals(well, removePlacement) {
  const pos  = well.dataset.pos;
  const info = placements[pos];
  if (info && !info.isControl) {
    const card = document.getElementById('card-' + info.qcId);
    if (card) { card.classList.remove('nb-card-placed'); card.setAttribute('draggable', 'true'); }
  }
  if (removePlacement) delete placements[pos];
  well.className = 'nb-well nb-well-empty';
  well.setAttribute('draggable', 'false');
  well.querySelector('.nb-well-name').textContent = '';
  delete well.dataset.qcId;
}

function clearPlate() {
  document.querySelectorAll('.nb-well-occupied').forEach(w => _clearWellVisuals(w, true));
  document.querySelectorAll('.nb-card-placed').forEach(c => {
    c.classList.remove('nb-card-placed'); c.setAttribute('draggable', 'true');
  });
  updateStats();
}

function updateStats() {
  const count = Object.keys(placements).length;
  document.getElementById('statCount').textContent = count;
  document.getElementById('saveBtn').disabled = count === 0;
}

// LOCATION MODAL
function openLocationModal() {
  const workflow = document.getElementById('workflowSelect');
  const dt       = document.getElementById('datePrepInput').value;
  if (!workflow.value) { alert('Please select a Workflow Type first.'); workflow.focus(); return; }
  if (!dt)             { alert('Please enter a Date Prepped first.'); return; }
  document.getElementById('locationModal').style.display = 'flex';
}
function closeLocationModal() {
  document.getElementById('locationModal').style.display = 'none';
}

function updateSlotGrid() {
  const sel   = document.getElementById('rackSelect');
  const opt   = sel.options[sel.selectedIndex];
  const grid  = document.getElementById('slotGrid');
  const nextBtn = document.getElementById('locationNextBtn');

  selectedRackId   = sel.value || null;
  selectedRackName = opt ? opt.text : '';
  selectedSlot     = null;
  nextBtn.disabled = true;
  document.getElementById('selectedSlotDisplay').style.display = 'none';

  if (!sel.value) {
    grid.innerHTML = '<span style="font-size:.78rem;color:var(--text-muted);">Select a rack first</span>';
    return;
  }

  const rows = parseInt(opt.dataset.rows) || 4;
  const cols = parseInt(opt.dataset.cols) || 4;
  const rowLetters = 'ABCDEFGHIJKLMNOP'.slice(0, rows);

  let html = '<div class="nb-slot-table">';
  // Header row
  html += '<div class="nb-slot-row"><div class="nb-slot-cell nb-slot-hdr"></div>';
  for (let c = 1; c <= cols; c++) html += `<div class="nb-slot-cell nb-slot-hdr">${c}</div>`;
  html += '</div>';
  // Data rows
  for (const r of rowLetters) {
    html += `<div class="nb-slot-row"><div class="nb-slot-cell nb-slot-row-lbl">${r}</div>`;
    for (let c = 1; c <= cols; c++) {
      const base = `${r}${c}`;
      html += `
        <div class="nb-slot-cell nb-slot-group">
          <button class="nb-slot-btn" data-slot="${base}T" onclick="selectSlot('${base}T', '${base} Top', this)">T</button>
          <button class="nb-slot-btn" data-slot="${base}B" onclick="selectSlot('${base}B', '${base} Bottom', this)">B</button>
        </div>`;
    }
    html += '</div>';
  }
  html += '</div>';
  grid.innerHTML = html;
}

function selectSlot(slotCode, slotLabel, btn) {
  // Deselect all
  document.querySelectorAll('.nb-slot-btn').forEach(b => b.classList.remove('nb-slot-btn-active'));
  btn.classList.add('nb-slot-btn-active');
  selectedSlot = slotCode;
  document.getElementById('selectedSlotLabel').textContent = slotLabel;
  document.getElementById('selectedSlotDisplay').style.display = '';
  document.getElementById('locationNextBtn').disabled = false;
}

// CONFIRM MODAL
function openConfirmModal() {
  if (!selectedRackId || !selectedSlot) return;
  closeLocationModal();

  const workflow = document.getElementById('workflowSelect');
  const dt       = document.getElementById('datePrepInput').value;
  const count    = Object.keys(placements).length;

  document.getElementById('cWorkflow').textContent  = workflow.options[workflow.selectedIndex].text;
  document.getElementById('cDate').textContent      = dt;
  document.getElementById('cCount').textContent     = count + ' well' + (count !== 1 ? 's' : '');
  document.getElementById('cLocation').textContent  = `${selectedRackName} · ${selectedSlot}`;

  document.getElementById('confirmModal').style.display = 'flex';
}

function backToLocation() {
  document.getElementById('confirmModal').style.display = 'none';
  document.getElementById('locationModal').style.display = 'flex';
}

function confirmSave() {
  document.getElementById('fWorkflow').value   = document.getElementById('workflowSelect').value;
  document.getElementById('fDate').value       = document.getElementById('datePrepInput').value;
  document.getElementById('fNotes').value      = document.getElementById('notesInput').value;
  document.getElementById('fPlacements').value = JSON.stringify(placements);
  document.getElementById('fRackId').value     = selectedRackId;
  document.getElementById('fRackSlot').value   = selectedSlot;
  document.getElementById('batchForm').submit();
}

// Close modals on backdrop click
['locationModal','confirmModal'].forEach(id => {
  document.getElementById(id).addEventListener('click', function(e) {
    if (e.target === this) this.style.display = 'none';
  });
});