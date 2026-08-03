import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DATABASE_URL,

    # Neon PostgreSQL
    connect_args={
        "sslmode": "require"
    },

    # Connection Pool
    pool_pre_ping=True,
    pool_recycle=1800,      # Recycle every 30 min
    pool_size=10,           # Safe for Neon
    max_overflow=20,        # Extra temporary connections
    pool_timeout=30,        # Wait max 30 sec

    # SQLAlchemy 2.x
    future=True,

    # Disable SQL logs in production
    echo=False
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)