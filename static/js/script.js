// Global variables
let currentData = [];
let currentType = '';

// Theme management
function toggleTheme() {
    const body = document.body;
    const currentTheme = body.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    body.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    
    // Update theme toggle icon
    const themeToggle = document.querySelector('.theme-toggle i');
    themeToggle.className = newTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
}

// Initialize theme
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.body.setAttribute('data-theme', savedTheme);
    
    const themeToggle = document.querySelector('.theme-toggle i');
    themeToggle.className = savedTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
}

// Show loading
function showLoading() {
    const overlay = document.getElementById('loadingOverlay');
    overlay.classList.add('show');
}

// Hide loading
function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    overlay.classList.remove('show');
}

// Show toast notification
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    const messageElement = toast.querySelector('.toast-message');
    
    messageElement.textContent = message;
    toast.className = `toast ${type}`;
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 4000);
}

// Fetch data from API and auto-download
async function fetchData(type) {
    let requestData = {
        type: type
    };
    
    // Add date parameters for divergencias
    if (type === 'divergencias') {
        const startDate = document.getElementById('start_date').value;
        const endDate = document.getElementById('end_date').value;
        
        if (!startDate || !endDate) {
            showToast('Por favor, selecione as datas de início e fim.', 'error');
            return;
        }
        
        requestData.start_date = startDate;
        requestData.end_date = endDate;
    }
    
    showLoading();
    
    try {
        const response = await fetch('/fetch_data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            currentData = result.data;
            currentType = type;
            
            showToast(`${result.count} registros encontrados. Iniciando download...`, 'success');
            
            // Auto-download após sucesso
            setTimeout(() => {
                downloadExcel();
            }, 1000);
            
        } else {
            showToast(result.message, 'error');
            
            // Se for erro de configuração, destacar o alert
            if (result.message.includes('Credenciais não configuradas') || 
                result.message.includes('JIRA_EMAIL') || 
                result.message.includes('JIRA_TOKEN')) {
                highlightConfigAlert();
            }
        }
    } catch (error) {
        showToast('Erro de conexão: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Highlight config alert
function highlightConfigAlert() {
    const alert = document.querySelector('.alert');
    if (alert) {
        alert.style.animation = 'pulse 1s ease-in-out 3';
    }
}

// Download Excel file
async function downloadExcel() {
    if (currentData.length === 0) {
        showToast('Nenhum dado para exportar.', 'warning');
        return;
    }
    
    const filename = generateFilename();
    
    try {
        const response = await fetch('/download_excel', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                data: currentData,
                filename: filename
            })
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showToast('Arquivo baixado com sucesso!', 'success');
        } else {
            const result = await response.json();
            showToast(result.message, 'error');
        }
    } catch (error) {
        showToast('Erro ao baixar arquivo: ' + error.message, 'error');
    }
}

// Generate filename based on type and date
function generateFilename() {
    const now = new Date();
    const timestamp = now.toISOString().slice(0, 19).replace(/[:.]/g, '-');
    
    let filename = `${currentType}_${timestamp}.xlsx`;
    
    if (currentType === 'divergencias') {
        const startDate = document.getElementById('start_date').value;
        const endDate = document.getElementById('end_date').value;
        if (startDate && endDate) {
            filename = `divergencias_${startDate}_${endDate}.xlsx`;
        }
    }
    
    return filename;
}

// Set default dates
function setDefaultDates() {
    const today = new Date();
    const thirtyDaysAgo = new Date(today.getTime() - (30 * 24 * 60 * 60 * 1000));
    
    const startDateInput = document.getElementById('start_date');
    const endDateInput = document.getElementById('end_date');
    
    if (startDateInput && endDateInput) {
        startDateInput.value = thirtyDaysAgo.toISOString().split('T')[0];
        endDateInput.value = today.toISOString().split('T')[0];
    }
}

// Add loading states to buttons
function setButtonLoading(button, loading = true) {
    if (loading) {
        button.disabled = true;
        const originalText = button.innerHTML;
        button.setAttribute('data-original-text', originalText);
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processando...';
    } else {
        button.disabled = false;
        const originalText = button.getAttribute('data-original-text');
        if (originalText) {
            button.innerHTML = originalText;
        }
    }
}

// Enhanced fetch function with button states
async function fetchDataEnhanced(type, buttonElement) {
    setButtonLoading(buttonElement, true);
    
    try {
        await fetchData(type);
    } finally {
        setButtonLoading(buttonElement, false);
    }
}

// Add click handlers to buttons
function initializeButtons() {
    const buttons = document.querySelectorAll('.btn[onclick^="fetchData"]');
    
    buttons.forEach(button => {
        const originalOnClick = button.getAttribute('onclick');
        if (originalOnClick) {
            const type = originalOnClick.match(/fetchData\('(\w+)'\)/)[1];
            
            button.removeAttribute('onclick');
            button.addEventListener('click', (e) => {
                e.preventDefault();
                if (!button.disabled) {
                    fetchDataEnhanced(type, button);
                }
            });
        }
    });
}

// Keyboard shortcuts
function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + Enter to fetch data
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            const activeElement = document.activeElement;
            const card = activeElement.closest('.report-card');
            if (card) {
                const type = card.getAttribute('data-type');
                const button = card.querySelector('.btn');
                if (button && !button.disabled) {
                    fetchDataEnhanced(type, button);
                }
            }
        }
        
        // Ctrl/Cmd + D to download (apenas se houver dados)
        if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
            e.preventDefault();
            if (currentData.length > 0) {
                downloadExcel();
            }
        }
    });
}

// Add pulse animation to CSS
function addPulseAnimation() {
    const style = document.createElement('style');
    style.textContent = `
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.02); }
            100% { transform: scale(1); }
        }
    `;
    document.head.appendChild(style);
}

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    initTheme();
    setDefaultDates();
    initializeButtons();
    initKeyboardShortcuts();
    addPulseAnimation();
    
    console.log('Jira Issues Fetcher initialized successfully!');
});

// Error handling for uncaught errors
window.addEventListener('error', function(e) {
    console.error('Uncaught error:', e.error);
    showToast('Ocorreu um erro inesperado. Verifique o console para mais detalhes.', 'error');
});

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled promise rejection:', e.reason);
    showToast('Erro de conexão. Verifique sua internet e tente novamente.', 'error');
});