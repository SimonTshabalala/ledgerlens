const API_URL = "https://ledgerlens-mdv3.onrender.com";
let authToken = null;
let chartInstance = null;
let currentUsername = null;

// ==================== PAGE NAVIGATION ====================
function scrollToFeatures() {
    document.getElementById('features').scrollIntoView({ behavior: 'smooth' });
}

function showLogin() {
    document.getElementById('authTitle').innerText = 'Login to LedgerLens';
    document.getElementById('loginForm').style.display = 'block';
    document.getElementById('registerForm').style.display = 'none';
    document.getElementById('authModal').style.display = 'flex';
}

function showRegister() {
    document.getElementById('authTitle').innerText = 'Create Your Account';
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'block';
    document.getElementById('authModal').style.display = 'flex';
}

function closeAuthModal() {
    document.getElementById('authModal').style.display = 'none';
}

// ==================== AUTHENTICATION ====================
async function register() {
    const username = document.getElementById('regUsername').value;
    const email = document.getElementById('regEmail').value;
    const password = document.getElementById('regPassword').value;
    const company = document.getElementById('regCompany').value;
    
    if (!username || !email || !password) {
        alert("Please fill in all fields");
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/api/register?username=${encodeURIComponent(username)}&email=${encodeURIComponent(email)}&password=${encodeURIComponent(password)}&company_name=${encodeURIComponent(company)}`, {
            method: 'POST'
        });
        
        if (response.ok) {
            alert('Registration successful! Please login.');
            showLogin();
            document.getElementById('regUsername').value = '';
            document.getElementById('regEmail').value = '';
            document.getElementById('regPassword').value = '';
            document.getElementById('regCompany').value = '';
        } else {
            const error = await response.json();
            alert('Registration failed: ' + (error.detail || "Unknown error"));
        }
    } catch (error) {
        console.error("Registration error:", error);
        alert("Cannot connect to server");
    }
}

async function login() {
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;
    
    if (!username || !password) {
        alert("Please enter username and password");
        return;
    }
    
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    
    try {
        const response = await fetch(`${API_URL}/api/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData
        });
        
        if (response.ok) {
            const data = await response.json();
            authToken = data.username;
            currentUsername = data.username;
            document.getElementById('authModal').style.display = 'none';
            document.getElementById('landingPage').style.display = 'none';
            document.getElementById('dashboard').style.display = 'block';
            document.getElementById('userInfo').innerHTML = `<strong>${data.company}</strong><br>Welcome, ${data.username}!`;
            loadStats();
            loadTransactions();
        } else {
            alert('Login failed: Invalid credentials');
        }
    } catch (error) {
        console.error("Login error:", error);
        alert("Cannot connect to server");
    }
}

function logout() {
    authToken = null;
    currentUsername = null;
    document.getElementById('dashboard').style.display = 'none';
    document.getElementById('landingPage').style.display = 'block';
    document.getElementById('loginUsername').value = '';
    document.getElementById('loginPassword').value = '';
}

function getHeaders() {
    return {
        'username': currentUsername
    };
}

// ==================== CSV UPLOAD ====================
function showUpload() {
    const uploadSection = document.getElementById('uploadSection');
    uploadSection.style.display = uploadSection.style.display === 'none' ? 'block' : 'none';
}

async function uploadCSV() {
    const file = document.getElementById('csvFile').files[0];
    if (!file) {
        alert('Please select a CSV file');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch(`${API_URL}/api/upload`, {
            method: 'POST',
            headers: getHeaders(),
            body: formData
        });
        
        if (response.ok) {
            const data = await response.json();
            alert(`✅ Upload complete!\n\n📊 Total: ${data.total} transactions\n🤖 Anomalies found: ${data.anomalies}\n⚠️ High risk: ${data.flagged_count}`);
            loadTransactions();
            loadStats();
            document.getElementById('uploadSection').style.display = 'none';
            document.getElementById('csvFile').value = '';
        } else {
            alert('Upload failed');
        }
    } catch (error) {
        console.error("Upload error:", error);
        alert("Upload failed: " + error.message);
    }
}

// ==================== DATA DISPLAY ====================
async function loadStats() {
    try {
        const response = await fetch(`${API_URL}/api/stats`, { headers: getHeaders() });
        const stats = await response.json();
        
        document.getElementById('stats').innerHTML = `
            <div class="card"><h3>Total Transactions</h3><p>${stats.total || 0}</p></div>
            <div class="card"><h3>High Risk</h3><p>${stats.high_risk || 0}</p></div>
            <div class="card"><h3>AI Anomalies</h3><p>${stats.anomalies || 0}</p></div>
            <div class="card"><h3>Total Volume</h3><p>R${(stats.total_amount || 0).toLocaleString()}</p></div>
        `;
    } catch (error) {
        console.error("Stats error:", error);
    }
}

async function loadTransactions() {
    try {
        const response = await fetch(`${API_URL}/api/transactions`, { headers: getHeaders() });
        const data = await response.json();
        renderDashboard(data);
    } catch (error) {
        console.error("Load transactions error:", error);
    }
}

async function loadHighRisk() {
    try {
        const response = await fetch(`${API_URL}/api/high-risk`, { headers: getHeaders() });
        const data = await response.json();
        renderDashboard(data);
    } catch (error) {
        console.error("Load high risk error:", error);
    }
}

// ==================== REPORT GENERATION ====================
async function generateReport() {
    try {
        const response = await fetch(`${API_URL}/api/generate-report`, {
            method: 'POST',
            headers: getHeaders()
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `ledgerlens_report_${new Date().toISOString().split('T')[0]}.pdf`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            alert("Report generated successfully!");
        } else {
            alert("No transactions found. Please upload data first.");
        }
    } catch (error) {
        console.error("Report error:", error);
        alert("Failed to generate report");
    }
}

function renderDashboard(data) {
    if (!data || data.length === 0) {
        document.getElementById('results').innerHTML = '<p>No transactions found. Upload a CSV file to get started.</p>';
        return;
    }
    
    // Update chart
    const vendors = {};
    data.forEach(t => {
        vendors[t.vendor] = (vendors[t.vendor] || 0) + t.amount;
    });
    
    const ctx = document.getElementById('chartCanvas').getContext('2d');
    if (chartInstance) chartInstance.destroy();
    chartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: Object.keys(vendors),
            datasets: [{
                label: 'Spend per Vendor (R)',
                data: Object.values(vendors),
                backgroundColor: 'rgba(102, 126, 234, 0.6)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true
        }
    });
    
    // Build table
    let html = '<table class="data-table"><thead><tr>';
    const headers = ['Date', 'Vendor', 'Amount', 'Risk Score', 'AI Anomaly'];
    headers.forEach(h => html += `<th>${h}</th>`);
    html += '</tr></thead><tbody>';
    
    data.forEach(row => {
        const riskClass = row.risk_score >= 40 ? 'high-risk' : (row.risk_score >= 20 ? 'medium-risk' : 'low-risk');
        html += `<tr class="${riskClass}">
            <td>${new Date(row.date).toLocaleDateString()}</td>
            <td>${row.vendor}</td>
            <td>R${row.amount.toLocaleString()}</td>
            <td>${row.risk_score}</td>
            <td>${row.is_anomaly ? '⚠️ ANOMALY' : '✓ Normal'}</td>
        </tr>`;
    });
    
    html += '</tbody></table>';
    document.getElementById('results').innerHTML = html;
}
