const API_URL = "https://fluffy-parakeet-8000.app.github.dev";

const form = document.getElementById("uploadForm");
const fileInput = document.getElementById("csvFile");
const results = document.getElementById("results");

form.addEventListener("submit", async function (e) {
e.preventDefault();

```
const file = fileInput.files[0];

if (!file) {
    results.innerHTML = "Please select a CSV file.";
    return;
}

const formData = new FormData();
formData.append("file", file);

results.innerHTML = "Uploading and analyzing...";

try {
    const response = await fetch(API_URL + "/upload-transactions", {
        method: "POST",
        body: formData
    });

    const data = await response.json();

    if (!data.flagged_transactions || data.flagged_transactions.length === 0) {
        results.innerHTML = "No suspicious transactions found.";
        return;
    }

    let html = "<h3>Flagged Transactions</h3>";
    html += "<table border='1'>";
    
    const headers = Object.keys(data.flagged_transactions[0]);

    html += "<tr>";
    headers.forEach(function(h){
        html += "<th>" + h + "</th>";
    });
    html += "</tr>";

    data.flagged_transactions.forEach(function(row){
        html += "<tr>";
        headers.forEach(function(h){
            html += "<td>" + row[h] + "</td>";
        });
        html += "</tr>";
    });

    html += "</table>";

    results.innerHTML = html;

} catch (error) {
    console.error(error);
    results.innerHTML = "Error connecting to backend.";
}
```

});
