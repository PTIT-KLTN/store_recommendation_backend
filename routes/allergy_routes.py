from flask import Blueprint, request, jsonify
from utils.token_utils import token_required
from services.allergy_service import get_allergy_service
from validators.allergy_validators import validate_add_allergy, validate_remove_allergy
import logging

logger = logging.getLogger(__name__)

allergy_bp = Blueprint('allergy', __name__)


@allergy_bp.route('/allergies', methods=['GET'])
@token_required
def get_allergies(current_user):
    try:
        allergy_service = get_allergy_service()
        allergies = allergy_service.get_user_allergies(current_user['email'])
        
        return jsonify({
            'success': True,
            'allergies': allergies,
            'total': len(allergies)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting allergies: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@allergy_bp.route('/allergies', methods=['POST'])
@token_required
@validate_add_allergy
def add_allergy(current_user):
    try:
        data = request.get_json()
        allergy_service = get_allergy_service()
        
        result = allergy_service.add_allergy(current_user['email'], data)
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error adding allergy: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@allergy_bp.route('/allergies', methods=['DELETE'])
@token_required
@validate_remove_allergy
def remove_allergy(current_user):
    try:
        data = request.get_json()
        allergy_service = get_allergy_service()
        
        result = allergy_service.remove_allergy(
            current_user['email'],
            data['name_vi']
        )
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error removing allergy: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@allergy_bp.route('/allergies/clear', methods=['POST'])
@token_required
def clear_allergies(current_user):
    try:
        allergy_service = get_allergy_service()
        result = allergy_service.clear_all_allergies(current_user['email'])
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error clearing allergies: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
