from contextlib import asynccontextmanager
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse

from app.db.session import engine
from app.db.base import Base

# Models
from app.models.refresh_token import RefreshToken
from app.models import user, menu, order, order_item, subscription_plan

# Routers
from app.api.v1 import (
    auth,
    users,
    menu as menu_api,
    dashboard,
    review,
    tomorrow_special,
    notification,
    subscription,
    orders,
    cart,
    address,
    send_otp,
)

# Cloudinary
import app.core.cloudinary_config


# ==========================
# ENV
# ==========================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)


# ==========================
# Lifespan
# ==========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Chef Backend Starting...")

    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database Connected")
    except Exception as e:
        print("❌ Database Error:", e)

    yield

    print("🛑 Chef Backend Shutdown")


# ==========================
# App
# ==========================

app = FastAPI(
    title="Chef Backend API",
    version="1.0.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)


# ==========================
# Middleware
# ==========================

# GZip Compression
app.add_middleware(
    GZipMiddleware,
    minimum_size=1000
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Production me frontend domain use karna
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================
# Routers
# ==========================

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(send_otp.router, prefix="/auth", tags=["Auth"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(menu_api.router, prefix="/menu", tags=["Menu"])

app.include_router(address.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(subscription.router)
app.include_router(notification.router)
app.include_router(tomorrow_special.router)
app.include_router(dashboard.router)
app.include_router(review.router)


# ==========================
# Health Check
# ==========================

@app.get("/health", include_in_schema=False)
async def health():
    return {
        "status": "healthy"
    }


# ==========================
# Root
# ==========================
@app.get("/ping")
async def ping():
    return {"status": "alive"}

@app.get("/")
async def root():
    return {
        "status": "success",
        "message": "Chef Backend Running 🚀"
    }
    