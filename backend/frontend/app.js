const API_URL = "https://YOUR-CODESPACE-NAME-8000.app.github.dev";

function loadAll() {
    fetch(API_URL + "/transactions")
        .then(res => res.json())
        .then(data => renderDashboard(data));
}

function loadHighRisk() {
    fetch(API_URL + "/high-risk")
        .then(res => res.json())
        .then(data => renderDashboard(data));
}

function loadVendors() {
    fetch(API_URL + "/vendors")
        .then(res => res.json())
        .then(data => renderVendorStats(data));
}

function renderDashboard(data) {

    const results = document.getElementById("results");
    const stats = document.getElementById("stats");

    if (!data || data.length === 0) {
        results.innerHTML = "No data found";
        return;
    }

    // Stats
    const total = data.length;
    const highRisk = data.filter(t => t.risk_score >= 40).length;

    stats.innerHTML = `
        <div class="card">
            <h3>Total Transactions</h3>
            <p>${total}</p>
        </div>
        <div class="card">
            <h3>High Risk</h3>
            <p>${highRisk}</p>
        </div>
    `;

    // Table
    let html = "<table><tr>";

    const headers = Object.keys(data[0]);

    headers.forEach(h => {
        html += "<th>" + h + "</th>";
    });

    html += "</tr>";

    data.forEach(row => {

        let riskClass = "low";
        if (row.risk_score >= 40) riskClass = "high";
        else if (row.risk_score >= 20) riskClass = "medium";

        html += `<tr class="${riskClass}">`;

        headers.forEach(h => {
            html += "<td>" + row[h] + "</td>";
        });

        html += "</tr>";
    });

    html += "</table>";

    results.innerHTML = html;
}

function renderVendorStats(data) {

    const results = document.getElementById("results");
    const stats = document.getElementById("stats");

    stats.innerHTML = `
        <div class="card">
            <h3>Total Vendors</h3>
            <p>${data.length}</p>
        </div>
    `;

    let html = "<table><tr>";

    const headers = Object.keys(data[0]);

    headers.forEach(h => {
        html += "<th>" + h + "</th>";
    });

    html += "</tr>";

    data.forEach(row => {
        html += "<tr>";

        headers.forEach(h => {
            html += "<td>" + row[h] + "</td>";
        });

        html += "</tr>";
    });

    html += "</table>";

    results.innerHTML = html;
}