"""
Validators for allergy-related requests
"""
from flask import request, jsonify
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def validate_add_allergy(f):
    """Validate add allergy request"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required'
            }), 400
        
        # Validate required fields
        if 'name_vi' not in data or not data['name_vi']:
            return jsonify({
                'success': False,
                'error': 'name_vi is required'
            }), 400
        
        # Validate name length
        if len(data['name_vi']) > 100:
            return jsonify({
                'success': False,
                'error': 'name_vi is too long (max 100 characters)'
            }), 400
        
        return f(*args, **kwargs)
    
    return decorated_function


def validate_remove_allergy(f):
    """Validate remove allergy request"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required'
            }), 400
        
        # Validate required fields
        if 'name_vi' not in data or not data['name_vi']:
            return jsonify({
                'success': False,
                'error': 'name_vi is required'
            }), 400
        
        return f(*args, **kwargs)
    
    return decorated_function
