import os
import requests
from simple_salesforce import Salesforce


def get_case(case_number: str) -> dict:
    """
    Retrieves a case record based on the provided case number.

    Args:
        case_number: The case number to retrieve.

    Returns:
        A dictionary containing case details or an error message.
    """

    print("=" * 50)
    print("::::[TOOL CALLED] GET CASE BY NUMBER::::")
    print(f"Case Number:: {case_number}")
    print("=" * 50)

    # def get_connection_credentials(connection_id: str, providerConfigKey: str):
    #     base_url = os.getenv("NANGO_BASE_URL")
    #     secret_key = os.getenv("NANGO_SECRET_KEY")
    #     url = f"{base_url}/connection/{connection_id}"
    #     params = {
    #         "provider_config_key": providerConfigKey,
    #         "refresh_token": "true",
    #     }
    #     headers = {"Authorization": f"Bearer {secret_key}"}
    #     response = requests.get(url, headers=headers, params=params)
    #     response.raise_for_status()
    #     return response.json()

    try:
        # instance_url = os.getenv("SALESFORCE_INSTANCE_URL")
        # salesforce_connection_id = os.getenv("SALESFORCE_CONNECTION_ID")
        # credentials = get_connection_credentials(salesforce_connection_id, "salesforce")
        # access_token = credentials["credentials"]["access_token"]
        # sf = Salesforce(instance_url=instance_url, session_id=access_token)
        username = os.getenv("SALESFORCE_USERNAME")
        password = os.getenv("SALESFORCE_PASSWORD")
        security_token = os.getenv("SALESFORCE_SECURITY_TOKEN")
        sf = Salesforce(username=username, password=password, security_token=security_token)
        query = f"SELECT Id FROM Case WHERE CaseNumber = '{case_number}'"
        results = sf.query(query)
        print(f"GET CASE Results:: {results}")
        if results["totalSize"] == 0:
            return {"error": f"Case with CaseNumber '{case_number}' not found."}
        elif results["totalSize"] > 1:
            return {"error": f"Multiple cases found with CaseNumber '{case_number}'."}

        case_id = results["records"][0]["Id"]
        case_data = sf.Case.get(case_id)
        return dict(case_data)

    except Exception as e:
        return {"error": str(e)}