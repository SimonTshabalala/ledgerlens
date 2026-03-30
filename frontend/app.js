const API_URL = "https://fluffy-parakeet-pjgqvv9pp7jc9p4w-8000.app.github.dev";

function showLoading() {
    document.getElementById("results").innerHTML = "Loading...";
}
async function loadAll() {
    showLoading();

    try {
        const res = await fetch(API_URL + "/transactions");

        if (!res.ok) {
            throw new Error("API error");
        }

        const data = await res.json();
        renderDashboard(data);

    } catch (err) {
        document.getElementById("results").innerHTML = "Error loading data";
        console.error(err);
    }
}

function loadHighRisk() {
    showLoading();
    fetch(API_URL + "/high-risk")
        .then(res => res.json())
        .then(data => renderDashboard(data));
}

function loadVendors() {
    showLoading();
    fetch(API_URL + "/vendors")
        .then(res => res.json())
        .then(data => renderVendorStats(data));
}

let chartInstance = null;

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

    // -------- CHART DATA --------
    const vendors = {};
    data.forEach(t => {
        vendors[t.vendor] = (vendors[t.vendor] || 0) + t.amount;
    });

    const labels = Object.keys(vendors);
    const values = Object.values(vendors);

    const ctx = document.getElementById("chartCanvas").getContext("2d");

    if (chartInstance) chartInstance.destroy();

    chartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [{
                label: "Spend per Vendor",
                data: values
            }]
        },
        options: {
            responsive: true
        }
    });

    // -------- TABLE --------
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