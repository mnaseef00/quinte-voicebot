"""
hangup_call.py
Tool for hanging up a Twilio call.
"""

import os
from typing import Dict
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

def hangup_call(call_sid: str = None) -> Dict[str, str]:
    """
    Hang up an active Twilio call.
    
    Args:
        call_sid: The SID of the call to hang up. If not provided, will use the current call SID.
        
    Returns:
        Dict containing status and message
    """
    try:
        # Initialize Twilio client
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        print("::::[TOOL CALLED] HANGUP CALL  ::::")
        print(f"Call SID: {call_sid}")
        
        if not account_sid or not auth_token:
            return {"status": "error", "message": "Twilio credentials not configured"}
            
        client = Client(account_sid, auth_token)
        
        # If no call_sid provided, we can't hang up a specific call
        if not call_sid:
            return {"status": "error", "message": "Call SID is required to hang up a call"}
            
        # Add a small delay before hanging up to ensure the user hears the final message
        import time
        time.sleep(10)  # 10 second delay
        
        # Update the call status to 'completed' to hang up
        call = client.calls(call_sid).update(status='completed')
        
        return {
            "status": "success", 
            "message": f"Call {call_sid} has been terminated",
            "call_status": call.status
        }
        
    except TwilioRestException as e:
        return {
            "status": "error",
            "message": f"Failed to hang up call: {str(e)}",
            "error_code": e.code if hasattr(e, 'code') else None
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"An unexpected error occurred: {str(e)}"
        }
