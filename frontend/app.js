// Multimodal RAG System - Frontend Application

const API_BASE = '';

// DOM Elements
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const browseBtn = document.getElementById('browseBtn');
const uploadProgress = document.getElementById('uploadProgress');
const progressFill = document.getElementById('progressFill');
const uploadStatus = document.getElementById('uploadStatus');
const queryInput = document.getElementById('queryInput');
const sendBtn = document.getElementById('sendBtn');
const imageBtn = document.getElementById('imageBtn');
const queryImageInput = document.getElementById('queryImageInput');
const imagePreview = document.getElementById('imagePreview');
const previewImg = document.getElementById('previewImg');
const removeImageBtn = document.getElementById('removeImageBtn');
const chatMessages = document.getElementById('chatMessages');
const newChatBtn = document.getElementById('newChatBtn');
const viewDocsBtn = document.getElementById('viewDocsBtn');
const docsModal = document.getElementById('docsModal');
const closeDocsModal = document.getElementById('closeDocsModal');
const docsList = document.getElementById('docsList');
const toastContainer = document.getElementById('toastContainer');
const docCount = document.getElementById('docCount');
const chunkCount = document.getElementById('chunkCount');

// State
let isProcessing = false;
let queryImageFile = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    setupEventListeners();
});

// Event Listeners
function setupEventListeners() {
    // File upload
    browseBtn.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('click', (e) => {
        if (e.target === uploadArea) fileInput.click();
    });
    fileInput.addEventListener('change', handleFileSelect);

    // Drag and drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) uploadFiles(files);
    });

    // Query
    sendBtn.addEventListener('click', sendQuery);
    queryInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendQuery();
        }
    });
    queryInput.addEventListener('input', autoResize);

    // Image upload for query
    imageBtn.addEventListener('click', () => queryImageInput.click());
    queryImageInput.addEventListener('change', handleQueryImageSelect);
    removeImageBtn.addEventListener('click', removeQueryImage);

    // New chat
    newChatBtn.addEventListener('click', startNewChat);

    // Documents modal
    viewDocsBtn.addEventListener('click', () => {
        loadDocuments();
        docsModal.classList.remove('hidden');
    });
    closeDocsModal.addEventListener('click', () => {
        docsModal.classList.add('hidden');
    });
    docsModal.addEventListener('click', (e) => {
        if (e.target === docsModal) docsModal.classList.add('hidden');
    });

    // Suggested questions
    document.querySelectorAll('.suggestion-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            queryInput.value = btn.textContent;
            sendQuery();
        });
    });
}

// File Upload
function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) uploadFiles(files);
    fileInput.value = '';
}

async function uploadFiles(files) {
    if (isProcessing) return;

    isProcessing = true;
    uploadProgress.classList.remove('hidden');
    progressFill.style.width = '0%';
    uploadStatus.textContent = `Uploading ${files.length} file(s)...`;

    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const formData = new FormData();
        formData.append('file', file);

        try {
            progressFill.style.width = `${((i / files.length) * 100)}%`;
            uploadStatus.textContent = `Uploading ${file.name}...`;

            const response = await fetch(`${API_BASE}/api/upload`, {
                method: 'POST',
                body: formData,
            });

            const result = await response.json();

            if (response.ok) {
                showToast(`Uploaded: ${file.name} (${result.chunk_count} chunks, ${result.image_count} images)`, 'success');
            } else {
                showToast(`Failed: ${file.name} - ${result.detail}`, 'error');
            }
        } catch (error) {
            showToast(`Error uploading ${file.name}: ${error.message}`, 'error');
        }
    }

    progressFill.style.width = '100%';
    uploadStatus.textContent = 'Complete!';

    setTimeout(() => {
        uploadProgress.classList.add('hidden');
        isProcessing = false;
        loadStats();
    }, 1000);
}

// Query Image Handling
function handleQueryImageSelect(e) {
    const file = e.target.files[0];
    if (file) {
        queryImageFile = file;
        const reader = new FileReader();
        reader.onload = (e) => {
            previewImg.src = e.target.result;
            imagePreview.classList.remove('hidden');
        };
        reader.readAsDataURL(file);
    }
}

function removeQueryImage() {
    queryImageFile = null;
    queryImageInput.value = '';
    imagePreview.classList.add('hidden');
    previewImg.src = '';
}

// Query
async function sendQuery() {
    const question = queryInput.value.trim();
    if (!question || isProcessing) return;

    isProcessing = true;
    sendBtn.disabled = true;
    queryInput.disabled = true;

    // Add user message
    addMessage('user', question, queryImageFile);
    queryInput.value = '';
    autoResize();

    // Add loading message
    const loadingId = addMessage('assistant', '<i class="fas fa-spinner fa-spin"></i> Thinking...');

    try {
        const formData = new FormData();
        formData.append('question', question);
        if (queryImageFile) {
            formData.append('image', queryImageFile);
        }

        const response = await fetch(`${API_BASE}/api/query`, {
            method: 'POST',
            body: formData,
        });

        const result = await response.json();

        if (response.ok) {
            updateMessage(loadingId, result.answer, result.sources, result.response_time);
        } else {
            updateMessage(loadingId, `Error: ${result.detail || 'Unknown error'}`, [], 0);
        }
    } catch (error) {
        updateMessage(loadingId, `Error: ${error.message}`, [], 0);
    }

    // Reset image after query
    removeQueryImage();

    isProcessing = false;
    sendBtn.disabled = false;
    queryInput.disabled = false;
    queryInput.focus();
}

// Chat Messages
function addMessage(role, content, imageFile = null) {
    const id = `msg-${Date.now()}`;
    const time = new Date().toLocaleTimeString();

    let imageHtml = '';
    if (imageFile) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const imgEl = document.querySelector(`#${id} .message-image img`);
            if (imgEl) imgEl.src = e.target.result;
        };
        reader.readAsDataURL(imageFile);
        imageHtml = `<div class="message-image"><img src="" alt="User image"></div>`;
    }

    const messageHtml = `
        <div class="message ${role}" id="${id}">
            <div class="message-avatar">
                <i class="fas fa-${role === 'user' ? 'user' : 'robot'}"></i>
            </div>
            <div class="message-content">
                <div class="message-header">
                    <span class="message-role">${role === 'user' ? 'You' : 'AI Assistant'}</span>
                    <span class="message-time">${time}</span>
                </div>
                ${imageHtml}
                <div class="message-text">${content}</div>
            </div>
        </div>
    `;

    chatMessages.insertAdjacentHTML('beforeend', messageHtml);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return id;
}

function updateMessage(id, content, sources, responseTime) {
    const messageEl = document.getElementById(id);
    if (!messageEl) return;

    const contentEl = messageEl.querySelector('.message-text');
    contentEl.textContent = content;

    // Add sources
    if (sources && sources.length > 0) {
        const sourcesHtml = `
            <div class="sources">
                <div class="sources-title"><i class="fas fa-link"></i> Sources (${sources.length})</div>
                ${sources.map(s => `
                    <div class="source-item">
                        <span class="source-filename">${s.filename}</span>
                        <span class="source-similarity">${(s.similarity * 100).toFixed(1)}%</span>
                        ${s.chunk_type === 'text' ? `<p>${s.content_preview}</p>` : `<p><i class="fas fa-image"></i> Image from page ${s.page_num}</p>`}
                    </div>
                `).join('')}
            </div>
        `;
        contentEl.insertAdjacentHTML('beforeend', sourcesHtml);
    }

    // Update time
    const timeEl = messageEl.querySelector('.message-time');
    timeEl.textContent = `${new Date().toLocaleTimeString()} · ${responseTime}s`;

    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function startNewChat() {
    chatMessages.innerHTML = `
        <div class="welcome-message">
            <i class="fas fa-robot"></i>
            <h2>New Conversation</h2>
            <p>Ask questions using text and images about your uploaded documents.</p>
        </div>
    `;
    queryInput.value = '';
    removeQueryImage();
    queryInput.focus();
}

// Documents
async function loadDocuments() {
    try {
        const response = await fetch(`${API_BASE}/api/documents`);
        const result = await response.json();

        if (result.documents.length === 0) {
            docsList.innerHTML = '<p class="empty-state">No documents uploaded yet.</p>';
            return;
        }

        docsList.innerHTML = result.documents.map(doc => `
            <div class="doc-item">
                <div class="doc-info">
                    <i class="fas fa-file-${getFileIcon(doc.file_type)} doc-icon"></i>
                    <div>
                        <div class="doc-name">${doc.filename}</div>
                        <div class="doc-meta">${doc.file_type.toUpperCase()} · ${formatFileSize(doc.file_size)} · ${doc.chunk_count} chunks</div>
                    </div>
                </div>
                <div class="doc-actions">
                    <button class="doc-delete" onclick="deleteDocument(${doc.id})">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        docsList.innerHTML = '<p class="empty-state">Error loading documents.</p>';
    }
}

async function deleteDocument(id) {
    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
        const response = await fetch(`${API_BASE}/api/documents/${id}`, {
            method: 'DELETE',
        });

        if (response.ok) {
            showToast('Document deleted', 'success');
            loadDocuments();
            loadStats();
        } else {
            showToast('Failed to delete document', 'error');
        }
    } catch (error) {
        showToast('Error deleting document', 'error');
    }
}

// Stats
async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/api/stats`);
        const result = await response.json();

        docCount.textContent = result.total_documents || 0;
        chunkCount.textContent = result.vector_store?.total_chunks || 0;
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

// Utilities
function autoResize() {
    queryInput.style.height = 'auto';
    queryInput.style.height = Math.min(queryInput.scrollHeight, 150) + 'px';
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 5000);
}

function getFileIcon(type) {
    const icons = {
        pdf: 'pdf',
        docx: 'word',
        text: 'alt',
        image: 'image',
    };
    return icons[type] || 'alt';
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}
