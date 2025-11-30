document.addEventListener('DOMContentLoaded', () => {
    fetchFiles();
});

async function fetchFiles() {
    try {
        const response = await fetch('/api/files');
        const files = await response.json();
        renderFiles(files);
    } catch (error) {
        console.error('Error fetching files:', error);
    }
}

function renderFiles(files) {
    const grid = document.getElementById('file-grid');
    grid.innerHTML = ''; // Clear loading state

    files.forEach(file => {
        const card = document.createElement('div');
        card.className = 'file-card';

        let iconClass = 'fa-file';
        if (file.type === 'folder') {
            iconClass = 'fa-folder';
            card.querySelector('.icon')?.style.setProperty('color', '#5f6368'); // Folder color
        } else if (file.name.endsWith('.txt')) {
            iconClass = 'fa-file-lines';
        } else if (file.name.match(/\.(jpg|jpeg|png|gif)$/)) {
            iconClass = 'fa-image';
        }

        card.innerHTML = `
            <div class="icon"><i class="fa-solid ${iconClass}"></i></div>
            <div class="name">${file.name}</div>
        `;

        grid.appendChild(card);
    });
}
