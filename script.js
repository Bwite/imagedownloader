let currentSessionId = null;
let statusInterval = null;

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('downloadForm').addEventListener('submit', handleFormSubmit);
    
    // Input validation for image count
    document.getElementById('imageCount').addEventListener('input', function(e) {
        const value = parseInt(e.target.value);
        if (value > 50) {
            e.target.value = 50;
        } else if (value < 1) {
            e.target.value = 1;
        }
    });
});

function handleFormSubmit(e) {
    e.preventDefault();
    
    const query = document.getElementById('query').value.trim();
    const imageCount = document.getElementById('imageCount').value;
    const minSize = document.getElementById('minSize').value;
    
    if (!query) {
        alert('Please enter a search query!');
        return;
    }
    
    if (imageCount < 1 || imageCount > 50) {
        alert('Please enter a number between 1 and 50!');
        return;
    }
    
    startDownload(query, imageCount, minSize);
}

async function startDownload(query, count, minSize) {
    const button = document.querySelector('.download-btn');
    const originalText = button.innerHTML;
    
    try {
        // Show loading state
        button.innerHTML = '<span class="icon">⏳</span>Starting...';
        button.disabled = true;
        
        // Send request to backend
        const response = await fetch('/download', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: query,
                count: parseInt(count),
                min_size: minSize
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            currentSessionId = result.session_id;
            
            // Create progress display
            createProgressDisplay();
            
            // Start monitoring progress
            startProgressMonitoring();
            
            // Show success message
            showMessage(`Started downloading ${count} images for "${query}"`, 'success');
            
        } else {
            throw new Error(result.error || 'Download failed to start');
        }
        
    } catch (error) {
        console.error('Error:', error);
        showMessage(`Error: ${error.message}`, 'error');
        
        // Reset button
        button.innerHTML = originalText;
        button.disabled = false;
    }
}

function createProgressDisplay() {
    const container = document.querySelector('.container');
    
    // Remove existing progress if any
    const existingProgress = document.getElementById('progressDisplay');
    if (existingProgress) {
        existingProgress.remove();
    }
    
    const progressDiv = document.createElement('div');
    progressDiv.id = 'progressDisplay';
    progressDiv.className = 'progress-display';
    
    progressDiv.innerHTML = `
        <h3>Download Progress</h3>
        <div class="progress-bar-container">
            <div id="progressBar" class="progress-bar"></div>
        </div>
        <div id="progressText" class="progress-text">Initializing...</div>
        <div class="progress-buttons">
            <button id="downloadZipBtn" onclick="downloadZip()" class="btn-success" style="display: none;">📥 Download ZIP</button>
            <button onclick="resetForm()" class="btn-secondary">🔄 New Download</button>
        </div>
    `;
    
    container.appendChild(progressDiv);
}

async function startProgressMonitoring() {
    if (!currentSessionId) return;
    
    statusInterval = setInterval(async () => {
        try {
            const response = await fetch(`/status/${currentSessionId}`);
            const status = await response.json();
            
            updateProgress(status);
            
            if (status.status === 'completed' || status.status === 'failed') {
                clearInterval(statusInterval);

                if (status.status === 'completed') {
                    document.getElementById('downloadZipBtn').style.display = 'inline-block';
                    showMessage(status.message, 'success');
                } else {
                    showMessage(status.message, 'error');
                }

                // Reset download button
                const button = document.querySelector('.download-btn');
                button.innerHTML = '<span class="icon">📥</span>Start Download';
                button.disabled = false;
            }
            
        } catch (error) {
            console.error('Status check error:', error);
        }
    }, 1000);
}

function updateProgress(status) {
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    
    if (progressBar && progressText) {
        const percentage = status.total > 0 ? (status.progress / status.total) * 100 : 0;
        progressBar.style.width = `${percentage}%`;
        
        let text = status.message || 'Processing...';
        if (status.downloaded !== undefined) {
            text += ` (${status.downloaded}/${status.total} downloaded`;
            if (status.failed > 0) {
                text += `, ${status.failed} failed`;
            }
            text += ')';
        }
        
        progressText.textContent = text;
    }
}

async function downloadZip() {
    if (!currentSessionId) return;

    try {
        // Create a temporary link to trigger download
        const link = document.createElement('a');
        link.href = `/download/${currentSessionId}`;
        link.download = ''; // Let the browser handle the filename from the response
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        showMessage('Download started!', 'success');
    } catch (error) {
        showMessage('Error downloading ZIP file', 'error');
    }
}

async function openFolder() {
    if (!currentSessionId) return;

    try {
        const response = await fetch(`/open-folder/${currentSessionId}`);
        const result = await response.json();

        if (!result.success) {
            showMessage('Could not open folder', 'error');
        }
    } catch (error) {
        showMessage('Error opening folder', 'error');
    }
}

function resetForm() {
    // Clear form
    document.getElementById('query').value = '';
    document.getElementById('imageCount').value = '20';
    
    // Remove progress display
    const progressDisplay = document.getElementById('progressDisplay');
    if (progressDisplay) {
        progressDisplay.remove();
    }
    
    // Clear status interval
    if (statusInterval) {
        clearInterval(statusInterval);
    }
    
    // Reset button
    const button = document.querySelector('.download-btn');
    button.innerHTML = '<span class="icon">📥</span>Start Download';
    button.disabled = false;
    
    currentSessionId = null;
    
    // Remove any status messages
    const statusMessage = document.getElementById('statusMessage');
    if (statusMessage) {
        statusMessage.remove();
    }
}

function showMessage(message, type) {
    // Remove existing message
    const existingMessage = document.getElementById('statusMessage');
    if (existingMessage) {
        existingMessage.remove();
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.id = 'statusMessage';
    messageDiv.className = `status-message ${type}`;
    messageDiv.textContent = message;
    
    document.querySelector('.container').appendChild(messageDiv);
    
    // Auto-remove success messages after 5 seconds
    if (type === 'success') {
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 5000);
    }
}