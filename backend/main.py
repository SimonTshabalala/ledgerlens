from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import pandas as pd
from io import StringIO
import numpy as np
from sklearn.ensemble import IsolationForest
from datetime import datetime, timedelta
import hashlib
import os

# ==================== DATABASE SETUP ====================
DB_PATH = "/tmp/ledgerlens.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==================== MODELS ====================
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    company_name = Column(String, default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    date = Column(DateTime)
    vendor = Column(String)
    amount = Column(Float)
    risk_score = Column(Integer, default=0)
    is_anomaly = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# ==================== SIMPLE AUTH (No bcrypt issues) ====================
def get_password_hash(password):
    """Simple SHA256 hashing for passwords - avoids bcrypt issues"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password, hashed_password):
    """Verify password against hash"""
    return get_password_hash(plain_password) == hashed_password

def create_access_token(data: dict):
    """Simple token creation (for demo)"""
    # For production, use JWT. For now, return simple dict
    return data.get("sub", "")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==================== FASTAPI APP ====================
app = FastAPI(title="LedgerLens API")

# CORS - Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== HEALTH CHECK ====================
@app.get("/")
def root():
    return {"message": "LedgerLens API is running", "version": "2.0", "status": "healthy"}

# ==================== AUTH ENDPOINTS ====================
@app.post("/api/register")
def register(username: str, email: str, password: str, company_name: str = "", db: Session = Depends(get_db)):
    try:
        # Check if user exists
        existing_user = db.query(User).filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username or email already registered")
        
        # Create new user
        hashed_password = get_password_hash(password)
        user = User(
            username=username, 
            email=email, 
            hashed_password=hashed_password, 
            company_name=company_name if company_name else username
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"message": "User created successfully", "user_id": user.id, "username": user.username}
    except Exception as e:
        db.rollback()
        print(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return {
        "access_token": user.username, 
        "token_type": "bearer", 
        "user_id": user.id, 
        "company": user.company_name,
        "username": user.username
    }

@app.get("/api/me")
def get_me(username: str = None, db: Session = Depends(get_db)):
    if not username:
        return {"error": "Not authenticated"}
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return {"error": "User not found"}
    return {
        "id": user.id, 
        "username": user.username, 
        "email": user.email, 
        "company": user.company_name
    }

# ==================== ANOMALY DETECTION ====================
def detect_anomalies(df):
    if len(df) < 10:
        df['is_anomaly'] = False
        return df
    
    features = df[['amount']].copy()
    features['amount_log'] = np.log1p(features['amount'])
    features['amount_zscore'] = (features['amount'] - features['amount'].mean()) / features['amount'].std()
    features = features.fillna(0)
    
    iso_forest = IsolationForest(contamination=0.1, random_state=42)
    df['is_anomaly'] = iso_forest.fit_predict(features) == -1
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

# ==================== CSV UPLOAD ====================
@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...), username: str = None, db: Session = Depends(get_db)):
    try:
        # For now, use first user or create default
        user = db.query(User).first()
        if not user:
            # Create default user if none exists
            default_user = User(
                username="demo",
                email="demo@demo.com",
                hashed_password=get_password_hash("demo123"),
                company_name="Demo Company"
            )
            db.add(default_user)
            db.commit()
            db.refresh(default_user)
            user = default_user
        
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
                user_id=user.id,
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
    except Exception as e:
        db.rollback()
        print(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== DATA RETRIEVAL ====================
@app.get("/api/transactions")
def get_transactions(db: Session = Depends(get_db)):
    transactions = db.query(Transaction).all()
    return [{
        "id": t.id, 
        "date": t.date, 
        "vendor": t.vendor, 
        "amount": t.amount, 
        "risk_score": t.risk_score, 
        "is_anomaly": t.is_anomaly
    } for t in transactions]

@app.get("/api/high-risk")
def get_high_risk(db: Session = Depends(get_db)):
    transactions = db.query(Transaction).filter(Transaction.risk_score >= 40).all()
    return [{
        "id": t.id, 
        "date": t.date, 
        "vendor": t.vendor, 
        "amount": t.amount, 
        "risk_score": t.risk_score
    } for t in transactions]

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    transactions = db.query(Transaction).all()
    if not transactions:
        return {"total": 0, "high_risk": 0, "anomalies": 0, "total_amount": 0}
    
    total = len(transactions)
    high_risk = sum(1 for t in transactions if t.risk_score >= 40)
    anomalies = sum(1 for t in transactions if t.is_anomaly)
    total_amount = sum(t.amount for t in transactions)
    
    return {
        "total": total,
        "high_risk": high_risk,
        "anomalies": anomalies,
        "total_amount": total_amount
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
