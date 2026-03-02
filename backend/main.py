from fastapi import FastAPI,UploadFile,UploadFile,File
import pandas as pd
from io import StringIO

app = FastAPI()

@app.get("/")
def root():
    return {"message": "LedgerLens API running" }
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    contents = await file.read()

    #Convert bytes to string
    s = str(contents, 'utf-8')

    #Read into pandas
    df = pd.read_csv(StringIO(s))

    #Basic validation
    if df.empty:
        return {"error": "Uploaded file is empty"}
    
    # --- DUPLICATE DETECTION RULE ---
    # Flag exact duplicate rows
    duplicates = df[df.duplicated(keep=False)]

    # Convert results to dictionary
    flagged = duplicates.to_dict(orient="records")

    return {
        "total_transactions": len(df),
        "duplicate_count": len(duplicates),
        "flagged_transactions": flagged
    }