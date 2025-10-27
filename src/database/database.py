import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

password = os.getenv("POSTGRES_PASSWORD", "password")
user = os.getenv("POSTGRES_USER", "postgres")

SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{user}:{password}@localhost/tira_db"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
