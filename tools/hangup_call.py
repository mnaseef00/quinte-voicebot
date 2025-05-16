"""
hangup_call.py
Tool for signaling a Twilio call hangup in the Quinte Voicebot system.
"""

from typing import Dict

import requests

def hangup_call() -> dict:
    print("::::Calling hang up tool:::::")
    return {"status": "call_hung_up"}
