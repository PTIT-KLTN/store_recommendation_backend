def validate_pagination_params(page, size):
    """Validate pagination parameters"""
    if page < 0:
        raise ValueError("Page number must be >= 0")
    if size <= 0 or size > 1000:
        raise ValueError("Page size must be between 1 and 1000")
    return True

def validate_store_id(store_id):
    """Validate store ID parameter"""
    if not store_id or not str(store_id).strip():
        return False, "Store ID is required"
    return True, None

def validate_suggestion_params(query, limit):
    """Validate suggestion parameters"""
    if not query or len(query.strip()) < 1:
        return False, "Query must be at least 1 character"
    if limit <= 0 or limit > 50:
        return False, "Limit must be between 1 and 50"
    return True, None