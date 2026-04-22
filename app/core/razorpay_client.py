import razorpay
import os

client = razorpay.Client(auth=(
    os.getenv("RAZORPAY_KEY_ID"),
    os.getenv("RAZORPAY_KEY_SECRET")
))

# print("KEY:", os.getenv("RAZORPAY_KEY_ID"))
# print("SECRET:", os.getenv("RAZORPAY_KEY_SECRET"))