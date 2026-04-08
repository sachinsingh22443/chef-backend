import random
import redis

# ✅ Redis connection (safe)
try:
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    r.ping()
except redis.ConnectionError:
    r = None
    print("❌ Redis not connected")


# 🔥 Generate OTP
def generate_otp(phone: str):
    if not r:
        raise Exception("Redis not available")

    otp = str(random.randint(100000, 999999))

    key = f"otp:{phone}"  # ✅ better key naming
    r.setex(key, 300, otp)  # 5 min expiry

    return otp


# 🔥 Verify OTP
def verify_otp(phone: str, otp: str):
    if not r:
        raise Exception("Redis not available")

    key = f"otp:{phone}"
    stored = r.get(key)

    if not stored:
        return False

    # ✅ match
    if stored == otp:
        r.delete(key)  # 🔥 OTP one-time use
        return True

    return False