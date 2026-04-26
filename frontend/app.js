const API_URL = "https://ledgerlens-mdv3.onrender.com";
let authToken = null;
let chartInstance = null;

// Make functions global
window.showLogin = showLogin;
window.showRegister = showRegister;
window.closeAuthModal = closeAuthModal;
window.register = register;
window.login = login;
window.logout = logout;
window.showUpload = showUpload;
window.uploadCSV = uploadCSV;
window.loadTransactions = loadTransactions;
window.loadHighRisk = loadHighRisk;

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
    console.log("Register function called");
    
    const username = document.getElementById('regUsername').value;
    const email = document.getElementById('regEmail').value;
    const password = document.getElementById('regPassword').value;
    const company = document.getElementById('regCompany').value;
    
    if (!username || !email || !password) {
        alert("Please fill in all fields");
        return;
    }
    
    const url = `${API_URL}/api/register?username=${encodeURIComponent(username)}&email=${encodeURIComponent(email)}&password=${encodeURIComponent(password)}&company_name=${encodeURIComponent(company)}`;
    console.log("Calling:", url);
    
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Accept': 'application/json'
            }
        });
        
        console.log("Response status:", response.status);
        const data = await response.json();
        console.log("Response data:", data);
        
        if (response.ok) {
            alert('Registration successful! Please login.');
            showLogin();
            // Clear registration form
            document.getElementById('regUsername').value = '';
            document.getElementById('regEmail').value = '';
            document.getElementById('regPassword').value = '';
            document.getElementById('regCompany').value = '';
        } else {
            alert('Registration failed: ' + (data.detail || "Unknown error"));
        }
    } catch (error) {
        console.error("Registration error:", error);
        alert("Cannot connect to backend. Please make sure the server is running.");
    }
}

async function login() {
    console.log("Login function called");
    
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
            headers: { 
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            },
            body: formData
        });
        
        console.log("Login response:", response.status);
        
        if (response.ok) {
            const data = await response.json();
            authToken = data.access_token;
            document.getElementById('authModal').style.display = 'none';
            document.getElementById('dashboard').style.display = 'block';
            document.getElementById('userInfo').innerHTML = `<strong>${data.company || username}</strong><br>Welcome!`;
            loadStats();
            loadTransactions();
        } else {
            const error = await response.json();
            alert('Login failed: ' + (error.detail || "Invalid credentials"));
        }
    } catch (error) {
        console.error("Login error:", error);
        alert("Cannot connect to backend. Please make sure the server is running.");
    }
}

function logout() {
    authToken = null;
    document.getElementById('dashboard').style.display = 'none';
    document.getElementById('loginUsername').value = '';
    document.getElementById('loginPassword').value = '';
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
    
    try {
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
    } catch (error) {
        console.error("Upload error:", error);
        alert("Upload failed: " + error.message);
    }
}

async function loadStats() {
    try {
        const response = await fetch(`${API_URL}/api/stats`, { headers: getHeaders() });
        if (!response.ok) throw new Error("Failed to load stats");
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
        if (!response.ok) throw new Error("Failed to load transactions");
        const data = await response.json();
        renderDashboard(data);
    } catch (error) {
        console.error("Load transactions error:", error);
    }
}

async function loadHighRisk() {
    try {
        const response = await fetch(`${API_URL}/api/high-risk`, { headers: getHeaders() });
        if (!response.ok) throw new Error("Failed to load high risk");
        const data = await response.json();
        renderDashboard(data);
    } catch (error) {
        console.error("Load high risk error:", error);
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
                backgroundColor: 'rgba(54, 162, 235, 0.6)'
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

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log("Page loaded, showing login");
    showLogin();
});
