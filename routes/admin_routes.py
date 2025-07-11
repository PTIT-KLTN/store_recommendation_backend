from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database.mongodb import MongoDBConnection

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/ingredient/add', methods=['POST'])
@jwt_required()
def add_ingredient():
    try:
        ingredient_data = request.get_json()
        db = MongoDBConnection.get_primary_db()
        
        # TODO: Add role-based access control
        
        result = db.ingredients.insert_one(ingredient_data)
        ingredient_data['_id'] = str(result.inserted_id)
        
        return jsonify(ingredient_data), 200
        
    except Exception as e:
        return jsonify({'message': str(e)}), 500