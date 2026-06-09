
function updateSuppliers() {
    const sel     = document.getElementById('productSelect');
    const opt     = sel.options[sel.selectedIndex];
    const pid     = parseInt(sel.value);
    const supSel  = document.getElementById('supplierSelect');
    const opts    = supSel.querySelectorAll('.supplier-opt');
    const refNum  = opt ? opt.dataset.ref : '';

    // Show ref number
    if (pid && refNum) {
        document.getElementById('refNum').textContent = refNum;
        document.getElementById('refPreview').style.display = '';
    } else {
        document.getElementById('refPreview').style.display = 'none';
    }

    // Filter suppliers
    const validIds = supplierMap[pid] || [];
    supSel.value = '';
    supSel.options[0].text = validIds.length ? '— Select supplier —' : '— No suppliers linked —';
    opts.forEach(o => {
        const show = validIds.includes(parseInt(o.value));
        o.style.display = show ? '' : 'none';
    });

    // Auto-select if only one supplier
    const visible = [...opts].filter(o => o.style.display !== 'none');
    if (visible.length === 1) supSel.value = visible[0].value;

    updateSummary();
}

// UNIT PICKER
function selectUnit(val, btn, isCustom) {
    if (!isCustom) {
        document.querySelectorAll('.unit-btn').forEach(b => b.classList.remove('active'));
        document.getElementById('customUnit').value = '';
        if (btn) btn.classList.add('active');
    }
    document.getElementById('unitHidden').value = val;
    updatePreview();
    updateSummary();
}

function updatePreview() {
    const qty  = document.getElementById('qtyInput').value;
    const unit = document.getElementById('unitHidden').value;
    const prev = document.getElementById('unitPreview');
    const text = document.getElementById('unitPreviewText');
    if (qty && unit) {
        text.textContent = `${qty} ${unit}`;
        prev.style.display = '';
    } else {
        prev.style.display = 'none';
    }
}

// LIVE SUMMARY SIDEBAR 
function updateSummary() {
    const productSel  = document.getElementById('productSelect');
    const supplierSel = document.getElementById('supplierSelect');
    const qty         = document.getElementById('qtyInput').value;
    const unit        = document.getElementById('unitHidden').value;
    const locationSel = document.querySelector('[name="location"]');
    const expiryIn    = document.querySelector('[name="expiration_date"]');
    const condChecked = document.querySelector('[name="receiving_condition"]:checked');

    const productText  = productSel.options[productSel.selectedIndex]?.text  || '—';
    const supplierText = supplierSel.options[supplierSel.selectedIndex]?.text || '—';
    const locationText = locationSel.options[locationSel.selectedIndex]?.text || '—';
    const expiryText   = expiryIn.value ? new Date(expiryIn.value).toLocaleDateString('en-US', {month:'short',day:'numeric',year:'numeric'}) : 'No expiry';
    const condText     = condChecked ? condChecked.value : '—';

    document.getElementById('sum-product').textContent   = productText === '— Select product —' ? '—' : productText;
    document.getElementById('sum-supplier').textContent  = supplierText === '— Select supplier —' ? '—' : supplierText;
    document.getElementById('sum-qty').textContent       = (qty && unit) ? `${qty} ${unit}` : '—';
    document.getElementById('sum-condition').textContent = condText;
    document.getElementById('sum-location').textContent  = locationText === '— Select location —' ? '—' : locationText;
    document.getElementById('sum-expiry').textContent    = expiryText;

    // Enable submit if required fields filled
    const ready = productSel.value && supplierSel.value && qty && unit &&
                  document.querySelector('[name="lot_number"]').value &&
                  locationSel.value &&
                  document.querySelector('[name="date_received"]').value;
    document.getElementById('submitBtn').disabled = !ready;
}

// Attach live updates to all inputs
document.querySelectorAll('input, select').forEach(el => {
    el.addEventListener('input',  updateSummary);
    el.addEventListener('change', updateSummary);
});
document.getElementById('qtyInput').addEventListener('input', () => {
    updatePreview();
    updateSummary();
});