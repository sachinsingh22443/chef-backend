import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.api.deps import get_db

load_dotenv()  # 🔥 sabse pehle

# render database
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DATABASE_URL,
    connect_args={"sslmode": "require"}
)




SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)