from pydantic import BaseModel
import os
import requests
from simple_salesforce import Salesforce


class EmailContentModel(BaseModel):
    subject: str | None = None
    body: str | None = None
    # Add other expected fields if necessary, e.g., to: list[str] | None, from_address: str | None

    model_config = {
        "extra": "forbid"  # This ensures additionalProperties: false in the JSON schema
    }


def update_case(
    case_number: str,
    ai_summary_content: str | None = None,
    comments: str | None = None,
    notes: str | None = None,
    email_content: EmailContentModel | None = None,
    priority: str | None = None,
    request_type: str | None = None,
) -> dict:
    """
    Updates an existing Salesforce case record identified by its case number.

    Only provided (non-None) fields will be updated.

    Args:
        case_number: The CaseNumber field of the case to update.
        ai_summary_content: New AI-generated summary content.
        comments: Additional comments for the case.
        notes: Notes for the case.
        email_content: Email content as a structured EmailContentModel (will be JSON stringified).
        priority: Case priority (e.g., Low, Medium, High).
        request_type: Request type field to update.

    Returns:
        A dictionary containing updated case data, or an error message.
    """

    print("=" * 50)
    print("::::[TOOL CALLED] UPDATE SALESFORCE CASE::::")
    print(f"Case Number: {case_number}"),
    print(f"ai_summary_content: {ai_summary_content}")
    print(f"comments: {comments}")
    print(f"notes: {notes}")
    print(f"email_content: {email_content}")
    print(f"priority: {priority}")
    print(f"request_type: {request_type}")
    print("=" * 50)

    try:
        username = os.getenv("SALESFORCE_USERNAME")
        password = os.getenv("SALESFORCE_PASSWORD")
        security_token = os.getenv("SALESFORCE_SECURITY_TOKEN")
        sf = Salesforce(
            username=username, password=password, security_token=security_token
        )

        # Step 1: Find Case ID
        query = f"SELECT Id FROM Case WHERE CaseNumber = '{case_number}'"
        results = sf.query(query)

        if results["totalSize"] == 0:
            return {"error": f"Case with CaseNumber '{case_number}' not found."}
        elif results["totalSize"] > 1:
            return {"error": f"Multiple cases found with CaseNumber '{case_number}'."}

        case_id = results["records"][0]["Id"]

        # Step 2: Prepare update fields
        update_data = {}
        if ai_summary_content is not None:
            update_data["AI_Summary_Content__c"] = ai_summary_content
        if notes is not None:
            update_data["Comments_Notes__c"] = notes
        if comments is not None:
            update_data["Comments"] = comments
        if priority is not None:
            update_data["Priority"] = priority
        if request_type is not None:
            update_data["Request_Type__c"] = request_type
        if email_content is not None:
            try:
                update_data["EmailContent__c"] = email_content.model_dump_json()
            except TypeError as e:
                print(f"Error serializing EmailContentModel: {e}")
                return {"error": f"Failed to serialize email_content to JSON: {e}"}

        if not update_data:
            return {"error": "No fields provided to update."}

        # Step 3: Perform update
        update_response = sf.Case.update(case_id, update_data)

        if update_response == 204:
            print(f"Case {case_number} (ID: {case_id}) updated successfully.")
            updated_case_data = sf.Case.get(case_id)
            return dict(updated_case_data)
        else:
            return {"error": f"Failed to update case. Status code: {update_response}"}

    except Exception as e:
        print(f"An error occurred during case update: {e}")
        return {"error": f"An error occurred: {str(e)}"}
