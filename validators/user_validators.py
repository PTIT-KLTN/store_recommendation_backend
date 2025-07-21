def validate_location_data(location_data):
    if not location_data:
        return False, "No location data provided"
    
    if not isinstance(location_data, dict):
        return False, "Invalid location data format"
    
    if 'latitude' not in location_data or 'longitude' not in location_data:
        return False, "Latitude and longitude are required"
    
    try:
        latitude = float(location_data['latitude'])
        longitude = float(location_data['longitude'])
        
        if not (-90 <= latitude <= 90):
            return False, "Latitude must be between -90 and 90"
        
        if not (-180 <= longitude <= 180):
            return False, "Longitude must be between -180 and 180"
            
    except (ValueError, TypeError):
        return False, "Invalid coordinate values"
    
    return True, "Valid"