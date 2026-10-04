import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# ============================================================
# DELIVERY PARTNER EARNING
# ============================================================

DELIVERY_EARNING_PER_ORDER = float(
    os.getenv("DELIVERY_EARNING_PER_ORDER", "20")
)