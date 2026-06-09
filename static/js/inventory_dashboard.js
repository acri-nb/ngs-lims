// TAB SWITCHING
function showTab(name, btn) {
    document.querySelectorAll('.tab-pane').forEach(p => p.style.display = 'none');
    document.querySelectorAll('.inv-tab').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-' + name).style.display = '';
    btn.classList.add('active');
}

// STOCK FILTER 
let activeStatusFilter = 'all';

function toggleChip(btn, filter) {
    document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    activeStatusFilter = filter;
    filterStock();
}

function filterStock() {
    const q   = document.getElementById('stockSearch').value.toLowerCase();
    const loc = document.getElementById('stockLocation').value.toLowerCase();
    document.querySelectorAll('.stock-row').forEach(row => {
        const matchText   = row.dataset.name.includes(q) || row.dataset.lot.includes(q);
        const matchLoc    = !loc || row.dataset.loc.toLowerCase() === loc;
        const status      = row.dataset.status;
        const expired     = row.dataset.expired === 'true';
        let   matchStatus = true;
        if (activeStatusFilter === 'low')     matchStatus = status === 'low' || status === 'critical';
        if (activeStatusFilter === 'expired') matchStatus = expired;
        if (activeStatusFilter === 'ok')      matchStatus = status === 'ok' && !expired;
        row.style.display = (matchText && matchLoc && matchStatus) ? '' : 'none';
    });
}

// RECEIPT SEARCH 
function filterReceipts() {
    const q = document.getElementById('receiptSearch').value.toLowerCase();
    document.querySelectorAll('.receipt-row').forEach(row => {
        const match = row.dataset.name.includes(q) ||
                      row.dataset.lot.includes(q) ||
                      row.dataset.supplier.includes(q);
        row.style.display = match ? '' : 'none';
    });
}

// PRODUCT SEARCH 
function filterProducts() {
    const q = document.getElementById('productSearch').value.toLowerCase();
    document.querySelectorAll('.product-row').forEach(row => {
        row.style.display = (row.dataset.name.includes(q) || row.dataset.ref.includes(q)) ? '' : 'none';
    });
}

// SUPPLIER SEARCH
function filterSuppliers() {
    const q = document.getElementById('supplierSearch').value.toLowerCase();
    document.querySelectorAll('.supplier-card-wrap').forEach(card => {
        card.style.display = (card.dataset.name.includes(q) || card.dataset.contact.includes(q)) ? '' : 'none';
    });
}