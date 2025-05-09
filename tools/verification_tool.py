import os
import json
from agents import function_tool

@function_tool(
    name_override="verification_tool",
    description_override="Handles customer verification using phone number and a security question. "
                         "1. Initial call with 'phone_number': Returns security question if customer exists. "
                         "2. Second call with 'phone_number' and 'answer': Validates answer. "
                         "If correct, returns 'verified' status. "
                         "Returns 'customer_not_found', 'verification_failed', or 'no_security_question_configured' as appropriate.",
    strict_mode=True
)
def verification_tool(phone_number: str, answer: str | None = None):
    print("="*50)
    print("::::[TOOL CALLED] VERIFICATION TOOL::::")
    print(f"phone_number: {phone_number}")
    if answer is not None: print(f"answer: {answer}")

    if not phone_number:
        print("No phone_number provided.")
        print("="*50)
        result = {
            "status": "invalid_input",
            "message": "Input 'phone_number' is required."
        }
        print(f"Returning: {result}")
        return result
        
    # For initial phone lookup, customer_id is not required

    # --- Input Cleaning --- 
    def clean_string(input_str):
        if not isinstance(input_str, str):
            input_str = str(input_str) # Ensure it's a string
        cleaned = input_str.replace(' ', '').replace('-', '').replace('_', '')
        return cleaned.lower().strip()
    
    cleaned_phone_number = clean_string(phone_number)
    cleaned_answer = None
    if answer is not None:
        cleaned_answer = clean_string(answer)
    # ----------------------

    # Get the directory of the current script
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Load security questions from JSON file
    security_questions_path = os.path.join(base_dir, 'assets', 'security_questions.json')
    with open(security_questions_path, 'r') as f:
        security_questions_data = json.load(f)
        security_questions = security_questions_data.get('security_questions', {})
    
    # Load customers from JSON file
    customers_path = os.path.join(base_dir, 'assets', 'customers.json')
    with open(customers_path, 'r') as f:
        customers_data = json.load(f)
        customers = customers_data.get('customers', [])
        
    print(f"Successfully loaded data from JSON files")

    # Find customer by phone number
    found_customer_record = None
    for cust_data in customers:
        if cleaned_phone_number == clean_string(cust_data.get("phone_number", "")):
            found_customer_record = cust_data
            break

    if not found_customer_record:
        print("--- LOOKUP RESULT (CUSTOMER NOT FOUND) ---")
        result = {
            "status": "customer_not_found",
            "message": "No customer found with the provided phone number."
        }
        print(f"Returning: {result}")
        return result

    # Ensure account_status exists, default to 'active' if not present
    if "account_status" not in found_customer_record:
        found_customer_record["account_status"] = "active"
    
    # Check if account is active
    if found_customer_record["account_status"].lower() != "active":
        print(f"--- ACCOUNT NOT ACTIVE: {found_customer_record['account_status']} ---")
        result = {
            "status": "verification_failed",
            "message": f"Account is not active. Current status: {found_customer_record['account_status']}"
        }
        print(f"Returning: {result}")
        return result
        
    # Check if security question exists for this customer
    if found_customer_record["customer_id"] not in security_questions:
        print("--- RESULT: NO SECURITY QUESTION CONFIGURED ---")
        result = {
            "status": "no_security_question_configured",
            "message": "No security question is configured for this account."
        }
        print(f"Returning: {result}")
        return result
        
    # Case 1: Initial call (phone_number provided, no answer)
    if answer is None:
        print("--- MODE: INITIAL LOOKUP - PROVIDE SECURITY QUESTION ---")
        security_question = security_questions[found_customer_record["customer_id"]]["question"]
        
        print("--- RESULT: SECURITY QUESTION FOUND ---")
        # Get customer name, default to "Customer" if not found
        customer_name = found_customer_record.get("full_name")
        result = {
            "status": "security_question_provided",
            "customer_name": customer_name,
            "question": security_question
        }
        print(f"Returning: {result}")
        return result

    # Case 2: Answering the question (phone_number and answer provided)
    else:
        print("--- MODE: VALIDATE ANSWER ---")
        stored_answer = security_questions[found_customer_record["customer_id"]]["answer"]
        stored_answer_cleaned = clean_string(stored_answer)
        
        if cleaned_answer == stored_answer_cleaned:
            print("--- ANSWER CORRECT - VERIFIED ---")
            # Return customer data
            result = {
                "status": "verified",
                "customer_data": found_customer_record
            }
            print(f"Returning: {result}")
            return result
        else:
            print("--- ANSWER INCORRECT - FREEZING ACCOUNT ---")
            
            # Update account status to 'freezed' in memory
            found_customer_record["account_status"] = "freezed"
            
            # Update the account status in the JSON file
            for i, customer in enumerate(customers):
                if customer["customer_id"] == found_customer_record["customer_id"]:
                    customers[i]["account_status"] = "freezed"
                    break
            
            # Write the updated data back to the JSON file
            try:
                customers_path = os.path.join(base_dir, 'assets', 'customers.json')
                with open(customers_path, 'w') as f:
                    json.dump({"customers": customers}, f, indent=4)
                print("--- ACCOUNT STATUS UPDATED TO 'freezed' IN DATABASE ---")
            except Exception as e:
                print(f"--- ERROR UPDATING ACCOUNT STATUS: {e} ---")
            
            result = {
                "status": "verification_failed", 
                "message": "The answer provided was incorrect. Your account has been frozen for security reasons."
            }
            print(f"Returning: {result}")
            return result
