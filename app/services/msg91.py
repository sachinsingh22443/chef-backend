import requests
import os

API_KEY = os.getenv("MSG91_API_KEY")
TEMPLATE_ID = os.getenv("MSG91_TEMPLATE_ID")

def send_otp(phone: str):
    url = "https://control.msg91.com/api/v5/otp"

    payload = {
        "template_id": TEMPLATE_ID,
        "mobile": f"91{phone}"
    }

    headers = {
        "authkey": API_KEY,
        "Content-Type": "application/json"
    }

    return requests.post(url, json=payload, headers=headers).json()


def verify_otp(phone: str, otp: str):
    url = "https://control.msg91.com/api/v5/otp/verify"

    payload = {
        "mobile": f"91{phone}",
        "otp": otp
    }

    headers = {
        "authkey": API_KEY,
        "Content-Type": "application/json"
    }

    return requests.post(url, json=payload, headers=headers).json()