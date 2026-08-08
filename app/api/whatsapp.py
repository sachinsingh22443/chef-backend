import os
import logging

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import PlainTextResponse


router = APIRouter(
    prefix="/whatsapp",
    tags=["WhatsApp"],
)

logger = logging.getLogger(__name__)


# =========================================================
# VERIFY TOKEN
# =========================================================

def get_whatsapp_verify_token() -> str:
    return os.getenv(
        "WHATSAPP_VERIFY_TOKEN",
        "eatunity_whatsapp_verify_2026",
    )


# =========================================================
# META WEBHOOK VERIFICATION
# =========================================================

@router.get("/webhook")
async def verify_whatsapp_webhook(
    hub_mode: str | None = Query(
        None,
        alias="hub.mode",
    ),
    hub_verify_token: str | None = Query(
        None,
        alias="hub.verify_token",
    ),
    hub_challenge: str | None = Query(
        None,
        alias="hub.challenge",
    ),
):
    """
    Meta webhook verification endpoint.
    """

    if (
        hub_mode == "subscribe"
        and hub_verify_token == get_whatsapp_verify_token()
    ):
        logger.info(
            "WhatsApp webhook verified successfully"
        )

        return PlainTextResponse(
            content=hub_challenge or ""
        )

    logger.warning(
        "WhatsApp webhook verification failed"
    )

    raise HTTPException(
        status_code=403,
        detail="Verification failed",
    )


# =========================================================
# WHATSAPP WEBHOOK EVENTS
# =========================================================

@router.post("/webhook")
async def whatsapp_webhook(request: Request):
    """
    Receives WhatsApp messages and message-status webhooks.
    """

    try:
        payload = await request.json()

        logger.info(
            "WhatsApp webhook received: %s",
            payload,
        )

        # -------------------------------------------------
        # WHATSAPP BUSINESS ACCOUNT EVENT
        # -------------------------------------------------

        if payload.get("object") != "whatsapp_business_account":
            return {"status": "ignored"}

        entries = payload.get("entry", [])

        for entry in entries:

            changes = entry.get("changes", [])

            for change in changes:

                value = change.get("value", {})

                # =========================================
                # INCOMING MESSAGES
                # =========================================

                messages = value.get("messages", [])

                for message in messages:

                    sender = message.get("from")
                    message_type = message.get("type")

                    logger.info(
                        "WhatsApp message received | sender=%s type=%s",
                        sender,
                        message_type,
                    )

                    # -------------------------------------
                    # TEXT MESSAGE
                    # -------------------------------------

                    if message_type == "text":

                        text = (
                            message
                            .get("text", {})
                            .get("body", "")
                        )

                        logger.info(
                            "WhatsApp text from %s: %s",
                            sender,
                            text,
                        )

                        # Future:
                        # Customer reply processing yahan hoga.

                # =========================================
                # MESSAGE STATUS
                # =========================================

                statuses = value.get("statuses", [])

                for status in statuses:

                    message_id = status.get("id")
                    message_status = status.get("status")
                    recipient = status.get("recipient_id")

                    logger.info(
                        "WhatsApp status | id=%s status=%s recipient=%s",
                        message_id,
                        message_status,
                        recipient,
                    )

        # Meta ko immediately 200 dena important hai
        return {
            "status": "received"
        }

    except Exception as e:

        logger.exception(
            "WhatsApp webhook processing error: %s",
            e,
        )

        # Webhook ko unnecessarily fail nahi karna
        return {
            "status": "received"
        }