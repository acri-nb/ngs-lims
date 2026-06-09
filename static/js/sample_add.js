// CASE DATA from server 
let availableCases = [];   // populated after project is selected
let caseSelected   = false;

// AJAX: load cases when project changes 
document.getElementById('id_project').addEventListener('change', function() {
    const projectId  = this.value;
    const caseInput  = document.getElementById('case_input');
    const caseHidden = document.getElementById('case_name_hidden');

    // Reset case field
    caseInput.value  = '';
    caseHidden.value = '';
    caseSelected     = false;
    availableCases   = [];
    caseInput.classList.remove('case-selected');
    document.getElementById('clientHint').style.display = 'none';

    if (!projectId) { updatePreview(); return; }

    fetch(`${AJAX_CASES_URL}?project_id=${projectId}`)
        .then(r => r.json())
        .then(data => {
            availableCases = data.cases;   // [{case_id, case_name}, ...]
            if (data.client_name) {
                document.getElementById('clientName').textContent = data.client_name;
                document.getElementById('clientHint').style.display = '';
                document.getElementById('sum-client').textContent = data.client_name;
            }
            updatePreview();
        });
});

//CASE AUTOCOMPLETE 
function filterCases(val) {
    caseSelected = false;
    document.getElementById('case_name_hidden').value = val;   // allow free text too
    showCaseDropdown(val);
    updatePreview();
}

function showCaseDropdown(query) {
    const dropdown = document.getElementById('caseDropdown');
    const q        = (query || document.getElementById('case_input').value).toLowerCase().trim();
    const matches  = availableCases.filter(c => c.case_name.toLowerCase().includes(q));

    dropdown.innerHTML = '';

    // Existing matches
    matches.forEach(c => {
        const div = document.createElement('div');
        div.className = 'case-option';
        div.innerHTML = `<i class="fas fa-folder" style="color:var(--text-muted);font-size:0.75rem;"></i>${c.case_name}`;
        div.onmousedown = () => selectCase(c.case_name, true);
        dropdown.appendChild(div);
    });

    // "Create new" option — show if typed text doesn't exactly match an existing case
    const exactMatch = availableCases.some(c => c.case_name.toLowerCase() === q);
    if (q && !exactMatch) {
        const div = document.createElement('div');
        div.className = 'case-option create-new';
        div.innerHTML = `<i class="fas fa-plus-circle"></i> Create new case "<strong>${q}</strong>"`;
        div.onmousedown = () => selectCase(document.getElementById('case_input').value, false);
        dropdown.appendChild(div);
    }

    dropdown.style.display = (matches.length > 0 || (q && !exactMatch)) ? '' : 'none';
}

function selectCase(name, isExisting) {
    document.getElementById('case_input').value        = name;
    document.getElementById('case_name_hidden').value  = name;
    document.getElementById('caseDropdown').style.display = 'none';
    document.getElementById('case_input').classList.add('case-selected');

    const hint = document.getElementById('caseHint');
    if (isExisting) {
        hint.innerHTML = '<i class="fas fa-check-circle me-1" style="color:var(--success);"></i>Existing case selected.';
    } else {
        hint.innerHTML = '<i class="fas fa-plus-circle me-1" style="color:var(--accent);"></i>New case will be created and linked to this project\'s client.';
    }
    caseSelected = true;
    updatePreview();
}

function hideCaseDropdown() {
    // Small delay so onmousedown on options fires first
    setTimeout(() => {
        document.getElementById('caseDropdown').style.display = 'none';
    }, 150);
}

// LIVE PREVIEW
function updatePreview() {
    const projectSel  = document.getElementById('id_project');
    const caseText    = document.getElementById('case_input').value.trim();
    const specimenSel = document.getElementById('id_specimen_type');
    const typeChecked = document.querySelector('.type-radio:checked');
    const locationSel = document.querySelector('[name="location"]');
    const concInput   = document.querySelector('[name="concentration"]');
    const volInput    = document.querySelector('[name="volume_received"]');

    const projectText  = projectSel.options[projectSel.selectedIndex]?.text || '—';
    const specimenText = specimenSel.options[specimenSel.selectedIndex]?.text;
    const typeText     = typeChecked?.value;
    const locationText = locationSel.options[locationSel.selectedIndex]?.text || '—';

    document.getElementById('sum-project').textContent  =
        projectText === '— Select project —' ? '—' : projectText;
    document.getElementById('sum-case').textContent     = caseText     || '—';
    document.getElementById('sum-specimen').textContent = specimenText || '—';
    document.getElementById('sum-type').textContent     = typeText     || '—';
    document.getElementById('sum-location').textContent =
        locationText === '— None —' ? '—' : locationText;
    document.getElementById('sum-conc').textContent =
        concInput.value ? `${concInput.value} ng/µL` : '—';
    document.getElementById('sum-vol').textContent =
        volInput.value ? `${volInput.value} µL` : '—';

    // Name preview
    const preview = document.getElementById('namePreviewValue');
    if (caseText && specimenText && specimenText !== '— Select specimen type —' && typeText) {
        preview.textContent = `${caseText}-${specimenText}-${typeText}-?????`;
        preview.classList.remove('placeholder');
    } else {
        preview.textContent = '—';
        preview.classList.add('placeholder');
    }

    // Enable submit
    const ready = projectSel.value && caseText && specimenSel.value && typeText;
    document.getElementById('submitBtn').disabled = !ready;
}

// Attach listeners
document.getElementById('id_specimen_type').addEventListener('change', updatePreview);
document.querySelectorAll('.type-radio').forEach(r => r.addEventListener('change', updatePreview));
document.querySelectorAll('[name="concentration"], [name="volume_received"]').forEach(i =>
    i.addEventListener('input', updatePreview)
);
document.querySelector('[name="location"]').addEventListener('change', updatePreview);