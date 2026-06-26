
// STATE
// placements: { wellPos → { qcId, sampleName, status, isControl } }
const placements = {};

// What is currently being dragged:
//   source = 'sidebar' | 'well'
//   sourcePos = well pos if from well, null if from sidebar
let dragMeta = null;

// WORKFLOW SELECT: show/hide controls box 
const workflowSel = document.getElementById('workflowSelect');
const controlsBox = document.getElementById('controlsBox');

function updateControlsVisibility() {
  const opt = workflowSel.options[workflowSel.selectedIndex];
  const type = opt ? opt.dataset.type : '';
  // Hide controls for DNA workflows
  controlsBox.style.display = (type === 'DNA') ? 'none' : '';
}
workflowSel.addEventListener('change', updateControlsVisibility);
updateControlsVisibility();


// DRAG FROM SIDEBAR CARD
function onDragStart(event) {
  const card  = event.currentTarget;
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


// DRAG FROM A WELL (well-to-well or well-to-sidebar)
function onWellDragStart(event) {
  const well = event.currentTarget;
  if (!well.classList.contains('nb-well-occupied')) {
    event.preventDefault();
    return;
  }
  const pos  = well.dataset.pos;
  const info = placements[pos];
  if (!info) { event.preventDefault(); return; }

  dragMeta = {
    source:     'well',
    sourcePos:  pos,
    qcId:       info.qcId,
    sampleName: info.sampleName,
    status:     info.status,
    isControl:  info.isControl,
    cardEl:     null,
  };
  well.setAttribute('draggable', 'true');
  event.dataTransfer.effectAllowed = 'move';
  event.dataTransfer.setData('text/plain', info.qcId);
  well.classList.add('nb-card-dragging');
}

// WELL DROP 
function onDragOver(event) {
  event.preventDefault();
  event.currentTarget.classList.add('nb-well-dragover');
}
function onDragLeave(event) {
  event.currentTarget.classList.remove('nb-well-dragover');
}

function onDrop(event) {
  event.preventDefault();
  const targetWell = event.currentTarget;
  targetWell.classList.remove('nb-well-dragover');
  if (!dragMeta) return;

  const targetPos  = targetWell.dataset.pos;
  const isOccupied = targetWell.classList.contains('nb-well-occupied');

  // Swap if target is already occupied 
  if (isOccupied && dragMeta.source === 'well' && dragMeta.sourcePos !== targetPos) {
    const displaced = { ...placements[targetPos] };
    // Put displaced sample into the source well
    _placeInWell(dragMeta.sourcePos, displaced);
    // Put dragged sample into target well
    _placeInWell(targetPos, {
      qcId:       dragMeta.qcId,
      sampleName: dragMeta.sampleName,
      status:     dragMeta.status,
      isControl:  dragMeta.isControl,
    });
    _clearWellVisuals(document.querySelector(`.nb-well[data-pos="${dragMeta.sourcePos}"]`), false);
    dragMeta = null;
    updateStats();
    return;
  }

  // If dragging from another well, vacate it first 
  if (dragMeta.source === 'well' && dragMeta.sourcePos) {
    const srcWell = document.querySelector(`.nb-well[data-pos="${dragMeta.sourcePos}"]`);
    if (srcWell) _clearWellVisuals(srcWell, true);
    delete placements[dragMeta.sourcePos];
  } else if (dragMeta.source === 'sidebar') {
    // Mark sidebar card as placed (non-controls only; controls are reusable)
    if (!dragMeta.isControl) {
      // Check if this sample is already on the plate — remove it first
      const existing = Object.entries(placements).find(([,v]) => v.qcId === dragMeta.qcId);
      if (existing) {
        const oldWell = document.querySelector(`.nb-well[data-pos="${existing[0]}"]`);
        if (oldWell) _clearWellVisuals(oldWell, true);
        delete placements[existing[0]];
      }
      if (dragMeta.cardEl) {
        dragMeta.cardEl.classList.add('nb-card-placed');
        dragMeta.cardEl.setAttribute('draggable', 'false');
      }
    }
  }

  // Place in target well 
  _placeInWell(targetPos, {
    qcId:       dragMeta.qcId,
    sampleName: dragMeta.sampleName,
    status:     dragMeta.status,
    isControl:  dragMeta.isControl,
  });

  dragMeta = null;
  updateStats();
}


function onListDragOver(event) {
  event.preventDefault();
  event.currentTarget.classList.add('nb-list-dragover');
}
function onListDragLeave(event) {
  event.currentTarget.classList.remove('nb-list-dragover');
}
function onListDrop(event) {
  event.preventDefault();
  event.currentTarget.classList.remove('nb-list-dragover');
  if (!dragMeta || dragMeta.source !== 'well' || dragMeta.isControl) return;

  // Remove from well
  const srcWell = document.querySelector(`.nb-well[data-pos="${dragMeta.sourcePos}"]`);
  if (srcWell) _clearWellVisuals(srcWell, true);
  delete placements[dragMeta.sourcePos];

  // Restore sidebar card
  const card = document.getElementById('card-' + dragMeta.qcId);
  if (card) {
    card.classList.remove('nb-card-placed', 'nb-card-dragging');
    card.setAttribute('draggable', 'true');
  }

  dragMeta = null;
  updateStats();
}


// HELPERS

function _placeInWell(pos, info) {
  placements[pos] = info;
  const well = document.querySelector(`.nb-well[data-pos="${pos}"]`);
  if (!well) return;
  well.classList.remove('nb-well-empty');
  well.classList.add('nb-well-occupied', `nb-well-${info.status}`);
  well.setAttribute('draggable', 'true');
  well.querySelector('.nb-well-name').textContent = info.sampleName;
  well.dataset.qcId = info.qcId;
  // Remove stale state classes
  well.classList.remove('nb-card-dragging');
}

function _clearWellVisuals(well, removePlacement) {
  const pos   = well.dataset.pos;
  const info  = placements[pos];

  // If a non-control sidebar card was the source, unplace it
  if (info && !info.isControl) {
    const card = document.getElementById('card-' + info.qcId);
    if (card) {
      card.classList.remove('nb-card-placed');
      card.setAttribute('draggable', 'true');
    }
  }
  if (removePlacement) delete placements[pos];

  well.className = 'nb-well nb-well-empty';
  well.setAttribute('draggable', 'false');
  well.querySelector('.nb-well-name').textContent = '';
  delete well.dataset.qcId;
}


// CLEAR ALL
function clearPlate() {
  document.querySelectorAll('.nb-well-occupied').forEach(w => _clearWellVisuals(w, true));
  // Re-enable all sidebar cards
  document.querySelectorAll('.nb-card-placed').forEach(c => {
    c.classList.remove('nb-card-placed');
    c.setAttribute('draggable', 'true');
  });
  updateStats();
}

// STATS
function updateStats() {
  const count = Object.keys(placements).length;
  document.getElementById('statCount').textContent = count;
  document.getElementById('saveBtn').disabled = count === 0;
}


function saveBatch() {
  const workflow = document.getElementById('workflowSelect');
  const dt       = document.getElementById('datePrepInput').value;

  if (!workflow.value) {
    alert('Please select a Workflow Type before saving.');
    workflow.focus();
    return;
  }
  if (!dt) {
    alert('Please enter a Date Prepped before saving.');
    return;
  }

  const count  = Object.keys(placements).length;
  const wfText = workflow.options[workflow.selectedIndex].text;

  document.getElementById('mCount').textContent    = count;
  document.getElementById('mWorkflow').textContent = wfText;
  document.getElementById('mDate').textContent     = dt;
  document.getElementById('modalBackdrop').style.display = 'flex';
}

function closeModal() {
  document.getElementById('modalBackdrop').style.display = 'none';
}

function confirmSave() {
  document.getElementById('fWorkflow').value  = document.getElementById('workflowSelect').value;
  document.getElementById('fDate').value      = document.getElementById('datePrepInput').value;
  document.getElementById('fNotes').value     = document.getElementById('notesInput').value;
  document.getElementById('fPlacements').value = JSON.stringify(placements);
  document.getElementById('batchForm').submit();
}

document.getElementById('modalBackdrop').addEventListener('click', function(e) {
  if (e.target === this) closeModal();
});