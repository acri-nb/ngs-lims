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

function selectRack(btnEl) {
  if (btnEl.disabled) return;

  document.querySelectorAll('.nb-rack-card.nb-rack-selected')
    .forEach(b => b.classList.remove('nb-rack-selected'));
  btnEl.classList.add('nb-rack-selected');

  const rackPk   = btnEl.dataset.rackId;
  const rackName = btnEl.dataset.rackName;

  window.selectedRackId   = null;   // not final until a slot is picked
  window.selectedRackSlot = null;
  document.getElementById('selectedSlotDisplay').style.display = 'none';
  document.getElementById('locationNextBtn').disabled = true;

  updateSlotGrid(rackPk, rackName);
}

async function updateSlotGrid(rackPk, rackName) {
  const slotGrid = document.getElementById('slotGrid');
  slotGrid.innerHTML = '<span style="font-size:.78rem;color:var(--text-muted);">Loading occupancy…</span>';

  let data;
  try {
    const resp = await fetch(`/locations/rack/${rackPk}/slots/`);
    data = await resp.json();
  } catch (err) {
    slotGrid.innerHTML = '<span style="font-size:.78rem;color:var(--danger);">Could not load rack occupancy.</span>';
    return;
  }

  const occBySlot = {};
  data.slots.forEach(s => { occBySlot[s.slot] = s; });

  slotGrid.innerHTML = '';
  const grid = document.createElement('div');
  grid.className = 'nb-slot-inner-grid';

  data.rows.forEach(row => {
    data.cols.forEach(col => {
      ['T', 'B'].forEach(side => {
        const slot = `${row}${col}${side}`;
        const info = occBySlot[slot];
        const btn  = document.createElement('button');
        btn.type = 'button';
        btn.textContent = slot;
        btn.className = 'nb-slot-btn ' + (info && info.occupied ? 'nb-slot-taken' : 'nb-slot-free');

        if (info && info.occupied) {
          btn.disabled = true;
          btn.title = `Occupied by ${info.plate_name}`;
        } else {
          btn.title = 'Available';
          btn.onclick = () => selectSlot(rackPk, rackName, slot, btn);
        }
        grid.appendChild(btn);
      });
    });
  });

  slotGrid.appendChild(grid);
}

function selectSlot(rackPk, rackName, slot, btnEl) {
  document.querySelectorAll('.nb-slot-btn.nb-slot-selected')
    .forEach(b => b.classList.remove('nb-slot-selected'));
  btnEl.classList.add('nb-slot-selected');

  window.selectedRackId   = rackPk;
  window.selectedRackSlot = slot;

  document.getElementById('selectedSlotDisplay').style.display = 'block';
  document.getElementById('selectedSlotLabel').textContent = `${rackName} — ${slot}`;
  document.getElementById('locationNextBtn').disabled = false;
}
function selectSlot(rackPk, rackName, slot, btnEl) {
  document.querySelectorAll('.nb-slot-btn.nb-slot-selected')
    .forEach(b => b.classList.remove('nb-slot-selected'));
  btnEl.classList.add('nb-slot-selected');

  window.selectedRackId   = rackPk;
  window.selectedRackSlot = slot;

  document.getElementById('selectedSlotDisplay').style.display = 'block';
  document.getElementById('selectedSlotLabel').textContent = `${rackName} — ${slot}`;
  document.getElementById('locationNextBtn').disabled = false;
}

// CONFIRM MODAL
async function openConfirmModal() {
  const placements  = collectPlacements();
  const workflowId  = document.getElementById('workflowSelect').value;

  const params = new URLSearchParams();
  params.append('workflow_type_id', workflowId);
  params.append('placements', JSON.stringify(placements));

  const resp = await fetch(`{% url 'libprep-check-batch' project.pk %}`, {
    method: 'POST',
    headers: {
      'X-CSRFToken': getCookie('csrftoken'),
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: params,
  });
  const data = await resp.json();

  if (!data.ok) {
    alert('This batch doesn\'t look right:\n\n' + data.errors.join('\n'));
    return;
  }

  document.getElementById('locationModal').style.display = 'none';
  document.getElementById('confirmModal').style.display  = 'flex';
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