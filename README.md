# 🔍 LedgerLens

> *Bringing clarity to your financial chaos — one transaction at a time.*

LedgerLens is a full-stack web-based finance dashboard that delivers **real-time transaction insights**, flags **high-risk anomalies**, and visualizes **vendor-specific spending patterns**. Built for users and businesses who want to stop guessing and start making data-driven financial decisions.

---

## 🚀 Features

- 📊 **Interactive Dashboard** — Stats cards, dynamic charts, and transaction tables all in one view
- ⚠️ **High-Risk Detection** — Anomaly detection powered by machine learning (IsolationForest) flags suspicious transactions automatically
- 🏢 **Vendor Analytics** — Visual breakdown of spending per vendor using interactive bar charts
- 🎨 **Risk-Based Coloring** — Transaction rows are color-coded by risk level (low / medium / high) for instant visual triage
- ⚡ **Real-Time Data** — FastAPI backend serves live transaction data on demand
- 🔄 **Loading States** — Smooth UX with loading indicators during data fetches

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/) |
| **Data Processing** | [Pandas](https://pandas.pydata.org/) |
| **Anomaly Detection** | [scikit-learn](https://scikit-learn.org/) — `IsolationForest` |
| **Frontend** | HTML5 / Vanilla JavaScript |
| **Data Visualization** | [Chart.js](https://www.chartjs.org/) |
| **Styling** | CSS3 |

---

## 📡 API Endpoints

```
GET /transactions     → Retrieve all transactions
GET /high-risk        → Retrieve transactions flagged as high risk
GET /vendors          → Retrieve vendor-specific analytics
```

---

## 📁 Project Structure

```
ledgerlens/
├── backend/
│   ├── main.py          # FastAPI app & endpoints
│   └── data/            # Transaction data & preprocessing
├── frontend/
│   ├── index.html       # Main dashboard UI
│   ├── app.js           # Dashboard logic & data fetching
│   └── styles.css       # Styling & risk-color themes
└── README.md
```

---

## ⚙️ Getting Started

### Prerequisites
- Python 3.9+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/ledgerlens.git
cd ledgerlens

# Install dependencies
pip install fastapi uvicorn pandas scikit-learn

# Run the backend
uvicorn main:app --reload
```

Then open `frontend/index.html` in your browser — or serve it with any static file server.

---

## 🗺️ Roadmap

- [ ] User authentication & role-based access
- [ ] Expanded anomaly detection models
- [ ] Mobile-responsive UI overhaul
- [ ] Data export functionality (CSV & PDF)
- [ ] Email alerts for high-risk transaction spikes

---

## 🏆 Achievements

- ✅ Built a full-stack web application from scratch
- ✅ Integrated real-time data visualization with Chart.js
- ✅ Implemented ML-based anomaly detection (IsolationForest)
- ✅ Dynamic risk-highlighted transaction tables
- ✅ Modular, extensible codebase ready for future features

---

## 📄 License

This project is original work , from scrach to finish.. but it's still "learning work" hence its licenced under an MIT license
--

<p align="center">Built with tonnes of brain power( yah i went through it fr!)  — <em>LedgerLens sees what others miss.</em></p>