import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()  # loads .env

# Main database
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set in .env")
engine = create_engine(DATABASE_URL, echo=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Test database
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if TEST_DATABASE_URL:
    test_engine = create_engine(TEST_DATABASE_URL, echo=True, future=True)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
else:
    TestingSessionLocal = None  # optional fallback

Base = declarative_base()
