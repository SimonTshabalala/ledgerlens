from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import pandas as pd
from io import StringIO
import numpy as np
from sklearn.ensemble import IsolationForest

from database import engine, SessionLocal
from models import Base, User, Transaction
from auth import get_password_hash, verify_password, create_access_token, get_current_user, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="LedgerLens API", description="Financial Anomaly Detection System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",  # Allow all for now (for testing)
        "https://ledgerlens-green.vercel.app",
        "http://localhost:3000",
        "http://localhost:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== AUTHENTICATION ====================

@app.post("/api/register")
def register(username: str, email: str, password: str, company_name: str = "", db: Session = Depends(get_db)):
    existing_user = db.query(User).filter((User.username == username) | (User.email == email)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already registered")
    
    hashed_password = get_password_hash(password)
    user = User(username=username, email=email, hashed_password=hashed_password, company_name=company_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User created successfully", "user_id": user.id}

@app.post("/api/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer", "user_id": user.id, "company": user.company_name}

@app.get("/api/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "email": current_user.email, "company": current_user.company_name}

# ==================== ANOMALY DETECTION ENGINE ====================

def detect_anomalies(df):
    """AI-powered anomaly detection using Isolation Forest"""
    if len(df) < 10:
        df['is_anomaly'] = False
        return df
    
    features = df[['amount']].copy()
    
    features['amount_log'] = np.log1p(features['amount'])
    features['amount_zscore'] = (features['amount'] - features['amount'].mean()) / features['amount'].std()
    
    iso_forest = IsolationForest(contamination=0.1, random_state=42)
    df['is_anomaly'] = iso_forest.fit_predict(features[['amount', 'amount_log', 'amount_zscore']]) == -1
    
    return df

def calculate_risk_score(row):
    risk = 0
    
    if row['amount'] > 10000:
        risk += 30
    elif row['amount'] > 5000:
        risk += 20
    elif row['amount'] > 1000:
        risk += 10
    
    if row.get('is_anomaly', False):
        risk += 40
    
    if row['amount'] % 1000 == 0:
        risk += 10
    
    return min(risk, 100)

# ==================== CSV UPLOAD & ANALYSIS ====================

@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    contents = await file.read()
    df = pd.read_csv(StringIO(contents.decode("utf-8")))
    
    df.columns = df.columns.str.lower()
    
    if not {"date", "amount", "vendor"}.issubset(df.columns):
        raise HTTPException(status_code=400, detail="CSV must have date, amount, vendor columns")
    
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["amount"])
    
    df = detect_anomalies(df)
    df['risk_score'] = df.apply(calculate_risk_score, axis=1)
    
    for _, row in df.iterrows():
        transaction = Transaction(
            user_id=current_user.id,
            date=row["date"],
            vendor=row["vendor"],
            amount=float(row["amount"]),
            risk_score=int(row["risk_score"]),
            is_anomaly=bool(row.get("is_anomaly", False))
        )
        db.add(transaction)
    
    db.commit()
    
    flagged = df[df['risk_score'] > 20]
    
    return {
        "total": len(df),
        "anomalies": int(df['is_anomaly'].sum()),
        "flagged_count": len(flagged),
        "transactions": flagged.to_dict(orient="records")
    }

# ==================== DATA RETRIEVAL ====================

@app.get("/api/transactions")
def get_transactions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    transactions = db.query(Transaction).filter(Transaction.user_id == current_user.id).all()
    return [{"id": t.id, "date": t.date, "vendor": t.vendor, "amount": t.amount, "risk_score": t.risk_score, "is_anomaly": t.is_anomaly} for t in transactions]

@app.get("/api/high-risk")
def get_high_risk(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    transactions = db.query(Transaction).filter(Transaction.user_id == current_user.id, Transaction.risk_score >= 40).all()
    return [{"id": t.id, "date": t.date, "vendor": t.vendor, "amount": t.amount, "risk_score": t.risk_score} for t in transactions]

@app.get("/api/stats")
def get_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    transactions = db.query(Transaction).filter(Transaction.user_id == current_user.id).all()
    
    if not transactions:
        return {"total": 0, "high_risk": 0, "anomalies": 0, "total_amount": 0}
    
    df = pd.DataFrame([{"amount": t.amount, "risk_score": t.risk_score, "is_anomaly": t.is_anomaly} for t in transactions])
    
    return {
        "total": len(transactions),
        "high_risk": int(df[df['risk_score'] >= 40].shape[0]),
        "anomalies": int(df[df['is_anomaly'] == True].shape[0]),
        "total_amount": float(df['amount'].sum())
    }

@app.get("/")
def root():
    return {"message": "LedgerLens API is running", "version": "2.0", "features": ["auth", "ai-anomaly-detection", "csv-upload", "multi-tenant"]}
