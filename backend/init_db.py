from database import engine, Base
from models import User, Transaction

print("Creating database tables...")
Base.metadata.create_all(bind=engine)
print("Tables created successfully!")
