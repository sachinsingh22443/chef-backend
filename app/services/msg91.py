import requests
import os

API_KEY = os.getenv("MSG91_API_KEY")
TEMPLATE_ID = os.getenv("MSG91_TEMPLATE_ID")


def format_phone(phone: str):
    if phone.startswith("91"):
        return phone
    return "91" + phone


def send_otp(phone: str):
    try:
        url = "https://api.msg91.com/api/v5/otp"

        payload = {
            "template_id": TEMPLATE_ID,
            "mobile": format_phone(phone)
        }

        headers = {
            "authkey": API_KEY,
            "Content-Type": "application/json"
        }

        print("PAYLOAD:", payload)

        res = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=15
        )

        print("STATUS CODE:", res.status_code)
        print("RAW RESPONSE:", res.text)

        return res.json()

    except Exception as e:
        print("ERROR:", str(e))
        return {
            "type": "error",
            "message": str(e)
        }

def verify_otp(phone: str, otp: str):
    try:
        url = "https://api.msg91.com/api/v5/otp/verify"

        payload = {
            "mobile": format_phone(phone),
            "otp": otp
        }

        headers = {
            "authkey": API_KEY,
            "Content-Type": "application/json"
        }

        res = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=15
        )

        return res.json()

    except Exception as e:
        return {
            "type": "error",
            "message": str(e)
        }