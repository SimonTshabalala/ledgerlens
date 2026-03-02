from fastapi import FastAPI, UploadFile, File
import pandas as pd
from io import StringIO

app = FastAPI()

@app.get("/")
def root():
    return {"message": "LedgerLens API running"}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), window_days: int = 7):
    """
    Upload CSV and detect duplicate vendor+amount transactions within a date window.
    window_days: how many days to look back for duplicates
    """
    contents = await file.read()
    s = str(contents, 'utf-8')
    df = pd.read_csv(StringIO(s))
    
    if df.empty:
        return {"error": "Uploaded file is empty"}
    
    # Standardize column names
    df.columns = df.columns.str.lower()
    required = {"date", "amount", "vendor"}
    if not required.issubset(set(df.columns)):
        return {"error": "CSV must contain date, amount, vendor columns"}
    
    # Convert date to datetime
    df["date"] = pd.to_datetime(df["date"])
    
    # Sort for logic
    df = df.sort_values(by=["vendor", "amount", "date"])
    
    # Flag duplicates within the window
    flagged_rows = []
    for vendor in df["vendor"].unique():
        vendor_df = df[df["vendor"] == vendor]
        # Check each transaction against all previous transactions within window
        for i, row in vendor_df.iterrows():
            mask = (vendor_df["date"] >= row["date"] - pd.Timedelta(days=window_days)) & \
                   (vendor_df["date"] <= row["date"] + pd.Timedelta(days=window_days)) & \
                   (vendor_df["amount"] == row["amount"]) & \
                   (vendor_df.index != i)
            if vendor_df[mask].shape[0] > 0:
                flagged_rows.append(row.to_dict())
    
    return {
        "total_transactions": len(df),
        "flagged_count": len(flagged_rows),
        "flagged_transactions": flagged_rows
    }