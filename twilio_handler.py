import json
import base64
import asyncio
from fastapi import (
    APIRouter,
    WebSocket,
    Request,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse
from twilio.twiml.voice_response import VoiceResponse, Connect, Hangup
from loguru import logger
import aiohttp
from function_call_manager import FunctionCallManager
from dotenv import load_dotenv
import os

load_dotenv()

router = APIRouter()
function_call_manager = FunctionCallManager()



@router.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """Handle incoming call and return TwiML response to connect to Media Stream."""
    response = VoiceResponse()
    response.say(
        "Thanks for calling! Please wait while we connect your call to the AI voice assistant"
    )
    response.pause(length=1)
    response.say("O.K. you can start talking!")
    host = request.url.hostname
    connect = Connect()
    connect.stream(url=f"wss://{host}/api/v1/twilio/media-stream")
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")


async def initialize_session(openai_ws):
    """Control initial session with OpenAI."""

    SYSTEM_MESSAGE = f"""
## Complete Customer Support Workflow

### 1. Initial Greeting and Customer ID Collection
* Greet the user: "Hi, thanks for calling Quinte FT Support. Please provide your four-digit customer ID."
* Wait for the user to provide their customer ID.
* Invoke `verification_tool` with `customer_id`.
* Let the tool's response be `verification_step1`.

### 2. Customer ID Verification Processing
* If `verification_step1.status` is `"customer_not_found"`:
  * Say: "I'm sorry, but I couldn't find an account associated with this customer ID. Please contact our customer support team during business hours for assistance."
  * Invoke `hangup_call` tool to end the call.
  * (END verification - FAILED)

* If `verification_step1.status` is `"invalid_input"`:
  * Say: "It seems there was an issue verifying your identity. Please contact our customer support team during business hours for assistance."
  * Invoke `hangup_call` tool to end the call.
  * (END verification - FAILED)

* If `verification_step1.status` is `"security_question_provided"`:
  * Let `customer_name` = `verification_step1.customer_name`
  * Let `security_question` = `verification_step1.question`
  * Say: "Hello [customer_name]. Thanks for providing your customer ID."
  * Say: "For security purposes, I need to perform security check before we proceed."
  * Say: "Please answer the following security question: [security_question]"
  * Proceed to Security Question Verification.

### 3. Security Question Verification
* Wait for the user to provide their answer.
* Let `user_answer` be the user's response.

* If user indicates they are not sure, don't know, or requests to skip:
  * Say: "I understand you're not able to answer this security question. For security reasons, I cannot proceed without verification. Please contact our customer support team during business hours for assistance."
  * Invoke `hangup_call` tool to end the call.
  * (END verification - FAILED)

* Invoke `verification_tool` with `customer_id` and `user_answer` immediately after the answer is provided.
* Let the tool's response be `verification_step2`.

### 4. Final Verification Processing
* If `verification_step2.status` is `"verification_failed"`:
  * Say: "I'm sorry, I couldn't verify your identity based on the answer provided. For security reasons, we can't proceed further. Please contact our customer support team during business hours for assistance. If your account has been frozen, they will help you restore access."
  * Invoke `hangup_call` tool to end the call.
  * (END verification - FAILED)

* If `verification_step2.status` is `"invalid_input"`:
  * Say: "There was an issue processing your answer. Let's try that again."
  * Return to Security Question Verification (Step 3).

* If `verification_step2.status` is `"verified"`:
  * Say: "Thank you. Your identity has been successfully verified."
  * (Verification SUCCEEDS - PROCEED to Issue Collection)
  
### 5. Understanding the Issue
* (This section only runs if verification SUCCEEDED)
* Ask: "Now that we've verified your account, how can I help you today?"
* If the user requests the status of a ticket or case (e.g., asks for 'ticket status', 'case status', 'update on my ticket', etc.):
    * Ask for the ticket number: "Could you please provide the ticket number so I can check the current status for you?"
    * Once the ticket number is provided, immediately invoke the `get_case` tool with the provided `case_number` and inform the user of the current status.
* Otherwise, if the user shares a new issue or request:
    * Check if you have sufficient information to create a support ticket:
        * Clear description of the issue
    * Once sufficient information is collected:
        * Ask: "Thanks for sharing. Have you created a ticket for this before?"
        * If yes: 
            * Ask for the ticket number: "Could you please provide the ticket number? so that i can check the current status of it"
            * Invoke the `get_case` tool with the provided `case_number`.
            * If case is found:
                * Inform the user: "I found your ticket. Let me review it."
                * Review the ticket details (e.g., status, description) and tell the user about the current status of the ticket.
                * Ask: "Is there anything else I can help you with?"
            * If case is not found:
                * Inform the user: "I couldn't find your ticket."
                * Ask: "Is there anything else I can help you with?"
        * If no:
            * Tell the user: "I'll help you create a new ticket. Please hold on while I'm creating the ticket."
            * Invoke the `create_case` tool, passing:
                - Use the details provided by the user as the `subject` (create a subject of the ticket from users description),
                - Use the verified `contact_phone` (this is the `phone_number` collected during successful verification), and pass any mentioned monetary value as `disputed_amount` (as a number/double)
            * Inform the user: "I've created a new ticket for you. Let me know when you are ready to note down the number."
* Do NOT provide or mention the ticket number until the user has confirmed they are ready.
* When the user confirms they are ready, provide the ticket number.
* Ask: "Should I repeat the ticket number? Or is there anything else I can help you with?"
* If the user indicates they do not need any more help:
    * Ask: "How would you rate this interaction from 1 to 5?"
    * After receiving the rating, thank the user for their feedback.
    * Invoke the `hangup_call` tool to end the call.

    """
    VOICE = "sage"

    session_update = {
        "type": "session.update",
        "session": {
            "turn_detection": {
                "type": "server_vad",
                "create_response": True,  # only in conversation mode
                "interrupt_response": False,  # only in conversation mode
            },
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "voice": VOICE,
            "instructions": SYSTEM_MESSAGE,
            "modalities": ["text", "audio"],
            "temperature": 0.6,
            "tools": function_call_manager.tool_defs(),
            "input_audio_transcription": {
                "model": "gpt-4o-mini-transcribe",
                "language": "en",
            },
            "input_audio_noise_reduction": {
                "type": "near_field"
            },
            "include": [ 
                "item.input_audio_transcription.logprobs",
            ],
        },
    }
    print("Sending session update:", json.dumps(session_update))
    await openai_ws.send_str(json.dumps(session_update))


async def send_initial_conversation_item(openai_ws):
    """Send initial conversation item if AI talks first."""
    initial_conversation_item = {
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "Greet the user with 'Hi there!, How can I help you today?'",
                }
            ],
        },
    }
    await openai_ws.send_str(json.dumps(initial_conversation_item))
    await openai_ws.send_str(json.dumps({"type": "response.create"}))


@router.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle WebSocket connections between Twilio and OpenAI Realtime API."""
    logger.info("Twilio client connected to /twilio/media-stream")
    await websocket.accept()

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    LOG_EVENT_TYPES = [
        "error",
        "response.content.done",
        "rate_limits.updated",
        "response.done",
        "input_audio_buffer.committed",
        "input_audio_buffer.speech_stopped",
        "input_audio_buffer.speech_started",
        "session.created",
    ]
    SHOW_TIMING_MATH = False

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1",
    }

    # Conversation history for both user and agent
    conversation_history = []
    def print_conversation_history():
        logger.info("Current Conversation History:")
        logger.info(json.dumps(conversation_history, indent=2))

    async with aiohttp.ClientSession() as session:
        openai_ws_url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17"
        logger.info(f"Connecting to OpenAI WebSocket: {openai_ws_url}")
        async with session.ws_connect(
            openai_ws_url,
            headers=headers,
        ) as openai_ws:
            await initialize_session(openai_ws)
            # Session state
            stream_sid = None
            incoming_call_sid = None  
            latest_media_timestamp = 0
            last_assistant_item = None
            mark_queue = []
            response_start_timestamp_twilio = None

            async def receive_from_twilio():
                nonlocal stream_sid, latest_media_timestamp, last_assistant_item, response_start_timestamp_twilio, incoming_call_sid
                try:
                    async for message in websocket.iter_text():
                        data = json.loads(message)
                        # aiohttp's ClientWebSocketResponse does not have .open, check .closed instead
                        if data["event"] == "media" and not openai_ws.closed:
                            latest_media_timestamp = int(data["media"]["timestamp"])
                            audio_append = {
                                "type": "input_audio_buffer.append",
                                "audio": data["media"]["payload"],
                            }
                            await openai_ws.send_str(json.dumps(audio_append))
                        elif data["event"] == "start":
                            logger.info(f"Start event data: {json.dumps(data, indent=2)}")
                            stream_sid = data["start"].get("streamSid")
                            incoming_call_sid = data["start"].get("callSid")
                            logger.info(f"Incoming stream has started. Stream SID: {stream_sid}, Call SID: {incoming_call_sid}")
                            response_start_timestamp_twilio = None
                            latest_media_timestamp = 0
                            last_assistant_item = None
                        elif data["event"] == "mark":
                            if mark_queue:
                                mark_queue.pop(0)
                except WebSocketDisconnect:
                    logger.info("Twilio WebSocket client disconnected.")
                    if not openai_ws.closed:
                        await openai_ws.close()

            async def send_to_twilio():
                nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio
                try:
                    while True:
                        msg = await openai_ws.receive()
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            response = json.loads(msg.data)
                            if response["type"] in LOG_EVENT_TYPES:
                                logger.debug(
                                    f"Received event: {response['type']} {response}"
                                )

                            if (
                                response.get("type") == "response.audio.delta"
                                and "delta" in response
                            ):
                                audio_payload = base64.b64encode(
                                    base64.b64decode(response["delta"])
                                ).decode("utf-8")
                                audio_delta = {
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": audio_payload},
                                }
                                await websocket.send_json(audio_delta)
                                if response_start_timestamp_twilio is None:
                                    response_start_timestamp_twilio = (
                                        latest_media_timestamp
                                    )
                                    if SHOW_TIMING_MATH:
                                        logger.info(
                                            f"Setting start timestamp for new response: {response_start_timestamp_twilio}ms"
                                        )
                                if response.get("item_id"):
                                    last_assistant_item = response["item_id"]
                                await send_mark(websocket, stream_sid)

                            if response["type"] == "response.done":
                                outputs = response["response"]["output"]
                                for item in outputs:
                                    if item["type"] == "message":
                                        for content in item["content"]:
                                            if content["type"] == "audio":
                                                transcript = content.get("transcript", "")
                                                if transcript:
                                                    conversation_history.append({"agent": transcript})
                                                    print_conversation_history()

                            # --- Handle OpenAI transcription events ---
                            if response.get("type") == "conversation.item.input_audio_transcription.delta":
                                # log partial (incremental) user transcript
                                partial = response.get("delta", "")
                                logger.info(f"[User partial transcript] {partial}")

                            if response.get("type") == "conversation.item.input_audio_transcription.completed":
                                # log final user transcript and add to conversation history
                                transcript = response.get("transcript", "")
                                logger.info(f"[User final transcript] {transcript}")
                                if transcript:
                                    conversation_history.append({"user": transcript})
                                    print_conversation_history()

                            # --- Function calling support ---
                            if response.get("type") == "response.done":
                                output_items = response.get("response", {}).get(
                                    "output", []
                                )
                                for item in output_items:
                                    if item and item.get("type") == "function_call":
                                        fn_name = item.get("name")
                                        fn_args = item.get("arguments", "{}")
                                        call_id = item.get("call_id")
                                        logger.info(
                                            f"Function call requested: {fn_name} call_id={call_id}"
                                        )
                                        # Parse the function arguments
                                        args = json.loads(fn_args) if fn_args else {}
                                        
                                        # Add conversation history to the arguments if it's the create_case function
                                        if fn_name == 'create_case':
                                            args['conversation_history'] = conversation_history
                                        # Add call_sid to hangup_call arguments if available
                                        elif fn_name == 'hangup_call':
                                            args['call_sid'] = incoming_call_sid
                                        
                                        result = (
                                            await function_call_manager.call_function(
                                                fn_name, json.dumps(args)
                                            )
                                        )
                                        fn_result_event = {
                                            "type": "conversation.item.create",
                                            "item": {
                                                "type": "function_call_output",
                                                "call_id": call_id,
                                                "output": json.dumps(result),
                                            },
                                        }
                                        await openai_ws.send_str(
                                            json.dumps(fn_result_event)
                                        )
                                        response_event = {
                                            "type": "response.create",
                                        }
                                        await openai_ws.send_str(
                                            json.dumps(response_event)
                                        )
                                        logger.info(
                                            f"Sending function_call_result for {call_id}: {result}"
                                        )

                            if (
                                response.get("type")
                                == "input_audio_buffer.speech_started"
                            ):
                                logger.info("Speech started detected.")
                                if last_assistant_item:
                                    logger.info(
                                        f"Interrupting response with id: {last_assistant_item}"
                                    )
                                    await handle_speech_started_event()
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"WebSocket error: {msg.data}")
                            break
                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.CLOSING,
                        ):
                            logger.info("OpenAI WebSocket closed.")
                            break
                except Exception as e:
                    logger.error(f"Error in send_to_twilio: {e}")

            async def handle_speech_started_event():
                nonlocal response_start_timestamp_twilio, last_assistant_item
                logger.info("Handling speech started event.")
                if mark_queue and response_start_timestamp_twilio is not None:
                    elapsed_time = (
                        latest_media_timestamp - response_start_timestamp_twilio
                    )
                    if SHOW_TIMING_MATH:
                        logger.info(
                            f"Calculating elapsed time for truncation: {latest_media_timestamp} - {response_start_timestamp_twilio} = {elapsed_time}ms"
                        )
                    if last_assistant_item:
                        if SHOW_TIMING_MATH:
                            logger.info(
                                f"Truncating item with ID: {last_assistant_item}, Truncated at: {elapsed_time}ms"
                            )
                        truncate_event = {
                            "type": "conversation.item.truncate",
                            "item_id": last_assistant_item,
                            "content_index": 0,
                            "audio_end_ms": elapsed_time,
                        }
                        await openai_ws.send_str(json.dumps(truncate_event))
                    await websocket.send_json(
                        {"event": "clear", "streamSid": stream_sid}
                    )
                    mark_queue.clear()
                    last_assistant_item = None
                    response_start_timestamp_twilio = None

            async def send_mark(connection, stream_sid):
                if stream_sid:
                    mark_event = {
                        "event": "mark",
                        "streamSid": stream_sid,
                        "mark": {"name": "responsePart"},
                    }
                    await connection.send_json(mark_event)
                    mark_queue.append("responsePart")

            await asyncio.gather(receive_from_twilio(), send_to_twilio())