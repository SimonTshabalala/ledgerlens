from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, func, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import pandas as pd
from io import StringIO
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from datetime import datetime, timedelta
import hashlib
import os
import enum
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from fastapi.responses import Response

# ==================== DATABASE SETUP ====================
DB_PATH = "/tmp/ledgerlens.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==================== MODELS ====================
class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    date = Column(DateTime, nullable=False)
    vendor = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    transaction_type = Column(String, default="expense")
    category = Column(String, default="Uncategorized")
    risk_score = Column(Integer, default=0)
    is_anomaly = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    company_name = Column(String, default="")
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

# ==================== HEALTH CHECK ====================
@app.get("/")
def root():
    return {
        "company": "LedgerLens",
        "tagline": "AI-Powered Financial Intelligence Platform",
        "status": "operational",
        "version": "3.0"
    }

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

# ==================== CSV UPLOAD ====================
@app.post("/api/upload")
async def upload_csv(
    file: UploadFile = File(...),
    username: str = Header(None),
    db: Session = Depends(get_db)
):
    user = get_current_user(username, db)
    if not user:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    try:
        contents = await file.read()
        df = pd.read_csv(StringIO(contents.decode("utf-8")))
        df.columns = df.columns.str.lower()
        
        required_cols = {"date", "amount", "vendor"}
        if not required_cols.issubset(df.columns):
            raise HTTPException(status_code=400, detail="CSV must have date, amount, vendor columns")
        
        has_type = "transaction_type" in df.columns
        has_category = "category" in df.columns
        
        df["date"] = pd.to_datetime(df["date"])
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df = df.dropna(subset=["amount"])
        
        if has_type:
            df["transaction_type"] = df["transaction_type"].str.lower()
        else:
            df["transaction_type"] = "expense"
        
        if has_category:
            df["category"] = df["category"]
        else:
            df["category"] = "Uncategorized"
        
        df = detect_anomalies(df)
        df['risk_score'] = df.apply(calculate_risk_score, axis=1)
        
        # Delete ONLY this user's transactions
        db.query(Transaction).filter(Transaction.user_id == user.id).delete()
        
        for _, row in df.iterrows():
            transaction = Transaction(
                user_id=user.id,
                date=row["date"],
                vendor=row["vendor"],
                amount=float(row["amount"]),
                transaction_type=row["transaction_type"],
                category=row["category"],
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

# ==================== DATA RETRIEVAL ====================
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
        "transaction_type": t.transaction_type,
        "category": t.category,
        "risk_score": t.risk_score, 
        "is_anomaly": t.is_anomaly
    } for t in transactions]

@app.get("/api/high-risk")
def get_high_risk(username: str = Header(None), db: Session = Depends(get_db)):
    user = get_current_user(username, db)
    if not user:
        return []
    
    transactions = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.risk_score >= 40
    ).all()
    
    return [{
        "id": t.id, 
        "date": t.date.isoformat() if t.date else None,
        "vendor": t.vendor, 
        "amount": t.amount,
        "transaction_type": t.transaction_type,
        "category": t.category,
        "risk_score": t.risk_score, 
        "is_anomaly": t.is_anomaly
    } for t in transactions]

@app.get("/api/stats")
def get_stats(username: str = Header(None), db: Session = Depends(get_db)):
    user = get_current_user(username, db)
    if not user:
        return {"total": 0, "high_risk": 0, "anomalies": 0, "total_amount": 0, "total_income": 0, "total_expense": 0}
    
    transactions = db.query(Transaction).filter(Transaction.user_id == user.id).all()
    if not transactions:
        return {"total": 0, "high_risk": 0, "anomalies": 0, "total_amount": 0, "total_income": 0, "total_expense": 0}
    
    total = len(transactions)
    high_risk = sum(1 for t in transactions if t.risk_score >= 40)
    anomalies = sum(1 for t in transactions if t.is_anomaly)
    total_amount = sum(t.amount for t in transactions)
    total_income = sum(t.amount for t in transactions if t.transaction_type == "income")
    total_expense = sum(t.amount for t in transactions if t.transaction_type == "expense")
    
    # Year-over-year comparison
    current_year = datetime.utcnow().year
    prev_year = current_year - 1
    
    current_year_total = sum(t.amount for t in transactions if t.date.year == current_year)
    prev_year_total = sum(t.amount for t in transactions if t.date.year == prev_year)
    
    yoy_growth = ((current_year_total - prev_year_total) / prev_year_total * 100) if prev_year_total > 0 else 0
    
    # Future prediction
    monthly_data = {}
    for t in transactions:
        month_key = t.date.strftime("%Y-%m")
        monthly_data[month_key] = monthly_data.get(month_key, 0) + t.amount
    
    months = list(range(len(monthly_data)))
    amounts = list(monthly_data.values())
    
    if len(months) >= 3:
        model = LinearRegression()
        model.fit(np.array(months).reshape(-1, 1), amounts)
        next_month_pred = model.predict([[len(months)]])[0]
        next_3_months_pred = model.predict([[len(months) + 3]])[0]
    else:
        next_month_pred = sum(amounts) / len(amounts) if amounts else 0
        next_3_months_pred = next_month_pred * 3
    
    high_risk_total = sum(t.amount for t in transactions if t.risk_score >= 40)
    low_risk_total = sum(t.amount for t in transactions if t.risk_score < 40)
    
    return {
        "total": total,
        "high_risk": high_risk,
        "anomalies": anomalies,
        "total_amount": total_amount,
        "total_income": total_income,
        "total_expense": total_expense,
        "yoy_growth": round(yoy_growth, 2),
        "current_year_total": current_year_total,
        "prev_year_total": prev_year_total,
        "next_month_prediction": round(next_month_pred, 2),
        "next_3_months_prediction": round(next_3_months_pred, 2),
        "high_risk_percentage": round((high_risk_total / total_amount * 100), 2) if total_amount > 0 else 0,
        "low_risk_percentage": round((low_risk_total / total_amount * 100), 2) if total_amount > 0 else 0
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
    
    report_path = f"/tmp/report_{user.id}_{datetime.utcnow().timestamp()}.pdf"
    doc = SimpleDocTemplate(report_path, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#667eea'))
    story.append(Paragraph(f"LedgerLens Financial Intelligence Report", title_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>Company:</b> {user.company_name}", styles['Normal']))
    story.append(Paragraph(f"<b>Report Date:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Executive Summary
    story.append(Paragraph("Executive Summary", styles['Heading2']))
    stats = await get_stats(username, db)
    
    summary_data = [
        ["Metric", "Value"],
        ["Total Transactions", str(stats['total'])],
        ["Total Income", f"R{stats['total_income']:,.2f}"],
        ["Total Expenses", f"R{stats['total_expense']:,.2f}"],
        ["Net Profit/Loss", f"R{stats['total_income'] - stats['total_expense']:,.2f}"],
        ["High Risk Transactions", str(stats['high_risk'])],
        ["AI-Detected Anomalies", str(stats['anomalies'])],
        ["Year-over-Year Growth", f"{stats['yoy_growth']}%"],
        ["High Risk % of Portfolio", f"{stats['high_risk_percentage']}%"]
    ]
    
    summary_table = Table(summary_data, colWidths=[200, 150])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))
    
    # Year-over-Year Comparison
    story.append(Paragraph("Year-over-Year Performance", styles['Heading2']))
    yoy_data = [
        ["Period", "Total Amount"],
        [f"{datetime.utcnow().year - 1}", f"R{stats['prev_year_total']:,.2f}"],
        [f"{datetime.utcnow().year}", f"R{stats['current_year_total']:,.2f}"],
        ["Growth", f"{stats['yoy_growth']}%"]
    ]
    yoy_table = Table(yoy_data, colWidths=[150, 150])
    yoy_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(yoy_table)
    story.append(Spacer(1, 20))
    
    # Future Predictions
    story.append(Paragraph("Financial Forecast", styles['Heading2']))
    prediction_data = [
        ["Prediction Period", "Projected Amount"],
        ["Next Month", f"R{stats['next_month_prediction']:,.2f}"],
        ["Next 3 Months", f"R{stats['next_3_months_prediction']:,.2f}"]
    ]
    prediction_table = Table(prediction_data, colWidths=[150, 150])
    prediction_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(prediction_table)
    story.append(Spacer(1, 20))
    
    # Risk Distribution
    story.append(Paragraph("Risk Distribution", styles['Heading2']))
    risk_data = [
        ["Risk Level", "Percentage"],
        ["High Risk", f"{stats['high_risk_percentage']}%"],
        ["Low Risk", f"{stats['low_risk_percentage']}%"]
    ]
    risk_table = Table(risk_data, colWidths=[150, 150])
    risk_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(risk_table)
    story.append(Spacer(1, 20))
    
    # Detailed Transactions
    story.append(PageBreak())
    story.append(Paragraph("Detailed Transaction Log", styles['Heading1']))
    story.append(Spacer(1, 10))
    
    table_data = [["Date", "Vendor", "Amount (R)", "Type", "Category", "Risk Score", "Anomaly"]]
    for t in transactions[:200]:
        table_data.append([
            t.date.strftime('%Y-%m-%d') if t.date else "N/A",
            t.vendor,
            f"{t.amount:,.2f}",
            t.transaction_type.upper(),
            t.category,
            str(t.risk_score),
            "⚠️ Yes" if t.is_anomaly else "✓ No"
        ])
    
    transaction_table = Table(table_data, repeatRows=1)
    transaction_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ]))
    story.append(transaction_table)
    
    doc.build(story)
    
    with open(report_path, "rb") as f:
        pdf_content = f.read()
    
    os.remove(report_path)
    
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=LedgerLens_Report_{user.company_name}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOFcat > main.py << 'EOF'
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, func, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import pandas as pd
from io import StringIO
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from datetime import datetime, timedelta
import hashlib
import os
import enum
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from fastapi.responses import Response

# ==================== DATABASE SETUP ====================
DB_PATH = "/tmp/ledgerlens.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==================== MODELS ====================
class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    date = Column(DateTime, nullable=False)
    vendor = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    transaction_type = Column(String, default="expense")
    category = Column(String, default="Uncategorized")
    risk_score = Column(Integer, default=0)
    is_anomaly = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    company_name = Column(String, default="")
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

# ==================== HEALTH CHECK ====================
@app.get("/")
def root():
    return {
        "company": "LedgerLens",
        "tagline": "AI-Powered Financial Intelligence Platform",
        "status": "operational",
        "version": "3.0"
    }

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

# ==================== CSV UPLOAD ====================
@app.post("/api/upload")
async def upload_csv(
    file: UploadFile = File(...),
    username: str = Header(None),
    db: Session = Depends(get_db)
):
    user = get_current_user(username, db)
    if not user:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    try:
        contents = await file.read()
        df = pd.read_csv(StringIO(contents.decode("utf-8")))
        df.columns = df.columns.str.lower()
        
        required_cols = {"date", "amount", "vendor"}
        if not required_cols.issubset(df.columns):
            raise HTTPException(status_code=400, detail="CSV must have date, amount, vendor columns")
        
        has_type = "transaction_type" in df.columns
        has_category = "category" in df.columns
        
        df["date"] = pd.to_datetime(df["date"])
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df = df.dropna(subset=["amount"])
        
        if has_type:
            df["transaction_type"] = df["transaction_type"].str.lower()
        else:
            df["transaction_type"] = "expense"
        
        if has_category:
            df["category"] = df["category"]
        else:
            df["category"] = "Uncategorized"
        
        df = detect_anomalies(df)
        df['risk_score'] = df.apply(calculate_risk_score, axis=1)
        
        # Delete ONLY this user's transactions
        db.query(Transaction).filter(Transaction.user_id == user.id).delete()
        
        for _, row in df.iterrows():
            transaction = Transaction(
                user_id=user.id,
                date=row["date"],
                vendor=row["vendor"],
                amount=float(row["amount"]),
                transaction_type=row["transaction_type"],
                category=row["category"],
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

# ==================== DATA RETRIEVAL ====================
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
        "transaction_type": t.transaction_type,
        "category": t.category,
        "risk_score": t.risk_score, 
        "is_anomaly": t.is_anomaly
    } for t in transactions]

@app.get("/api/high-risk")
def get_high_risk(username: str = Header(None), db: Session = Depends(get_db)):
    user = get_current_user(username, db)
    if not user:
        return []
    
    transactions = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.risk_score >= 40
    ).all()
    
    return [{
        "id": t.id, 
        "date": t.date.isoformat() if t.date else None,
        "vendor": t.vendor, 
        "amount": t.amount,
        "transaction_type": t.transaction_type,
        "category": t.category,
        "risk_score": t.risk_score, 
        "is_anomaly": t.is_anomaly
    } for t in transactions]

@app.get("/api/stats")
def get_stats(username: str = Header(None), db: Session = Depends(get_db)):
    user = get_current_user(username, db)
    if not user:
        return {"total": 0, "high_risk": 0, "anomalies": 0, "total_amount": 0, "total_income": 0, "total_expense": 0}
    
    transactions = db.query(Transaction).filter(Transaction.user_id == user.id).all()
    if not transactions:
        return {"total": 0, "high_risk": 0, "anomalies": 0, "total_amount": 0, "total_income": 0, "total_expense": 0}
    
    total = len(transactions)
    high_risk = sum(1 for t in transactions if t.risk_score >= 40)
    anomalies = sum(1 for t in transactions if t.is_anomaly)
    total_amount = sum(t.amount for t in transactions)
    total_income = sum(t.amount for t in transactions if t.transaction_type == "income")
    total_expense = sum(t.amount for t in transactions if t.transaction_type == "expense")
    
    # Year-over-year comparison
    current_year = datetime.utcnow().year
    prev_year = current_year - 1
    
    current_year_total = sum(t.amount for t in transactions if t.date.year == current_year)
    prev_year_total = sum(t.amount for t in transactions if t.date.year == prev_year)
    
    yoy_growth = ((current_year_total - prev_year_total) / prev_year_total * 100) if prev_year_total > 0 else 0
    
    # Future prediction
    monthly_data = {}
    for t in transactions:
        month_key = t.date.strftime("%Y-%m")
        monthly_data[month_key] = monthly_data.get(month_key, 0) + t.amount
    
    months = list(range(len(monthly_data)))
    amounts = list(monthly_data.values())
    
    if len(months) >= 3:
        model = LinearRegression()
        model.fit(np.array(months).reshape(-1, 1), amounts)
        next_month_pred = model.predict([[len(months)]])[0]
        next_3_months_pred = model.predict([[len(months) + 3]])[0]
    else:
        next_month_pred = sum(amounts) / len(amounts) if amounts else 0
        next_3_months_pred = next_month_pred * 3
    
    high_risk_total = sum(t.amount for t in transactions if t.risk_score >= 40)
    low_risk_total = sum(t.amount for t in transactions if t.risk_score < 40)
    
    return {
        "total": total,
        "high_risk": high_risk,
        "anomalies": anomalies,
        "total_amount": total_amount,
        "total_income": total_income,
        "total_expense": total_expense,
        "yoy_growth": round(yoy_growth, 2),
        "current_year_total": current_year_total,
        "prev_year_total": prev_year_total,
        "next_month_prediction": round(next_month_pred, 2),
        "next_3_months_prediction": round(next_3_months_pred, 2),
        "high_risk_percentage": round((high_risk_total / total_amount * 100), 2) if total_amount > 0 else 0,
        "low_risk_percentage": round((low_risk_total / total_amount * 100), 2) if total_amount > 0 else 0
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
    
    report_path = f"/tmp/report_{user.id}_{datetime.utcnow().timestamp()}.pdf"
    doc = SimpleDocTemplate(report_path, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#667eea'))
    story.append(Paragraph(f"LedgerLens Financial Intelligence Report", title_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>Company:</b> {user.company_name}", styles['Normal']))
    story.append(Paragraph(f"<b>Report Date:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Executive Summary
    story.append(Paragraph("Executive Summary", styles['Heading2']))
    stats = await get_stats(username, db)
    
    summary_data = [
        ["Metric", "Value"],
        ["Total Transactions", str(stats['total'])],
        ["Total Income", f"R{stats['total_income']:,.2f}"],
        ["Total Expenses", f"R{stats['total_expense']:,.2f}"],
        ["Net Profit/Loss", f"R{stats['total_income'] - stats['total_expense']:,.2f}"],
        ["High Risk Transactions", str(stats['high_risk'])],
        ["AI-Detected Anomalies", str(stats['anomalies'])],
        ["Year-over-Year Growth", f"{stats['yoy_growth']}%"],
        ["High Risk % of Portfolio", f"{stats['high_risk_percentage']}%"]
    ]
    
    summary_table = Table(summary_data, colWidths=[200, 150])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))
    
    # Year-over-Year Comparison
    story.append(Paragraph("Year-over-Year Performance", styles['Heading2']))
    yoy_data = [
        ["Period", "Total Amount"],
        [f"{datetime.utcnow().year - 1}", f"R{stats['prev_year_total']:,.2f}"],
        [f"{datetime.utcnow().year}", f"R{stats['current_year_total']:,.2f}"],
        ["Growth", f"{stats['yoy_growth']}%"]
    ]
    yoy_table = Table(yoy_data, colWidths=[150, 150])
    yoy_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(yoy_table)
    story.append(Spacer(1, 20))
    
    # Future Predictions
    story.append(Paragraph("Financial Forecast", styles['Heading2']))
    prediction_data = [
        ["Prediction Period", "Projected Amount"],
        ["Next Month", f"R{stats['next_month_prediction']:,.2f}"],
        ["Next 3 Months", f"R{stats['next_3_months_prediction']:,.2f}"]
    ]
    prediction_table = Table(prediction_data, colWidths=[150, 150])
    prediction_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(prediction_table)
    story.append(Spacer(1, 20))
    
    # Risk Distribution
    story.append(Paragraph("Risk Distribution", styles['Heading2']))
    risk_data = [
        ["Risk Level", "Percentage"],
        ["High Risk", f"{stats['high_risk_percentage']}%"],
        ["Low Risk", f"{stats['low_risk_percentage']}%"]
    ]
    risk_table = Table(risk_data, colWidths=[150, 150])
    risk_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(risk_table)
    story.append(Spacer(1, 20))
    
    # Detailed Transactions
    story.append(PageBreak())
    story.append(Paragraph("Detailed Transaction Log", styles['Heading1']))
    story.append(Spacer(1, 10))
    
    table_data = [["Date", "Vendor", "Amount (R)", "Type", "Category", "Risk Score", "Anomaly"]]
    for t in transactions[:200]:
        table_data.append([
            t.date.strftime('%Y-%m-%d') if t.date else "N/A",
            t.vendor,
            f"{t.amount:,.2f}",
            t.transaction_type.upper(),
            t.category,
            str(t.risk_score),
            "⚠️ Yes" if t.is_anomaly else "✓ No"
        ])
    
    transaction_table = Table(table_data, repeatRows=1)
    transaction_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ]))
    story.append(transaction_table)
    
    doc.build(story)
    
    with open(report_path, "rb") as f:
        pdf_content = f.read()
    
    os.remove(report_path)
    
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=LedgerLens_Report_{user.company_name}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
