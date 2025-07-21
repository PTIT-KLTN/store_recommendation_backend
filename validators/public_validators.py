def validate_pagination_params(page, size):
    if page < 0:
        raise ValueError("Page number cannot be negative")
    if size <= 0:
        raise ValueError("Page size must be greater than 0")
    if size > 100:
        raise ValueError("Page size cannot exceed 100")
    return True

def validate_suggestion_params(query, limit):
    if len(query) < 2:
        return False, "Query must be at least 2 characters"
    if limit < 1 or limit > 50:
        raise ValueError("Limit must be between 1 and 50")
    return True, "Valid"

def validate_suggestion_type(suggestion_type):
    valid_types = ['all', 'name', 'vietnamese', 'category']
    if suggestion_type not in valid_types:
        raise ValueError(f"Invalid suggestion type. Must be one of: {', '.join(valid_types)}")
    return True