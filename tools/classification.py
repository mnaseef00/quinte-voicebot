from openai import OpenAI
import json
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()  # Optional, if using .env file
client = OpenAI()


class Classification(BaseModel):
    priority: str
    tags: list[str]
    justification: str
    confidence_score: float | None = None


prompt = """
You are an AI assistant tasked with classifying customer support transcripts for a financial institution. Your
goal is to determine the priority level and assign appropriate tags to each transcript based on its
content. Here's how to proceed:

1. First, carefully read the following transcript content. The transcript is a conversation between a customer and a financial institution's customer support agent.

2. Determine the priority level of the transcript. Consider the following criteria:

3. Assign appropriate tags to the transcript. Multiple tags can be assigned based on the content.

Transcript Format:
[
    {'user': 'Hello'}, 
    {'agent': 'Hi, thanks for calling Quinte FT Support'},
    ...and so on
]

Urgent Priority:
- Immediate attention required (response needed within hours)
- Potential financial loss or security breach involved
- System-wide issues affecting multiple customers
- Time-sensitive regulatory matters
- Keywords/Indicators: 
  * Fraud Related:
    - "unauthorized transaction", "fraud alert", "suspicious activity"
    - "account compromised", "identity theft", "money stolen"
    - "unknown charges"
  * Security Related:
    - "security breach", "phishing attempt", "data leak"
    - "password compromised"
  * System Critical:
    - "system down", "service outage", "cannot access account"
    - "payment system failure", "mass transaction failure"
  * Regulatory/Legal:
    - "compliance breach", "regulatory deadline", "legal notice"
    - "court order", "subpoena"
  * Customer Impact:
    - "urgent assistance required", "significant financial loss"
    - "business disruption", "immediate action required"
    - "emergency assistance"

High Priority:
- Response needed within 24 hours
- Individual customer account issues
- Specific transaction disputes
- Service disruptions for individual customers
- Keywords/Indicators:
  * Account Issues:
    - "account locked", "account freeze", "access denied"
    - "login problems", "account restriction"
  * Transaction Problems:
    - "failed transfer", "payment rejection", "missing payment"
    - "double charge", "transaction error", "payment declined"
  * Dispute Related:
    - "dispute", "chargeback", "transaction dispute"
    - "billing error", "wrong amount"
  * Service Issues:
    - "service unavailable", "app not working"
    - "cannot complete transaction", "error message"
  * Time Sensitive:
    - "deadline tomorrow", "urgent update needed"
    - "immediate response required", "pending transaction"

Medium Priority:
- Response needed within 48 hours
- General account inquiries requiring research
- Non-urgent service requests
- Transaction status inquiries
- Keywords/Indicators:
  * Account Related:
    - "account inquiry", "balance discrepancy", "statement request"
    - "account settings", "update profile"
  * Transaction Status:
    - "status update", "payment status", "transfer confirmation"
    - "transaction history", "payment schedule"
  * Loan/Financial:
    - "loan information", "interest rates", "payment terms"
    - "loan modification", "refinance options"
  * Service Requests:
    - "change request", "service upgrade", "account maintenance"
    - "limit increase"
  * Information Needs:
    - "clarification needed", "additional information"
    - "account features", "service details"

Low Priority:
- Response needed within 72 hours
- General information requests
- Documentation requests
- Feature inquiries
- Keywords/Indicators:
  * General Information:
    - "information about", "how to", "general question"
    - "learn more", "details about"
  * Documentation:
    - "documentation request", "copy of statement"
    - "tax documents", "proof of payment", "receipt copy"
  * Product/Service Info:
    - "product features", "service comparison", "pricing information"
    - "account types", "new services"
  * Educational:
    - "explanation needed", "account tutorial"
    - "user guide", "best practices"
  * Feedback:
    - "suggestion", "feedback", "improvement ideas"
    - "feature request"

3. Assign appropriate tags to the email. Multiple tags can be assigned based on the content.
Consider the following tag categories:

- Fraud Alert/Report: Unauthorized transactions, suspicious activities, security concerns
- Dispute Related: Transaction disputes, charge disagreements, service quality issues
- Compliance/Regulatory: Regulatory reporting, compliance inquiries, policy matters
- Transaction Issues: Failed transactions, payment problems, processing errors
- Technical Support: System access, online banking problems, app issues
- Account Services: Account maintenance, balance inquiries, statement requests
- Loan Related: Loan applications, payment issues, modification requests
- General Inquiry: Product information, service information, documentation requests

Remember:
- Assign tags based on both explicit mentions and contextual analysis
- There is no limit on the number of tags per email
- The primary tag should be the most critical issue mentioned
- Consider the overall context and tone of the email, not just keywords
- When in doubt about priority, err on the side of higher priority

4. Provide your classification in the following JSON format:

{
    "classification": {
        "priority": string,          // "Urgent", "High", "Medium", or "Low"
        "tags": string[],            // Array of applicable tags
        "justification": string,     // Explanation for priority and tag assignments
        "confidence_score": number   // Optional: 0-1 score indicating classification confidence
    }
}

Example output:
{
    "classification": {
        "priority": "Urgent",
        "tags": ["Fraud Alert/Report", "Transaction Issues", "Account Services"],
        "justification": "Email indicates unauthorized transactions and potential fraud requiring immediate action to prevent financial loss. Multiple tags assigned due to transaction-related fraud affecting account security.",
        "confidence_score": 0.95
    }
}
#NO MARKDOWN ALLOWED

Remember to analyze the email content thoroughly and consider all aspects before making your
classification. If you're unsure about a classification, err on the side of higher priority to
ensure important issues are not overlooked.
"""


def classify_call(transcript: str) -> dict:
    """
    Classify a customer call by priority level and assign relevant tags.

    Args:
        transcript (str): The transcript of the customer's call.

    Returns:
        dict: A dictionary containing classification with priority, tags, justification, and optional confidence.
    """

    print(
        f"OpenAI API Key Loaded: {bool(client.api_key)}"
    )  # Check if API key is perceived by the client
    print("=" * 50)
    print("::::[TOOL CALLED] EMAIL CLASSIFICATION TOOL::::")
    print(f"Email Content:\n{transcript}")
    print("=" * 50)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            temperature=0.8,
            messages=[
                {
                    "role": "system",
                    "content": [{"type": "text", "text": prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": transcript}],
                },
            ],
        )
        content = response.choices[0].message.content  # Correct way to get content
        print(f"Raw response:\n{content}")

        # Parse the JSON string and extract the nested 'classification' object
        data = json.loads(content)
        classification_data = data.get("classification")

        if not classification_data:
            print("Error: 'classification' key not found in AI response.")
            return {"error": "AI response missing 'classification' key."}

        result = Classification.model_validate(
            classification_data
        )  # Validate the nested dictionary
        print(f"Analyzed Result from classification tool: {result}")
        return result.model_dump()
    except Exception as e:
        print(
            f"Error during classification: {type(e).__name__} - {e}"
        )  # Print exception type and message
        import traceback

        traceback.print_exc()  # Print full traceback
        return {"error": str(e)}
