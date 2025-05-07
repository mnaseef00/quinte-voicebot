from agents import function_tool

@function_tool(
    name_override="verification_tool",
    description_override="Handles customer verification using phone number, customer ID, and a security question. "
                         "1. Initial call with 'phone_number' and 'customer_id': Returns security question if customer exists. "
                         "2. Subsequent call with 'phone_number', 'customer_id', and 'answer': Validates answer. "
                         "If correct, returns 'verified' status. "
                         "Returns 'customer_not_found', 'verification_failed', or 'no_security_question_configured' as appropriate.",
    strict_mode=True
)
def verification_tool(phone_number: str, customer_id: str | None = None, answer: str | None = None):
    print("="*50)
    print("::::[TOOL CALLED] VERIFICATION TOOL::::")
    print(f"phone_number: {phone_number}")
    if customer_id is not None: print(f"customer_id: {customer_id}")
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
        
    if not customer_id:
        print("No customer_id provided.")
        print("="*50)
        result = {
            "status": "invalid_input",
            "message": "Input 'customer_id' is required."
        }
        print(f"Returning: {result}")
        return result

    # --- Input Cleaning --- 
    def clean_string(input_str):
        if not isinstance(input_str, str):
            input_str = str(input_str) # Ensure it's a string
        cleaned = input_str.replace(' ', '').replace('-', '').replace('_', '')
        return cleaned.lower().strip()
    
    cleaned_phone_number = clean_string(phone_number)
    cleaned_customer_id = clean_string(customer_id)
    cleaned_answer = None
    if answer is not None:
        cleaned_answer = clean_string(answer)
    # ----------------------

    # Sample security questions database
    security_questions = {
        "1001": {"question": "Who is your childhood friend?", "answer": "alex"},
        "1002": {"question": "What is your favorite color?", "answer": "white"},
        "1003": {"question": "What is your favorite bird?", "answer": "parrot"},
        "1004": {"question": "What is your mother's maiden name?", "answer": "smith"}
    }

    # Sample local database (hardcoded) with simplified structure
    customers = [
        {
            "customer_id": "1001",
            "full_name": "Mohammed Naseef",
            "phone_number": "9876543210",
            "email": "mohammed.n@ampcome.com"
        },
        {
            "customer_id": "1002",
            "full_name": "ABC",
            "phone_number": "123",
            "email": "abctest@gmail.com"
        },
        {
            "customer_id": "1003",
            "full_name": "Jane Smith",
            "phone_number": "2288534567",
            "email": "janesmithtst@gmail.com"
        },
        {
            "customer_id": "1004",
            "full_name": "John Doe",
            "phone_number": "189",
            "email": "johndoe@gmail.com"
        }
    ]

    # Find the customer by phone number and customer ID
    found_customer_record = None
    for cust_data in customers:
        if (cleaned_phone_number == clean_string(cust_data.get("phone_number", "")) and
            cleaned_customer_id == clean_string(cust_data.get("customer_id", ""))):
            found_customer_record = cust_data
            break

    if not found_customer_record:
        print("--- LOOKUP RESULT (CUSTOMER NOT FOUND) ---")
        result = {
            "status": "customer_not_found",
            "message": "No customer found with the provided phone number and customer ID."
        }
        print(f"Returning: {result}")
        return result

    customer_id = found_customer_record["customer_id"]
    
    # Check if security question exists for this customer
    if customer_id not in security_questions:
        print("--- RESULT: NO SECURITY QUESTION CONFIGURED ---")
        result = {
            "status": "no_security_question_configured",
            "message": "No security question is configured for this account."
        }
        print(f"Returning: {result}")
        return result
        
    # Case 1: Initial call (phone_number and customer_id provided, no answer)
    if answer is None:
        print("--- MODE: INITIAL LOOKUP - PROVIDE SECURITY QUESTION ---")
        security_question = security_questions[customer_id]["question"]
        
        print("--- RESULT: SECURITY QUESTION FOUND ---")
        result = {
            "status": "security_question_provided",
            "question": security_question
        }
        print(f"Returning: {result}")
        return result

    # Case 2: Answering the question (phone_number, customer_id, and answer provided)
    else:
        print("--- MODE: VALIDATE ANSWER ---")
        stored_answer = security_questions[customer_id]["answer"]
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
            print("--- ANSWER INCORRECT ---")
            result = {
                "status": "verification_failed", 
                "message": "The answer provided was incorrect."
            }
            print(f"Returning: {result}")
            return result
