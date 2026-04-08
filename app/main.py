from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.db.session import engine
from app.db.base import Base

# models
from app.models import user, menu, order, order_item

# routers
from app.api.v1 import auth, users, menu as menu_api
from app.api.v1 import dashboard, review, tomorrow_special, notification, subscription, orders

import os
from dotenv import load_dotenv

# 🔥 FIX: सही तरीके से env load करो
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)

app = FastAPI()

# 🔥 CORS (production में domain डालना)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # बाद में बदलना
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔥 uploads folder safe बनाओ
if not os.path.exists("uploads"):
    os.makedirs("uploads")

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 🔥 DB create
Base.metadata.create_all(bind=engine)

# 🔥 ROUTES
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(menu_api.router, prefix="/menu", tags=["Menu"])

app.include_router(orders.router)
app.include_router(subscription.router)
app.include_router(notification.router)
app.include_router(tomorrow_special.router)
app.include_router(dashboard.router)
app.include_router(review.router)

# 🔥 root
@app.get("/")
def home():
    return {"msg": "Chef Backend Running 🚀"}