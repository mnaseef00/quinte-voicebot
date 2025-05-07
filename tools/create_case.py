from agents import function_tool
import os
import requests
from simple_salesforce import Salesforce
import base64
from urllib.parse import urlparse
from datetime import datetime

@function_tool(
    name_override="create_case",
    description_override="Create a Salesforce case with provided subject, phone number, body, disputed amount, and description.",
    strict_mode=True
)
def create_case(
    subject: str,
    contact_phone: str,
    body: str,
    disputed_amount: float | None = None,
    description: str | None = None,
    ai_summary_content: str | None = None,
    priority: str | None = None,
    request_type: str | None = None,
) -> dict:
    """
    Creates a case record based on the provided details.

    Args:
        subject: The subject of the case.
        contact_phone: The phone number of the customer.
        body: The body of the email.
        disputed_amount: Optional disputed amount in numbers only (no currency symbol).
        description: Optional detailed case description.
    """
    print("="*50)
    print("::::[TOOL CALLED] CREATE CASE::::")
    print(f"Subject: {subject}")
    print(f"Contact Phone: {contact_phone}")
    print(f"Body: {body}")
    print(f"Disputed Amount: {disputed_amount}")
    print(f"Description: {description}")
    print(f"AI Summary Content: {ai_summary_content}")
    print(f"Priority: {priority}")
    print(f"Request Type: {request_type}")
    print("="*50)

    def get_connection_credentials(connection_id: str, providerConfigKey: str):
        base_url = os.getenv("NANGO_BASE_URL")
        secret_key = os.getenv("NANGO_SECRET_KEY")
        url = f"{base_url}/connection/{connection_id}"
        params = {
            "provider_config_key": providerConfigKey,
            "refresh_token": "true",
        }
        headers = {"Authorization": f"Bearer {secret_key}"}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def format_internal_comments(subject: str, body: str) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"""
Original Complaint (Received through Voicebot: {timestamp})
----------------------------------------
Subject: {subject}
{body}
"""

    # Authenticate with Salesforce
    instance_url = os.getenv("SALESFORCE_INSTANCE_URL")
    salesforce_connection_id = os.getenv("SALESFORCE_CONNECTION_ID")
    credentials = get_connection_credentials(salesforce_connection_id, "salesforce")
    access_token = credentials["credentials"]["access_token"]
    sf = Salesforce(instance_url=instance_url, session_id=access_token)

    # Prepare case data
    case_data = {
        "Subject": subject,
        "Description": description,
        "SuppliedPhone": contact_phone,
        "Origin": "Web",
        "Status": "Pending",
        "Request_Subject_Name__c": subject,
        "Disputed_Amount__c": str(disputed_amount) if disputed_amount else None,
        "Comments": format_internal_comments(subject,body),
        "Assigned_To__c": "005dM00000BANfRQAX",
    }
    
    if ai_summary_content is not None:
        case_data["AI_Summary_Content__c"] = ai_summary_content
    if priority is not None:
        case_data["Priority"] = priority
    if request_type is not None:
        case_data["Request_Type__c"] = request_type

    # Create the case
    response = sf.Case.create(case_data)
    case_id = response["id"]
    case_data_res = dict(sf.Case.get(case_id))

    print(f"Case created successfully with ID: {case_id}")

    # Placeholder for attachments
    attachment_files = []
    if attachment_files:
        for attachment_url in attachment_files:
            try:
                response = requests.get(attachment_url, stream=True)
                response.raise_for_status()
                parsed_url = urlparse(attachment_url)
                file_name = os.path.basename(parsed_url.path) or "attachment_from_url"
                base64_file_content = base64.b64encode(response.content).decode("utf-8")

                attachment_data = {
                    "ParentId": case_id,
                    "Name": f"CUSTOMER_{file_name}",
                    "Body": base64_file_content,
                    "Description": f"Customer Document from {attachment_url}",
                }

                attachment_response = sf.Attachment.create(attachment_data)
                print(f"Attachment uploaded: {attachment_response}")
            except Exception as e:
                print(f"Attachment error: {e}")

    return case_data_res
