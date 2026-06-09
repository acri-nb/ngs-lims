document.querySelector('form').addEventListener('submit', function(e) {
    let errors = [];

    document.querySelectorAll('[name^="current_temp_"]').forEach(input => {
        const pk = input.name.replace('current_temp_', '');
        const current = parseFloat(input.value);
        const max     = parseFloat(document.querySelector(`[name="max_temp_${pk}"]`)?.value);
        const min     = parseFloat(document.querySelector(`[name="min_temp_${pk}"]`)?.value);
        const name    = input.closest('.loc-card')?.querySelector('.loc-name')?.textContent?.trim();

        if (!isNaN(current) && !isNaN(min) && min > current)
            errors.push(`${name}: Min (${min}) > Current (${current})`);
        if (!isNaN(current) && !isNaN(max) && current > max)
            errors.push(`${name}: Current (${current}) > Max (${max})`);
        if (!isNaN(min) && !isNaN(max) && min > max)
            errors.push(`${name}: Min (${min}) > Max (${max})`);
    });

    if (errors.length > 0) {
        e.preventDefault();
        alert('Please fix these temperature values before saving:\n\n' + errors.join('\n'));
    }
});