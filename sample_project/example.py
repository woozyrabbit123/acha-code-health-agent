"""Example module with code issues for ACHA to detect"""

# Duplicated constant - will be referenced many times
API_KEY = "secret-key-12345"

def get_api_key():
    """Get API key"""
    return API_KEY

def validate_key(key):
    """Validate key"""
    if key == API_KEY:
        return True
    return False

def check_access():
    """Check access"""
    key = get_api_key()
    if key == API_KEY:
        print(f"Access granted with {API_KEY}")
        return True
    return False

def log_key():
    """Log key"""
    print(f"Current API key: {API_KEY}")

# Risky construct - eval usage
def calculate(expression):
    """Dangerous calculation using eval"""
    result = eval(expression)
    return result
