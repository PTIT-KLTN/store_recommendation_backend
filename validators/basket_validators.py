def validate_basket_data(basket_data):
    if not basket_data:
        return False, "No basket data provided"
    
    if not isinstance(basket_data, dict):
        return False, "Invalid basket data format"
    
    return True, "Valid"

def validate_basket_index(basket_index):
    if not isinstance(basket_index, int):
        return False, "Basket index must be an integer"
    
    if basket_index < 0:
        return False, "Basket index cannot be negative"
    
    return True, "Valid"

def validate_favorite_basket_data(basket_data):
    is_valid, message = validate_basket_data(basket_data)
    if not is_valid:
        return False, message
    
    if not basket_data.get('basket_name'):
        return False, "Basket name is required"
    
    return True, "Valid"