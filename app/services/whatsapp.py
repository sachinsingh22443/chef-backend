import os
import logging
from typing import Optional

import httpx


logger = logging.getLogger(__name__)


# =========================================================
# CONFIG
# =========================================================

WHATSAPP_API_VERSION = os.getenv(
    "WHATSAPP_API_VERSION",
    "v23.0",
)


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
# COMMON META API REQUEST
# =========================================================

async def _send_whatsapp_payload(
    recipient: str,
    payload: dict,
) -> dict:

    phone_number_id = get_phone_number_id()
    access_token = get_access_token()

    url = (
        f"https://graph.facebook.com/"
        f"{WHATSAPP_API_VERSION}/"
        f"{phone_number_id}/messages"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
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

        data = response.json()

        if response.is_success:

            logger.info(
                "WhatsApp message accepted by Meta | "
                "recipient=%s | response=%s",
                recipient,
                data,
            )

            return data

        logger.error(
            "WhatsApp API error | "
            "recipient=%s | status=%s | response=%s",
            recipient,
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
            "WhatsApp HTTP error | recipient=%s | error=%s",
            recipient,
            exc,
        )

        raise RuntimeError(
            "Unable to connect to WhatsApp API"
        ) from exc


# =========================================================
# NORMAL TEXT MESSAGE
# =========================================================

async def send_whatsapp_message(
    recipient: str,
    message: str,
) -> dict:

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

    return await _send_whatsapp_payload(
        recipient,
        payload,
    )


# =========================================================
# WHATSAPP TEMPLATE MESSAGE
# =========================================================

async def send_whatsapp_template(
    recipient: str,
    template_name: str,
    parameters: Optional[list[str]] = None,
    language_code: str = "en_US",
) -> dict:
    """
    Send an approved WhatsApp template.

    parameters:
        Values are inserted into {{1}}, {{2}}, {{3}}, etc.
    """

    components = []

    if parameters:
        components.append(
            {
                "type": "body",
                "parameters": [
                    {
                        "type": "text",
                        "text": str(value),
                    }
                    for value in parameters
                ],
            }
        )

    template = {
        "name": template_name,
        "language": {
            "code": language_code,
        },
    }

    if components:
        template["components"] = components

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "template",
        "template": template,
    }

    return await _send_whatsapp_payload(
        recipient,
        payload,
    )


# =========================================================
# SEND TEMPLATE TO ALL ADMINS
# =========================================================

async def send_template_to_admins(
    template_name: str,
    parameters: Optional[list[str]] = None,
    language_code: str = "en_US",
) -> list[dict]:

    results = []

    admin_numbers = get_admin_numbers()

    if not admin_numbers:

        logger.warning(
            "No WhatsApp admin numbers configured"
        )

        return results

    for number in admin_numbers:

        try:

            result = await send_whatsapp_template(
                recipient=number,
                template_name=template_name,
                parameters=parameters,
                language_code=language_code,
            )

            results.append(
                {
                    "number": number,
                    "success": True,
                    "response": result,
                }
            )

        except Exception as exc:

            logger.exception(
                "Failed to send WhatsApp template "
                "to %s",
                number,
            )

            results.append(
                {
                    "number": number,
                    "success": False,
                    "error": str(exc),
                }
            )

    return results


# =========================================================
# SEND TEXT TO ALL ADMINS
# =========================================================

async def send_whatsapp_to_admins(
    message: str,
) -> list[dict]:

    results = []

    admin_numbers = get_admin_numbers()

    if not admin_numbers:

        logger.warning(
            "No WhatsApp admin numbers configured"
        )

        return results

    for number in admin_numbers:

        try:

            result = await send_whatsapp_message(
                recipient=number,
                message=message,
            )

            results.append(
                {
                    "number": number,
                    "success": True,
                    "response": result,
                }
            )

        except Exception as exc:

            logger.exception(
                "Failed to send WhatsApp notification "
                "to %s",
                number,
            )

            results.append(
                {
                    "number": number,
                    "success": False,
                    "error": str(exc),
                }
            )

    return results


# =========================================================
# NORMAL ORDER NOTIFICATION
# =========================================================

async def send_new_order_whatsapp(
    order_id: str,
    customer_name: str,
    amount: float,
    items: str,
    payment_method: str = "COD",
    status: str = "Confirmed",
) -> list[dict]:

    template_name = os.getenv(
        "WHATSAPP_ORDER_TEMPLATE",
        "new_order_admin",
    )

    parameters = [
        str(order_id),
        str(customer_name),
        str(items),
        f"{amount:.2f}",
        str(payment_method),
        str(status),
    ]

    logger.info(
        "📱 SENDING ORDER WHATSAPP TEMPLATE | "
        "order_id=%s | customer=%s",
        order_id,
        customer_name,
    )

    return await send_template_to_admins(
        template_name=template_name,
        parameters=parameters,
        language_code="en_US",
    )


# =========================================================
# SUBSCRIPTION NOTIFICATION
# =========================================================

async def send_new_subscription_whatsapp(
    customer_name: str,
    plan_name: str,
    duration: str,
    amount: float,
    breakfast_included: bool = False,
    status: str = "Active",
) -> list[dict]:

    template_name = os.getenv(
        "WHATSAPP_SUBSCRIPTION_TEMPLATE",
        "new_subscription_admin",
    )

    breakfast_text = (
        "Included"
        if breakfast_included
        else "Not Included"
    )

    parameters = [
        str(customer_name),
        str(plan_name),
        str(duration),
        f"{amount:.2f}",
        breakfast_text,
        str(status),
    ]

    logger.info(
        "📱 SENDING SUBSCRIPTION WHATSAPP | "
        "customer=%s | plan=%s",
        customer_name,
        plan_name,
    )

    return await send_template_to_admins(
        template_name=template_name,
        parameters=parameters,
        language_code="en_US",
    )


# =========================================================
# BREAKFAST ADD-ON
# =========================================================

async def send_breakfast_addon_whatsapp(
    customer_name: str,
    plan_name: str,
    price_per_day: float,
    remaining_days: int,
    status: str = "Active",
) -> list[dict]:

    template_name = os.getenv(
        "WHATSAPP_BREAKFAST_TEMPLATE",
        "breakfast_addon_admin",
    )

    parameters = [
        str(customer_name),
        str(plan_name),
        "Added",
        f"{price_per_day:.2f}",
        str(remaining_days),
        str(status),
    ]

    logger.info(
        "📱 SENDING BREAKFAST ADD-ON WHATSAPP | "
        "customer=%s | plan=%s",
        customer_name,
        plan_name,
    )

    return await send_template_to_admins(
        template_name=template_name,
        parameters=parameters,
        language_code="en_US",
    )


# =========================================================
# BREAKFAST / LUNCH / DINNER ON-OFF
# =========================================================

async def send_subscription_meal_whatsapp(
    customer_name: str,
    meal_type: str,
    action: str,
    date: str,
    amount: float,
) -> list[dict]:

    action = action.lower().strip()

    if action not in ["on", "off"]:
        raise ValueError(
            "Invalid diet action. Use 'on' or 'off'."
        )

    template_name = os.getenv(
        "WHATSAPP_MEAL_TEMPLATE",
        "diet_meal_update_admin",
    )

    meal_name = meal_type.title()

    if action == "off":

        amount_text = (
            f"Wallet Credit: ₹{amount:.2f}"
        )

        final_message = (
            "Today's meal has been cancelled."
        )

    else:

        amount_text = (
            f"Wallet Debit: ₹{amount:.2f}"
        )

        final_message = (
            "Today's meal has been restored."
        )

    parameters = [
        str(customer_name),
        meal_name,
        action.upper(),
        str(date),
        f"{amount:.2f}",
        f"{amount_text}\n{final_message}",
    ]

    logger.info(
        "📱 SENDING DIET WHATSAPP | "
        "customer=%s | meal=%s | action=%s",
        customer_name,
        meal_name,
        action.upper(),
    )

    return await send_template_to_admins(
        template_name=template_name,
        parameters=parameters,
        language_code="en_US",
    )