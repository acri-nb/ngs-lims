// static/js/samples.js

//  ROW CLICK → navigate to detail
function handleRowClick(e, row) {
    if (e.target.type === 'checkbox') return;
    const id = row.dataset.id;
    window.location = `/samples/${id}/`;
}

// SELECT ALL 
function toggleAll(master) {
    document.querySelectorAll('.row-check').forEach(cb => cb.checked = master.checked);
    updateBulkBar();
}

// UPDATE BULK BAR 
function updateBulkBar() {
    const checked = document.querySelectorAll('.row-check:checked');
    const bar     = document.getElementById('bulkBar');
    document.getElementById('bulkCount').textContent = `${checked.length} selected`;
    bar.style.display = checked.length > 0 ? 'flex' : 'none';
    document.getElementById('selectAll').indeterminate =
        checked.length > 0 && checked.length < document.querySelectorAll('.row-check').length;
    document.getElementById('selectAll').checked = checked.length === document.querySelectorAll('.row-check').length;
}

function clearSelection() {
    document.querySelectorAll('.row-check, #selectAll').forEach(cb => cb.checked = false);
    updateBulkBar();
}

// BULK ACTION
function bulkAction(action) {
    const checked = document.querySelectorAll('.row-check:checked');
    if (!checked.length) return;
    document.getElementById('bulkActionInput').value = action;
    document.getElementById('bulkForm').submit();
}

//  EXPORT SELECTED AS CSV
function exportSelected() {
    const ids = [...document.querySelectorAll('.row-check:checked')].map(cb => cb.value);
    if (!ids.length) return;
    window.location = `/samples/export/?ids=${ids.join(',')}`;
}

// COLUMN VISIBILITY TOGGLE 
document.querySelectorAll('.col-toggle').forEach(cb => {
    cb.addEventListener('change', function() {
        const col = parseInt(this.dataset.col);
        const show = this.checked;
        // toggle nth-child column (header + all rows)
        document.querySelectorAll( 
            `#sampleTable thead tr th:nth-child(${col}),
             #sampleTable tbody tr td:nth-child(${col})`
        ).forEach(cell => cell.style.display = show ? '' : 'none');
    });
});