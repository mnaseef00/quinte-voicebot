import os
import requests


def generate_case_summary(
    sentiment_analysis: str, classification: str, users_description: str
) -> str:
    """
    Generates a structured case summary using Claude API from provided inputs.
    Args:
        sentiment_analysis: String with tone and sentiment indicators.
        classification: Categorization of request type and priority.
        users_description: Text of customer's description of issue.
    Returns:
        A structured case summary string.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    print(f"Anthropic API Key Loaded: {bool(api_key)}")  # Check if API key is loaded

    print("=" * 60)
    print("::::[TOOL CALLED] GENERATE CASE SUMMARY::::")
    print("=" * 60)
    print("🎯 Sentiment Analysis Input:\n", sentiment_analysis)
    print("📂 Classification Input:\n", classification)
    print("📧 Customer Email Input:\n", users_description)
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
You are a Summary Agent that analyzes inputs from multiple banking support agents and creates concise case summaries.
## Input:
- Sentiment Analysis: {sentiment_analysis}
- Classification: {classification}
- User Description request/issue: {users_description}
## Output Format:
### 1. CASE OVERVIEW
- Brief description of customer request/issue
### 2. STATUS SUMMARY
✅ Completed steps  
⏳ Pending steps  
🔜 Next steps  
### 3. KEY INSIGHTS
- Sentiment indicators  
- Compliance considerations  
- Special handling  
Use emojis and keep the language professional and clear.
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
        return summary_text
    except Exception as e:
        print(
            f"❌ Failed to parse Claude response: {type(e).__name__} - {e}"
        )  # Print exception type and message
        return {"error": f"Parsing Claude response failed: {e}"}