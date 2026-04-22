import requests
import os

API_KEY = os.getenv("MSG91_API_KEY")
TEMPLATE_ID = os.getenv("MSG91_TEMPLATE_ID")


def format_phone(phone: str):
    if phone.startswith("91"):
        return phone
    return "91" + phone


def send_otp(phone: str):
    url = "https://api.msg91.com/api/v5/otp"

    phone = format_phone(phone)

    payload = {
        "template_id": TEMPLATE_ID,
        "mobile": phone
    }

    headers = {
        "authkey": API_KEY,
        "Content-Type": "application/json"
    }

    res = requests.post(url, json=payload, headers=headers)
    print("MSG91 SEND OTP:", res.json())  # debug

    return res.json()


def verify_otp(phone: str, otp: str):
    url = "https://api.msg91.com/api/v5/otp/verify"

    phone = format_phone(phone)

    payload = {
        "mobile": phone,
        "otp": otp
    }

    headers = {
        "authkey": API_KEY,
        "Content-Type": "application/json"
    }

    res = requests.post(url, json=payload, headers=headers)
    print("MSG91 VERIFY OTP:", res.json())  # debug

    return res.json()