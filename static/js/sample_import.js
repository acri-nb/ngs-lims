// 

function previewFile(input) {
    const preview = document.getElementById('filePreview');
    if (input.files[0]) {
        preview.textContent = `📄 ${input.files[0].name} (${(input.files[0].size/1024).toFixed(1)} KB)`;
        preview.style.display = '';
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