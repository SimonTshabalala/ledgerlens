const API_URL = "https://ledgerlens-mdv3.onrender.com";
let authToken = null;
let chartInstance = null;

function showLogin() {
    document.getElementById('authTitle').innerText = 'Login';
    document.getElementById('loginForm').style.display = 'block';
    document.getElementById('registerForm').style.display = 'none';
    document.getElementById('authModal').style.display = 'flex';
}

function showRegister() {
    document.getElementById('authTitle').innerText = 'Register';
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'block';
    document.getElementById('authModal').style.display = 'flex';
}

function closeAuthModal() {
    document.getElementById('authModal').style.display = 'none';
}

async function register() {
    const username = document.getElementById('regUsername').value;
    const email = document.getElementById('regEmail').value;
    const password = document.getElementById('regPassword').value;
    const company = document.getElementById('regCompany').value;
    
    const response = await fetch(`${API_URL}/api/register?username=${username}&email=${email}&password=${password}&company_name=${company}`, {
        method: 'POST'
    });
    
    if (response.ok) {
        alert('Registration successful! Please login.');
        showLogin();
    } else {
        alert('Registration failed');
    }
}

async function login() {
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;
    
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    
    const response = await fetch(`${API_URL}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData
    });
    
    if (response.ok) {
        const data = await response.json();
        authToken = data.access_token;
        document.getElementById('authModal').style.display = 'none';
        document.getElementById('dashboard').style.display = 'block';
        document.getElementById('userInfo').innerHTML = `<strong>${data.company || username}</strong><br>Welcome!`;
        loadStats();
        loadTransactions();
    } else {
        alert('Login failed');
    }
}

function logout() {
    authToken = null;
    document.getElementById('dashboard').style.display = 'none';
    showLogin();
}

function getHeaders() {
    return {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json'
    };
}

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
    
    const response = await fetch(`${API_URL}/api/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${authToken}` },
        body: formData
    });
    
    if (response.ok) {
        const data = await response.json();
        alert(`Upload complete! Found ${data.anomalies} anomalies out of ${data.total} transactions.`);
        loadTransactions();
        loadStats();
        document.getElementById('uploadSection').style.display = 'none';
    } else {
        alert('Upload failed');
    }
}

async function loadStats() {
    const response = await fetch(`${API_URL}/api/stats`, { headers: getHeaders() });
    const stats = await response.json();
    
    document.getElementById('stats').innerHTML = `
        <div class="card"><h3>Total Transactions</h3><p>${stats.total}</p></div>
        <div class="card"><h3>High Risk</h3><p>${stats.high_risk}</p></div>
        <div class="card"><h3>AI Anomalies</h3><p>${stats.anomalies}</p></div>
        <div class="card"><h3>Total Volume</h3><p>R${stats.total_amount.toLocaleString()}</p></div>
    `;
}

async function loadTransactions() {
    const response = await fetch(`${API_URL}/api/transactions`, { headers: getHeaders() });
    const data = await response.json();
    renderDashboard(data);
}

async function loadHighRisk() {
    const response = await fetch(`${API_URL}/api/high-risk`, { headers: getHeaders() });
    const data = await response.json();
    renderDashboard(data);
}

function renderDashboard(data) {
    if (!data || data.length === 0) {
        document.getElementById('results').innerHTML = '<p>No transactions found.</p>';
        return;
    }
    
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
                backgroundColor: 'rgba(54, 162, 235, 0.6)'
            }]
        }
    });
    
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
            <td>${row.is_anomaly ? '⚠️ ANOMALY' : '✓'}</td>
        </tr>`;
    });
    
    html += '</tbody></table>';
    document.getElementById('results').innerHTML = html;
}

showLogin();
