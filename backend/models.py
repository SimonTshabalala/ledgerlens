from sqlalchemy import Column, Integer, String, Float, DateTime
from database import Base
import datetime

class Transaction(Base):
**tablename** = "transactions"

```
id = Column(Integer, primary_key=True, index=True)
date = Column(DateTime)
vendor = Column(String)
amount = Column(Float)
risk_score = Column(Integer)
created_at = Column(DateTime, default=datetime.datetime.utcnow)
```
