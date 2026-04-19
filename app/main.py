from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.session import engine
from app.db.base import Base

from app.api.v1 import send_otp
# 🔹 Models (important for table creation)

# 🔹 Routers
from app.api.v1 import auth, users, menu as menu_api
from app.api.v1 import dashboard, review, tomorrow_special, notification, subscription, orders
from app.api.v1 import cart
from app.api.v1 import address
from app.models import user, menu, order, order_item, subscription_plan

import os
from dotenv import load_dotenv

# 🔥 ENV LOAD
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)

# 🔥 CLOUDINARY LOAD (VERY IMPORTANT)
import app.core.cloudinary_config

# 🔥 APP INIT
app = FastAPI(title="Chef Backend API 🚀")


# 🔥 CORS CONFIG
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 👉 production me specific domain dalna
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 🔥 DATABASE INIT
try:
    Base.metadata.create_all(bind=engine)
    print("✅ Database Connected")
except Exception as e:
    print("❌ Database Error:", e)


# 🔥 ROUTES REGISTER
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


# 🔥 ROOT
@app.get("/")
def home():
    return {
        "status": "success",
        "message": "Chef Backend Running 🚀"
    }