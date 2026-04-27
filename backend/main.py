from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import pandas as pd
from io import StringIO
import numpy as np
from sklearn.ensemble import IsolationForest
from datetime import datetime, timedelta
import hashlib
import os
import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

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

# ==================== AUTH SETUP ====================
def get_password_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password, hashed_password):
    return get_password_hash(plain_password) == hashed_password

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(username: str = None, db: Session = Depends(get_db)):
    if not username:
        return None
    return db.query(User).filter(User.username == username).first()

# ==================== FASTAPI APP ====================
app = FastAPI(title="LedgerLens API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== LANDING PAGE CONTENT ====================
LANDING_CONTENT = {
    "company": "LedgerLens",
    "tagline": "AI-Powered Financial Anomaly Detection for Modern Businesses",
    "description": "LedgerLens helps businesses detect suspicious financial activity before it becomes a problem. Using advanced AI and machine learning, we analyze transaction patterns, flag anomalies, and provide actionable insights.",
    "features": [
        "🚨 Real-time anomaly detection",
        "📊 Interactive financial dashboards",
        "🔒 Bank-grade security",
        "📑 Audit-ready reports",
        "🤖 AI-powered fraud detection",
        "🏢 Multi-tenant architecture"
    ],
    "pricing": [
        {"plan": "Starter", "price": "R999/month", "features": ["Up to 1,000 transactions", "Basic analytics", "Email support"]},
        {"plan": "Professional", "price": "R2,499/month", "features": ["Up to 10,000 transactions", "Advanced AI", "Priority support", "API access"]},
        {"plan": "Enterprise", "price": "Custom", "features": ["Unlimited transactions", "Custom AI models", "Dedicated support", "SLA guarantee"]}
    ]
}

# ==================== HEALTH CHECK ====================
@app.get("/")
def root():
    return LANDING_CONTENT

@app.get("/api/health")
def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# ==================== AUTH ENDPOINTS ====================
@app.post("/api/register")
def register(username: str, email: str, password: str, company_name: str = "", db: Session = Depends(get_db)):
    try:
        existing_user = db.query(User).filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username or email already registered")
        
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
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return {
        "access_token": user.username,
        "token_type": "bearer",
        "user_id": user.id,
        "company": user.company_name,
        "username": user.username
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

# ==================== CSV UPLOAD (User-Specific) ====================
@app.post("/api/upload")
async def upload_csv(
    file: UploadFile = File(...),
    username: str = Header(None),
    db: Session = Depends(get_db)
):
    try:
        user = get_current_user(username, db)
        if not user:
            # Create demo user for testing
            user = db.query(User).first()
            if not user:
                user = User(
                    username="demo",
                    email="demo@demo.com",
                    hashed_password=get_password_hash("demo123"),
                    company_name="Demo Company"
                )
                db.add(user)
                db.commit()
                db.refresh(user)
        
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
        
        # Clear user's old transactions
        db.query(Transaction).filter(Transaction.user_id == user.id).delete()
        
        # Add new transactions
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
        raise HTTPException(status_code=500, detail=str(e))

# ==================== DATA RETRIEVAL (User-Specific) ====================
@app.get("/api/transactions")
def get_transactions(username: str = Header(None), db: Session = Depends(get_db)):
    user = get_current_user(username, db)
    if not user:
        return []
    transactions = db.query(Transaction).filter(Transaction.user_id == user.id).all()
    return [{
        "id": t.id, 
        "date": t.date.isoformat() if t.date else None,
        "vendor": t.vendor, 
        "amount": t.amount, 
        "risk_score": t.risk_score, 
        "is_anomaly": t.is_anomaly
    } for t in transactions]

@app.get("/api/stats")
def get_stats(username: str = Header(None), db: Session = Depends(get_db)):
    user = get_current_user(username, db)
    if not user:
        return {"total": 0, "high_risk": 0, "anomalies": 0, "total_amount": 0}
    
    transactions = db.query(Transaction).filter(Transaction.user_id == user.id).all()
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

# ==================== REPORT GENERATION ====================
@app.post("/api/generate-report")
async def generate_report(username: str = Header(None), db: Session = Depends(get_db)):
    user = get_current_user(username, db)
    if not user:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    transactions = db.query(Transaction).filter(Transaction.user_id == user.id).all()
    if not transactions:
        raise HTTPException(status_code=404, detail="No transactions found")
    
    # Create PDF report
    report_path = f"/tmp/report_{user.id}_{datetime.utcnow().timestamp()}.pdf"
    doc = SimpleDocTemplate(report_path, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#667eea'))
    story.append(Paragraph(f"LedgerLens Financial Report", title_style))
    story.append(Paragraph(f"<b>Company:</b> {user.company_name}", styles['Normal']))
    story.append(Paragraph(f"<b>Generated:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Summary
    total_amount = sum(t.amount for t in transactions)
    high_risk_count = sum(1 for t in transactions if t.risk_score >= 40)
    anomaly_count = sum(1 for t in transactions if t.is_anomaly)
    
    summary_data = [
        ["Metric", "Value"],
        ["Total Transactions", str(len(transactions))],
        ["Total Amount", f"R{total_amount:,.2f}"],
        ["High Risk Transactions", str(high_risk_count)],
        ["AI-Detected Anomalies", str(anomaly_count)]
    ]
    
    summary_table = Table(summary_data)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))
    
    # Transactions table
    story.append(Paragraph("Detailed Transaction Report", styles['Heading2']))
    story.append(Spacer(1, 10))
    
    table_data = [["Date", "Vendor", "Amount (R)", "Risk Score", "AI Anomaly"]]
    for t in transactions[:100]:  # Limit to 100 for PDF
        table_data.append([
            t.date.strftime('%Y-%m-%d') if t.date else "N/A",
            t.vendor,
            f"{t.amount:,.2f}",
            str(t.risk_score),
            "⚠️ Yes" if t.is_anomaly else "✓ No"
        ])
    
    transaction_table = Table(table_data)
    transaction_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    story.append(transaction_table)
    
    # Build PDF
    doc.build(story)
    
    # Return PDF as downloadable
    with open(report_path, "rb") as f:
        pdf_content = f.read()
    
    os.remove(report_path)
    
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=ledgerlens_report_{user.company_name}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"}
    )

from fastapi.responses import Response
