from fastapi import FastAPI, UploadFile, File
import pandas as pd
from io import StringIO

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, func
from sqlalchemy.orm import sessionmaker, declarative_base, Session

import datetime

# -------------------- DATABASE SETUP --------------------

DATABASE_URL = "sqlite:///./ledgerlens.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime)
    vendor = Column(String)
    amount = Column(Float)
    risk_score = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


Base.metadata.create_all(bind=engine)

# -------------------- APP --------------------

app = FastAPI()


@app.get("/")
def root():
    return {"message": "LedgerLens API running"}


# -------------------- UPLOAD ENDPOINT --------------------

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), window_days: int = 7):

    contents = await file.read()

    df = pd.read_csv(StringIO(contents.decode("utf-8")))

    if df.empty:
        return {"error": "Empty file"}

    df.columns = df.columns.str.lower()

    if not {"date", "amount", "vendor"}.issubset(df.columns):
        return {"error": "CSV must contain date, amount, vendor"}

    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["amount"])

    df["risk_score"] = 0

    # -------- RULE 1: DUPLICATES --------
    df = df.sort_values(by=["vendor", "amount", "date"])

    for vendor in df["vendor"].unique():
        vendor_df = df[df["vendor"] == vendor]

        for i, row in vendor_df.iterrows():
            mask = (
                (vendor_df["amount"] == row["amount"]) &
                (vendor_df["date"] >= row["date"] - pd.Timedelta(days=window_days)) &
                (vendor_df["date"] <= row["date"] + pd.Timedelta(days=window_days)) &
                (vendor_df.index != i)
            )

            if vendor_df[mask].shape[0] > 0:
                df.loc[i, "risk_score"] += 40

    # -------- RULE 2: LARGE ANOMALY --------
    stats = df.groupby("vendor")["amount"].agg(["mean", "std"])

    for i, row in df.iterrows():
        vendor = row["vendor"]

        if vendor in stats.index:
            mean = stats.loc[vendor, "mean"]
            std = stats.loc[vendor, "std"]

            if std > 0 and row["amount"] > mean + (3 * std):
                df.loc[i, "risk_score"] += 30

    # -------- RULE 3: ROUND NUMBERS --------
    df.loc[df["amount"] % 1000 == 0, "risk_score"] += 10

    # -------- SAVE TO DATABASE --------
    db: Session = SessionLocal()

    for _, row in df.iterrows():
        transaction = Transaction(
            date=row["date"],
            vendor=row["vendor"],
            amount=float(row["amount"]),
            risk_score=int(row["risk_score"])
        )
        db.add(transaction)

    db.commit()
    db.close()

    flagged = df[df["risk_score"] > 0]

    return {
        "total_transactions": len(df),
        "flagged_count": len(flagged),
        "flagged_transactions": flagged.to_dict(orient="records")
    }


# -------------------- GET ALL TRANSACTIONS --------------------

@app.get("/transactions")
def get_all_transactions():
    db: Session = SessionLocal()
    transactions = db.query(Transaction).all()
    db.close()

    return [
        {
            "id": t.id,
            "date": t.date,
            "vendor": t.vendor,
            "amount": t.amount,
            "risk_score": t.risk_score
        }
        for t in transactions
    ]


# -------------------- GET HIGH RISK --------------------

@app.get("/high-risk")
def get_high_risk():
    db: Session = SessionLocal()
    transactions = db.query(Transaction).filter(Transaction.risk_score >= 40).all()
    db.close()

    return [
        {
            "id": t.id,
            "date": t.date,
            "vendor": t.vendor,
            "amount": t.amount,
            "risk_score": t.risk_score
        }
        for t in transactions
    ]


# -------------------- GET VENDOR STATS --------------------

@app.get("/vendors")
def get_vendor_stats():
    db: Session = SessionLocal()

    results = db.query(
        Transaction.vendor,
        func.count(Transaction.id),
        func.sum(Transaction.amount),
        func.avg(Transaction.amount)
    ).group_by(Transaction.vendor).all()

    db.close()

    return [
        {
            "vendor": r[0],
            "transaction_count": r[1],
            "total_amount": float(r[2]),
            "average_amount": float(r[3])
        }
        for r in results
    ]