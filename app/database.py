# app/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()  # loads .env in project root

# ── Main database ──────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set in .env")

engine = create_engine(DATABASE_URL, echo=True, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()

# Optional test DB (kept from your version)
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if TEST_DATABASE_URL:
    test_engine = create_engine(TEST_DATABASE_URL, echo=True, future=True)
    TestingSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
else:
    TestingSessionLocal = None

# ── FastAPI dependency: yields a session per request ───────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
