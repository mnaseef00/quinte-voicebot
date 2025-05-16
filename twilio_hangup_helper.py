import os
from twilio.rest import Client
from loguru import logger

def hangup_call_via_api(call_sid: str):
    """End a call using Twilio REST API."""
    logger.info(f"[hangup_call_via_api] Called with call_sid: {call_sid}")
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    logger.info(f"[hangup_call_via_api] account_sid: {account_sid[:6]}... (masked)")
    if not account_sid or not auth_token:
        logger.error("Twilio credentials not set in environment variables.")
        return False
    logger.info("[hangup_call_via_api] Creating Twilio Client...")
    client = Client(account_sid, auth_token)
    try:
        logger.info(f"[hangup_call_via_api] Attempting to hangup call with call_sid: {call_sid}")
        call = client.calls(call_sid).update(status="completed")
        logger.info(f"Call {call_sid} ended via Twilio API.")
        return True
    except Exception as e:
        logger.error(f"Failed to hang up call {call_sid}: {e}")
        return False
