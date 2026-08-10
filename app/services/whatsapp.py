import os
import logging

import httpx


logger = logging.getLogger(__name__)


# =========================================================
# CONFIG
# =========================================================

def get_access_token() -> str:
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")

    if not token:
        raise RuntimeError(
            "WHATSAPP_ACCESS_TOKEN is not configured"
        )

    return token


def get_phone_number_id() -> str:
    phone_number_id = os.getenv(
        "WHATSAPP_PHONE_NUMBER_ID"
    )

    if not phone_number_id:
        raise RuntimeError(
            "WHATSAPP_PHONE_NUMBER_ID is not configured"
        )

    return phone_number_id


# =========================================================
# SEND WHATSAPP TEXT MESSAGE
# =========================================================

async def send_whatsapp_message(
    recipient: str,
    message: str,
) -> dict:
    """
    Send a WhatsApp text message using Meta Cloud API.
    """

    phone_number_id = get_phone_number_id()
    access_token = get_access_token()

    url = (
        f"https://graph.facebook.com/v23.0/"
        f"{phone_number_id}/messages"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": message,
        },
    }

    try:

        async with httpx.AsyncClient(
            timeout=20.0
        ) as client:

            response = await client.post(
                url,
                headers=headers,
                json=payload,
            )

        if response.is_success:

            data = response.json()

            logger.info(
                "WhatsApp message sent successfully | recipient=%s",
                recipient,
            )

            return data

        logger.error(
            "WhatsApp API error | status=%s response=%s",
            response.status_code,
            response.text,
        )

        raise RuntimeError(
            f"WhatsApp API error: "
            f"{response.status_code} "
            f"{response.text}"
        )

    except httpx.HTTPError as exc:

        logger.exception(
            "WhatsApp HTTP error: %s",
            exc,
        )

        raise RuntimeError(
            "Unable to connect to WhatsApp API"
        ) from exc


# =========================================================
# ADMIN NUMBERS
# =========================================================

def get_admin_numbers() -> list[str]:

    numbers = []

    number_1 = os.getenv(
        "WHATSAPP_ADMIN_NUMBER_1"
    )

    number_2 = os.getenv(
        "WHATSAPP_ADMIN_NUMBER_2"
    )

    if number_1:
        numbers.append(number_1)

    if number_2:
        numbers.append(number_2)

    return numbers


# =========================================================
# SEND TO ADMINS
# =========================================================

async def send_whatsapp_to_admins(
    message: str,
) -> list[dict]:

    results = []

    for number in get_admin_numbers():

        try:

            result = await send_whatsapp_message(
                recipient=number,
                message=message,
            )

            results.append({
                "number": number,
                "success": True,
                "response": result,
            })

        except Exception as exc:

            logger.exception(
                "Failed to send WhatsApp notification to %s",
                number,
            )

            results.append({
                "number": number,
                "success": False,
                "error": str(exc),
            })

    return results


# =========================================================
# NORMAL ORDER NOTIFICATION
# =========================================================

async def send_new_order_whatsapp(
    order_id: str,
    customer_name: str,
    amount: float,
    items: str,
) -> list[dict]:

    message = (
        "🍱 NEW ORDER\n\n"
        f"Order ID: #{order_id}\n"
        f"Customer: {customer_name}\n"
        f"Items: {items}\n"
        f"Amount: ₹{amount:.2f}\n\n"
        "Status: New Order"
    )

    return await send_whatsapp_to_admins(
        message
    )
    
# =========================================================
# SUBSCRIPTION DIET NOTIFICATION
# =========================================================

async def send_subscription_meal_whatsapp(
    customer_name: str,
    meal_type: str,
    action: str,
    date: str,
    amount: float,
) -> list[dict]:

    if action == "off":
        message = (
            "🥗 DIET UPDATE\n\n"
            f"Customer: {customer_name}\n"
            f"Meal: {meal_type.title()}\n"
            "Action: OFF\n"
            f"Date: {date}\n"
            f"Wallet Credit: ₹{amount:.2f}\n\n"
            "Today's meal has been cancelled."
        )

    elif action == "on":
        message = (
            "🥗 DIET UPDATE\n\n"
            f"Customer: {customer_name}\n"
            f"Meal: {meal_type.title()}\n"
            "Action: ON\n"
            f"Date: {date}\n"
            f"Wallet Debit: ₹{amount:.2f}\n\n"
            "Today's meal has been restored."
        )

    else:
        raise ValueError(
            "Invalid diet action. Use 'on' or 'off'."
        )

    return await send_whatsapp_to_admins(message)