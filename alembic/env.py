import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# 1. .env FILE LOAD KAREIN
from dotenv import load_dotenv
load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 2. .env SE DATABASE_URL UTHAKAR ALEMBIC MEIN SET KAREIN
database_url = os.getenv("DATABASE_URL")
if database_url:
    # Render aur Neon ke liye 'postgres://' ko 'postgresql://' mein badalna zaroori hai
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    config.set_main_option("sqlalchemy.url", database_url)

# 3. APNE MODELS KO EK DUM SAHI SEQUENCE MEIN CONNECT KAREIN
from app.db.base import Base

# Aapke main.py ke exact imports jo error ko fix karenge
from app.models.refresh_token import RefreshToken
from app.models import (
    user,
    menu,
    order,
    order_item,
    subscription,
    subscription_plan,
    subscription_meal_schedule,
    subscription_plan_menu_cycle,
    wallet,
    wallet_transaction,
    menu_cycle,
    menu_date_override,
    tomorrow_special_pre_order,
)
# Agar cart ya address ke alag models hain jo main.py me import nahi the, unhe bhi safe side import kar lete hain:
try:
    from app.models import address, cart, review, tomorrow_special
except ImportError:
    pass

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
