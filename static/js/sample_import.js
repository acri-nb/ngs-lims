// 


function previewFile(input) {
    const file = input.files[0];
    if (!file) return;

    const zone = document.getElementById('dropZone');
    const icon = document.getElementById('dropIcon');
    const text = document.getElementById('dropText');
    const sub  = document.getElementById('dropSub');
    const chip = document.getElementById('fileChip');
    const lbl  = document.getElementById('browseLabel');

    zone.classList.add('drop-zone--loaded');

    if (icon) {
        icon.classList.remove('fa-cloud-upload-alt');
        icon.classList.add('fa-check-circle');
    }

    text.textContent = file.name;
    sub.textContent  = (file.size / 1024).toFixed(1) + ' KB';
    chip.style.display = 'block';
    chip.innerHTML = '<i class="fas fa-file-csv"></i> CSV loaded — ready to import';
    lbl.childNodes[0].textContent = 'Replace file ';
}

function handleDrop(event) {
    event.preventDefault();
    const zone = event.currentTarget;
    zone.classList.remove('drag-over');
    const file = event.dataTransfer.files[0];
    if (file && file.name.endsWith('.csv')) {
        document.getElementById('csvFile').files = event.dataTransfer.files;
        previewFile(document.getElementById('csvFile'));
    }
}

function handleDrop(e) {
    e.preventDefault();
    document.getElementById('dropZone').classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file && file.name.endsWith('.csv')) {
        const dt = new DataTransfer();
        dt.items.add(file);
        document.getElementById('csvFile').files = dt.files;
        document.getElementById('filePreview').textContent = `📄 ${file.name}`;
        document.getElementById('filePreview').style.display = '';
    }
}
