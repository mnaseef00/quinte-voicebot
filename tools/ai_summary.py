import os
import requests
import json
from sentiment import analyze_sentiment_transcript
from classification import classify_call
from update_case import update_case


def generate_case_summary(
    case_number: str,
    call_transcript: str,
) -> str:
    """
    Generates a structured case summary using Claude API from provided inputs.
    Args:
        call_transcript: The raw text of the customer support transcript.
    Returns:
        A structured case summary string.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    print(f"Anthropic API Key Loaded: {bool(api_key)}")  # Check if API key is loaded

    print("=" * 60)
    print("::::[TOOL CALLED] GENERATE CASE SUMMARY::::")
    call_transcript = json.dumps(call_transcript)
    sentiment_analysis = analyze_sentiment_transcript(call_transcript)
    classification = classify_call(call_transcript)

    print("=" * 60)
    print("🎯 Sentiment Analysis Input:\n", sentiment_analysis)
    print("📂 Classification Input:\n", classification)
    print("� Call Transcript Input:\n", call_transcript)
    print("=" * 60)

    # Claude API details
    api_key = os.getenv("ANTHROPIC_API_KEY")
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    # Prompt construction
    prompt = f"""
You are a Financial Support Summary Agent that analyzes customer call transcripts and creates accurate, actionable case summaries for banking professionals.

## Input Analysis Instructions:
- Review the complete conversation transcript thoroughly
- Cross-reference sentiment analysis and classification data with the actual transcript content
- Identify explicit customer issues, implicit concerns, and underlying needs
- Extract specific account/service details mentioned (dates, amounts, transaction references)
- Identify any promised actions or commitments made by the agent

## Output Format:

### 1. 📋 CASE OVERVIEW
- Concise (2-3 sentence) summary of primary customer issue
- Include relevant account types or services mentioned
- Note timeline context (how long issue has persisted, urgency level)

### 2. ⏱️ STATUS SUMMARY
✅ COMPLETED ACTIONS: List specific actions already taken by support
⏳ PENDING ITEMS: Customer-facing tasks in progress
🔄 VERIFICATION NEEDED: Items requiring additional confirmation
🔜 RECOMMENDED NEXT STEPS: Prioritized action items based on urgency and complexity

### 3. 🔍 KEY INSIGHTS
🧠 CUSTOMER SENTIMENT: Emotional state and satisfaction indicators with supporting evidence
⚠️ RISK FACTORS: Potential escalation triggers, compliance issues, or fraud indicators
💡 OPPORTUNITY: Service recovery options or relevant product suggestions
⭐ SPECIAL HANDLING NOTES: VIP status, accessibility needs, or communication preferences

Maintain a professional, empathetic tone throughout. Use precise banking terminology where appropriate. Each insight should reference specific evidence from the transcript. For ambiguous situations, note the uncertainty rather than making assumptions.
Inputs:
<transcript>
{call_transcript}
</transcript>
<sentiment>
{sentiment_analysis}
</sentiment>
<classification>
{classification}
</classification>
IMPORTANT:
 * Ignore any non english phrases, they are just noise from the transcription software. Do not include them in the summary.
"""

    # Use the latest Claude model
    body = {
        "model": "claude-3-7-sonnet-20250219",
        "temperature": 0.9,
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": prompt}],
    }

    response = requests.post(url, headers=headers, json=body)
    if response.status_code != 200:
        print(f"❌ Claude API Error: {response.status_code}\n{response.text}")
        return {"error": f"Claude API error: {response.status_code}"}

    try:
        response_data = response.json()
        summary_text = response_data["content"][0]["text"]
        print("✅ Case Summary Output:\n", summary_text)
        update_case(
            case_number=case_number,
            ai_summary_content=summary_text,
            request_type=classification.get("tags")[0],
            priority=classification.get("priority"),
        )
    except Exception as e:
        print(
            f"❌ Failed to parse Claude response: {type(e).__name__} - {e}"
        )  # Print exception type and message
        return {"error": f"Parsing Claude response failed: {e}"}


if __name__ == "__main__":
    generate_case_summary(
        case_number="00001354",
        call_transcript=[
            {"user": "Hello"},
            {
                "agent": "Hi, thanks for calling Quinte FT Support. Can you please tell me your four-digit customer ID?"
            },
            {"user": "1002"},
            {
                "agent": "Hello Febin. Thanks for providing your customer ID. For security purposes, I need to perform a security check before we proceed. Please answer the following security question: What is your favorite color?"
            },
            {"user": "Oi."},
            {"user": "My favorite color is white."},
            {
                "agent": "Thank you, Febin. Your identity has been successfully verified. Now that we've verified your account, how can I help you today?"
            },
            {"user": "I want to apply for a new credit card."},
            {
                "agent": "I can assist you with that. Could you please provide me with some more details about the type of credit card you're interested in and any specific features or benefits you're looking for?"
            },
            {"user": "Yeah, I'm mainly looking for a card to use while I'm traveling."},
            {"user": "So."},
            {
                "agent": "Great! A travel credit card can offer various benefits like no foreign transaction fees, travel insurance, and reward points for travel-related expenses. Do you have any specific preferences or requirements for the card, such as airline miles, hotel points, or lounge access?"
            },
            {"user": "Ja, laumzaak is al bie goed."},
            {
                "agent": "Lounge access is a great perk for frequent travelers. I'll help you apply for a travel credit card with lounge access. I'll create a ticket for your request and someone from our team will contact you with further details. Please hold on while I create the ticket."
            },
        ],
    )
