let currentFolderId = null;
let folderPath = [{ id: null, name: 'My Drive' }];
let contextMenuItem = null;
let viewMode = localStorage.getItem('viewMode') || 'grid'; // 'grid' or 'list'
let selectedItems = new Set(); // Track selected file IDs
let destinationPath = [{ id: null, name: 'My Drive' }];
let destinationAction = null; // 'move' or 'copy'
let actionItems = []; // Items being moved or copied

document.addEventListener('DOMContentLoaded', () => {
    fetchFiles();
    fetchStorageUsage();
    setupEventListeners();
    updateViewModeUI();
});

function setupEventListeners() {
    // File Input
    document.getElementById('file-input').addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0]);
        }
    });

    // Close menus on click outside
    document.addEventListener('click', (e) => {
        hideContextMenu();
        if (!e.target.closest('.new-btn-container')) {
            const newMenu = document.getElementById('new-menu');
            if (newMenu) newMenu.style.display = 'none';
        }
        if (e.target.classList.contains('modal')) {
            closeModal(e.target.id);
        }

        // Clear selection if clicking on empty file area
        if (e.target.classList.contains('file-area') || e.target.id === 'file-grid') {
            selectedItems.clear();
            updateSelectionUI();
        }
    });

    const contextMenu = document.getElementById('context-menu');
    if (contextMenu) {
        contextMenu.addEventListener('click', (e) => {
            e.stopPropagation();
        });
    }

    // Enter key for folder name
    const folderInput = document.getElementById('folder-name-input');
    if (folderInput) {
        folderInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') createFolder();
        });
    }
}

// --- UI Functions ---
function toggleNewMenu() {
    const menu = document.getElementById('new-menu');
    menu.style.display = menu.style.display === 'block' ? 'none' : 'block';
}

function showCreateFolderModal() {
    document.getElementById('new-menu').style.display = 'none';
    document.getElementById('folder-modal').style.display = 'flex';
    const input = document.getElementById('folder-name-input');
    input.value = '';
    input.focus();
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

function toggleView() {
    viewMode = viewMode === 'grid' ? 'list' : 'grid';
    localStorage.setItem('viewMode', viewMode);
    updateViewModeUI();
    if (window.lastFiles) {
        renderFiles(window.lastFiles);
    } else {
        fetchFiles();
    }
}

function updateViewModeUI() {
    const btn = document.getElementById('view-toggle-btn');
    const fileArea = document.querySelector('.file-area');
    const listHeader = document.getElementById('list-header');

    if (viewMode === 'list') {
        btn.innerHTML = '<i class="fa-solid fa-border-all"></i>';
        btn.title = 'Grid view';
        fileArea.classList.add('list-view');
        listHeader.style.display = 'flex';
    } else {
        btn.innerHTML = '<i class="fa-solid fa-list"></i>';
        btn.title = 'List view';
        fileArea.classList.remove('list-view');
        listHeader.style.display = 'none';
    }
}

async function createFolder() {
    const nameInput = document.getElementById('folder-name-input');
    const name = nameInput.value.trim();

    if (!name) return;

    try {
        const response = await fetch('/api/folders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                parent_id: currentFolderId
            })
        });

        if (response.ok) {
            closeModal('folder-modal');
            fetchFiles();
        } else {
            alert('Failed to create folder');
        }
    } catch (error) {
        console.error('Create folder error:', error);
        alert('Error creating folder');
    }
}

// --- File Functions ---
async function fetchFiles(folderId = currentFolderId) {
    const isNavigation = folderId !== currentFolderId;
    currentFolderId = folderId;
    updateBreadcrumbs();

    // Clear selection on navigation
    selectedItems.clear();

    const grid = document.getElementById('file-grid');

    // Only show full loading state if navigating to a new folder
    if (isNavigation || grid.children.length === 0) {
        grid.innerHTML = '<div class="file-card loading"><div class="icon"><i class="fa-solid fa-spinner fa-spin"></i></div><div class="name">Loading...</div></div>';
    }

    try {
        const response = await fetch(`/api/files?parent_id=${folderId || 'null'}`);

        if (response.status === 401) {
            window.location.href = '/login';
            return;
        }

        const files = await response.json();
        window.lastFiles = files; // Store for view toggling
        renderFiles(files);
    } catch (error) {
        console.error('Error fetching files:', error);
        grid.innerHTML = '<div class="error">Failed to load files</div>';
    }
}

function renderFiles(files) {
    const grid = document.getElementById('file-grid');
    grid.innerHTML = '';

    if (files.length === 0) {
        grid.innerHTML = '<div class="empty-state" style="padding: 20px; text-align: center; color: #5f6368;">Folder is empty</div>';
        return;
    }

    files.forEach(file => {
        const card = document.createElement('div');
        card.className = `file-card ${file.type}`;
        card.dataset.id = file.id;
        card.dataset.type = file.type;

        let iconClass = 'fa-file';
        let color = '#5f6368';

        if (file.type === 'folder') {
            iconClass = 'fa-folder';
            color = '#5f6368';
        } else if (file.name.endsWith('.txt')) {
            iconClass = 'fa-file-lines';
            color = '#1a73e8';
        } else if (file.name.match(/\.(jpg|jpeg|png|gif)$/i)) {
            iconClass = 'fa-image';
            color = '#d93025';
        } else if (file.name.match(/\.(pdf)$/i)) {
            iconClass = 'fa-file-pdf';
            color = '#d93025';
        }

        // Content depends on view mode
        if (viewMode === 'list') {
            card.innerHTML = `
                <div class="icon" style="color: ${color}"><i class="fa-solid ${iconClass}"></i></div>
                <div class="name">${file.name}</div>
                <div class="col-owner">me</div>
                <div class="col-modified">-</div>
                <div class="col-size">-</div>
            `;
        } else {
            card.innerHTML = `
                <div class="icon" style="color: ${color}"><i class="fa-solid ${iconClass}"></i></div>
                <div class="name">${file.name}</div>
            `;
        }

        // Click to select
        card.addEventListener('click', (e) => handleItemClick(e, file));

        // Double click to open
        card.addEventListener('dblclick', (e) => handleItemDblClick(e, file));

        // Right click for context menu
        card.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            // Select item on right click if not already selected
            if (!selectedItems.has(file.id)) {
                selectedItems.clear();
                selectedItems.add(file.id);
                updateSelectionUI();
            }
            showContextMenu(e, file);
        });

        grid.appendChild(card);
    });

    updateSelectionUI();
}

function handleItemClick(e, file) {
    e.stopPropagation(); // Prevent clearing selection from global click

    if (e.ctrlKey || e.metaKey) {
        // Toggle selection
        if (selectedItems.has(file.id)) {
            selectedItems.delete(file.id);
        } else {
            selectedItems.add(file.id);
        }
    } else {
        // Single select
        selectedItems.clear();
        selectedItems.add(file.id);
    }
    updateSelectionUI();
}

function handleItemDblClick(e, file) {
    if (file.type === 'folder') {
        folderPath.push({ id: file.id, name: file.name });
        fetchFiles(file.id);
    }
}

function updateSelectionUI() {
    const cards = document.querySelectorAll('.file-card');
    cards.forEach(card => {
        if (selectedItems.has(card.dataset.id)) {
            card.classList.add('selected');
        } else {
            card.classList.remove('selected');
        }
    });
}

// --- Upload Functions ---
let uploadQueue = [];
let uploadMinimized = false;

function toggleUploadContainer() {
    const list = document.getElementById('upload-list');
    const icon = document.getElementById('upload-toggle-icon');

    if (uploadMinimized) {
        list.style.display = 'block';
        icon.className = 'fa-solid fa-chevron-down';
    } else {
        list.style.display = 'none';
        icon.className = 'fa-solid fa-chevron-up';
    }
    uploadMinimized = !uploadMinimized;
}

function closeUploadContainer() {
    document.getElementById('upload-status-container').style.display = 'none';
    document.getElementById('upload-list').innerHTML = ''; // Clear completed
}

function createUploadItemUI(file) {
    const container = document.getElementById('upload-status-container');
    const list = document.getElementById('upload-list');

    if (container.style.display === 'none') {
        container.style.display = 'flex';
        uploadMinimized = false;
        document.getElementById('upload-list').style.display = 'block';
        document.getElementById('upload-toggle-icon').className = 'fa-solid fa-chevron-down';
    }

    const item = document.createElement('div');
    item.className = 'upload-item';
    item.id = `upload-${file.name}-${Date.now()}`;

    // Update header count
    const activeUploads = document.querySelectorAll('.upload-item .upload-progress-bar:not([style*="background-color: rgb(30, 142, 62)"])').length + 1;
    // Note: The selector above is a bit brittle. A simpler way is to maintain a counter or check pending items.
    // For now, let's just count all items in list as "items".
    // Better: Update count based on list children.
    const totalItems = list.children.length + 1;
    document.getElementById('upload-header-text').textContent = `Uploading ${totalItems} item${totalItems !== 1 ? 's' : ''}`;

    item.innerHTML = `
        <div class="upload-item-header">
            <div class="upload-filename" title="${file.name}">${file.name}</div>
            <div class="upload-status-icon"><i class="fa-solid fa-spinner fa-spin"></i></div>
        </div>
        <div class="upload-progress-bar-container">
            <div class="upload-progress-bar"></div>
        </div>
        <div class="upload-details">
            <span class="upload-size">Waiting...</span>
            <span class="upload-speed"></span>
        </div>
    `;

    list.prepend(item);
    return item;
}

function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function uploadFile(file) {
    const uiItem = createUploadItemUI(file);
    const progressBar = uiItem.querySelector('.upload-progress-bar');
    const sizeText = uiItem.querySelector('.upload-size');
    const speedText = uiItem.querySelector('.upload-speed');
    const statusIcon = uiItem.querySelector('.upload-status-icon');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('parent_id', currentFolderId || '');

    const xhr = new XMLHttpRequest();
    let startTime = Date.now();
    let lastLoaded = 0;

    xhr.upload.addEventListener('loadstart', () => {
        startTime = Date.now();
        lastLoaded = 0;
    });

    xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
            const percentComplete = (e.loaded / e.total) * 100;
            progressBar.style.width = percentComplete + '%';

            const currentTime = Date.now();
            const timeDiff = (currentTime - startTime) / 1000; // seconds

            // Calculate speed
            if (timeDiff > 0) {
                const speed = e.loaded / timeDiff; // bytes per second
                speedText.textContent = `${formatSize(speed)}/s`;
            }

            sizeText.textContent = `${formatSize(e.loaded)} / ${formatSize(e.total)}`;
        }
    });

    xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
            progressBar.style.width = '100%';
            progressBar.style.backgroundColor = '#1e8e3e'; // Green
            statusIcon.innerHTML = '<i class="fa-solid fa-check" style="color: #1e8e3e;"></i>';
            sizeText.textContent = 'Upload complete';
            speedText.textContent = '';
            speedText.textContent = '';
            fetchFiles(); // Refresh file list
            fetchStorageUsage(); // Update storage
        } else if (xhr.status === 401) {
            window.location.href = '/login';
        } else {
            statusIcon.innerHTML = '<i class="fa-solid fa-triangle-exclamation" style="color: #d93025;"></i>';
            sizeText.textContent = 'Upload failed';
            speedText.textContent = '';
            progressBar.style.backgroundColor = '#d93025'; // Red
        }
    });

    xhr.addEventListener('error', () => {
        statusIcon.innerHTML = '<i class="fa-solid fa-triangle-exclamation" style="color: #d93025;"></i>';
        sizeText.textContent = 'Network error';
        speedText.textContent = '';
        progressBar.style.backgroundColor = '#d93025';
    });

    xhr.addEventListener('abort', () => {
        statusIcon.innerHTML = '<i class="fa-solid fa-ban"></i>';
        sizeText.textContent = 'Cancelled';
        speedText.textContent = '';
    });

    xhr.open('POST', '/api/upload');
    xhr.send(formData);
}

function updateBreadcrumbs() {
    const container = document.getElementById('breadcrumbs');
    container.innerHTML = '';

    folderPath.forEach((folder, index) => {
        const span = document.createElement('span');
        span.className = 'crumb';
        span.textContent = folder.name;
        span.onclick = () => navigateTo(index);
        container.appendChild(span);
    });
}

function navigateTo(index) {
    if (index === null) {
        folderPath = [{ id: null, name: 'My Drive' }];
        fetchFiles(null);
    } else {
        const folder = folderPath[index];
        folderPath = folderPath.slice(0, index + 1);
        fetchFiles(folder.id);
    }
}

function showContextMenu(e, item) {
    e.stopPropagation();
    contextMenuItem = item;
    const menu = document.getElementById('context-menu');
    menu.style.display = 'block';
    menu.style.left = `${e.pageX}px`;
    menu.style.top = `${e.pageY}px`;
}

function hideContextMenu() {
    document.getElementById('context-menu').style.display = 'none';
    contextMenuItem = null;
}

function downloadItem() {
    if (!contextMenuItem || contextMenuItem.type === 'folder') return;

    window.location.href = `/api/download/${contextMenuItem.id}`;
    hideContextMenu();
}

async function deleteItem() {
    if (!contextMenuItem) return;

    let itemsToDelete = [];

    // Check if the right-clicked item is part of the selection
    if (selectedItems.has(contextMenuItem.id)) {
        // Delete all selected items
        selectedItems.forEach(id => {
            const card = document.querySelector(`.file-card[data-id="${id}"]`);
            if (card) {
                itemsToDelete.push({
                    id: id,
                    type: card.dataset.type
                });
            }
        });
    } else {
        // Delete only the right-clicked item
        itemsToDelete.push({
            id: contextMenuItem.id,
            type: contextMenuItem.type
        });
    }

    const count = itemsToDelete.length;
    const confirmMsg = count > 1 ? `Delete ${count} items?` : `Delete ${contextMenuItem.name}?`;

    if (!confirm(confirmMsg)) return;

    try {
        await fetch('/api/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                items: itemsToDelete
            })
        });
        fetchFiles();
        fetchStorageUsage(); // Update storage
        selectedItems.clear(); // Clear selection after delete
        updateSelectionUI();
    } catch (error) {
        console.error('Delete error:', error);
    }
    hideContextMenu();
}

function showRenameModal() {
    if (!contextMenuItem) return;
    hideContextMenu();

    document.getElementById('rename-modal').style.display = 'flex';
    const input = document.getElementById('rename-input');
    input.value = contextMenuItem.name;
    input.focus();

    // Handle Enter key
    input.onkeypress = (e) => {
        if (e.key === 'Enter') renameItem();
    };
}

async function renameItem() {
    if (!contextMenuItem) return;

    const input = document.getElementById('rename-input');
    const newName = input.value.trim();

    if (!newName || newName === contextMenuItem.name) {
        closeModal('rename-modal');
        return;
    }

    try {
        const response = await fetch('/api/rename', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id: contextMenuItem.id,
                type: contextMenuItem.type,
                name: newName
            })
        });

        if (response.ok) {
            closeModal('rename-modal');
            fetchFiles();
        } else {
            alert('Rename failed');
        }
    } catch (error) {
        console.error('Rename error:', error);
        alert('Rename error');
    }
}

async function logout() {
    if (!confirm('Are you sure you want to logout?')) return;

    try {
        const response = await fetch('/api/auth/logout', {
            method: 'POST'
        });

        if (response.ok) {
            window.location.href = '/login';
        } else {
            alert('Logout failed');
        }
    } catch (error) {
        console.error('Logout error:', error);
        alert('Logout error');
    }
}

// Expose for HTML onclick
window.navigateTo = navigateTo;
window.downloadItem = downloadItem;
window.deleteItem = deleteItem;
window.logout = logout;
window.toggleNewMenu = toggleNewMenu;
window.showCreateFolderModal = showCreateFolderModal;
window.closeModal = closeModal;
window.createFolder = createFolder;
window.toggleView = toggleView;
window.showRenameModal = showRenameModal;
window.renameItem = renameItem;

// Expose functions
window.openDestinationModal = openDestinationModal;
window.confirmMove = confirmMove;
window.confirmCopy = confirmCopy;
function openDestinationModal(action) {
    if (!contextMenuItem) return;

    actionItems = [];
    if (selectedItems.has(contextMenuItem.id)) {
        selectedItems.forEach(id => {
            const card = document.querySelector(`.file-card[data-id="${id}"]`);
            if (card) {
                actionItems.push({
                    id: id,
                    type: card.dataset.type,
                    name: card.querySelector('.name').textContent
                });
            }
        });
    } else {
        actionItems.push({
            id: contextMenuItem.id,
            type: contextMenuItem.type,
            name: contextMenuItem.name
        });
    }

    hideContextMenu();

    destinationAction = action;
    const count = actionItems.length;
    const title = action === 'move' ? `Move ${count} item${count > 1 ? 's' : ''} to...` : `Copy ${count} item${count > 1 ? 's' : ''} to...`;
    const btnText = action === 'move' ? 'Move Here' : 'Copy Here';

    document.getElementById('destination-title').textContent = title;
    document.getElementById('destination-confirm-btn').textContent = btnText;
    document.getElementById('destination-confirm-btn').onclick = action === 'move' ? confirmMove : confirmCopy;

    document.getElementById('destination-modal').style.display = 'flex';

    // Reset path
    destinationPath = [{ id: null, name: 'My Drive' }];
    fetchDestinationFolders(null);
}

async function fetchDestinationFolders(parentId) {
    updateDestinationBreadcrumbs();
    const list = document.getElementById('dest-list');
    list.innerHTML = '<div style="padding: 10px;">Loading...</div>';

    try {
        const response = await fetch(`/api/files?parent_id=${parentId || 'null'}`);
        const items = await response.json();
        const folders = items.filter(item => item.type === 'folder');

        renderDestinationFolders(folders);
    } catch (error) {
        console.error('Error fetching destination folders:', error);
        list.innerHTML = '<div style="padding: 10px; color: red;">Error loading folders</div>';
    }
}

function renderDestinationFolders(folders) {
    const list = document.getElementById('dest-list');
    list.innerHTML = '';

    if (folders.length === 0) {
        list.innerHTML = '<div style="padding: 10px; color: #5f6368;">No folders</div>';
        return;
    }

    folders.forEach(folder => {
        const item = document.createElement('div');
        item.className = 'dest-folder-item';
        item.style.padding = '10px';
        item.style.cursor = 'pointer';
        item.style.display = 'flex';
        item.style.alignItems = 'center';
        item.style.borderBottom = '1px solid #f1f3f4';

        // Disable if moving folder into itself (simple check, backend does full check)
        if (destinationAction === 'move') {
            const isSelf = actionItems.some(i => i.type === 'folder' && i.id === folder.id);
            if (isSelf) {
                item.style.opacity = '0.5';
                item.style.pointerEvents = 'none';
            }
        }

        item.innerHTML = `<i class="fa-solid fa-folder" style="margin-right: 10px; color: #5f6368;"></i> ${folder.name}`;

        item.onclick = () => {
            destinationPath.push({ id: folder.id, name: folder.name });
            fetchDestinationFolders(folder.id);
        };

        list.appendChild(item);
    });
}

function updateDestinationBreadcrumbs() {
    const container = document.getElementById('dest-breadcrumbs');
    container.innerHTML = '';

    destinationPath.forEach((folder, index) => {
        const span = document.createElement('span');
        span.className = 'crumb';
        span.textContent = folder.name;
        span.style.cursor = 'pointer';
        span.style.marginRight = '5px';

        if (index < destinationPath.length - 1) {
            span.innerHTML += ' <i class="fa-solid fa-chevron-right" style="font-size: 10px;"></i> ';
        }

        span.onclick = () => {
            destinationPath = destinationPath.slice(0, index + 1);
            fetchDestinationFolders(folder.id);
        };

        container.appendChild(span);
    });
}

async function confirmMove() {
    const currentDest = destinationPath[destinationPath.length - 1];
    const newParentId = currentDest.id;

    try {
        const response = await fetch('/api/move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                items: actionItems,
                new_parent_id: newParentId
            })
        });

        if (response.ok) {
            closeModal('destination-modal');
            fetchFiles(); // Refresh current view
            selectedItems.clear();
            updateSelectionUI();
        } else {
            const data = await response.json();
            alert(data.error || 'Move failed');
        }
    } catch (error) {
        console.error('Move error:', error);
        alert('Move error');
    }
}

async function confirmCopy() {
    const currentDest = destinationPath[destinationPath.length - 1];
    const newParentId = currentDest.id;

    // Show loading state on button
    const btn = document.getElementById('destination-confirm-btn');
    const originalText = btn.textContent;
    btn.textContent = 'Copying...';
    btn.disabled = true;

    try {
        const response = await fetch('/api/copy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                items: actionItems,
                new_parent_id: newParentId
            })
        });

        if (response.ok) {
            closeModal('destination-modal');
            fetchFiles(); // Refresh current view
            selectedItems.clear();
            updateSelectionUI();
        } else {
            const data = await response.json();
            alert(data.error || 'Copy failed');
        }
    } catch (error) {
        console.error('Copy error:', error);
        alert('Copy error');
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

async function fetchStorageUsage() {
    try {
        const response = await fetch('/api/storage');
        if (response.ok) {
            const data = await response.json();
            const usedBytes = data.used;
            const usedText = formatSize(usedBytes);

            const storageTextElement = document.querySelector('.storage-text');
            const progressBar = document.querySelector('.storage-widget .progress');

            if (storageTextElement) {
                storageTextElement.textContent = `${usedText} used of Unlimited`;
            }

            if (progressBar) {
                // For unlimited, we can just show a small fixed percentage or 0
                // Or maybe calculate based on some arbitrary "tier" just for visuals?
                // Let's just set it to something minimal to show activity if used > 0
                progressBar.style.width = usedBytes > 0 ? '1%' : '0%';
            }
        }
    } catch (error) {
        console.error('Error fetching storage usage:', error);
    }
}

// Expose
window.fetchStorageUsage = fetchStorageUsage;
