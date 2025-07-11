from flask import Blueprint, request, jsonify
from database.mongodb import MongoDBConnection
from bson import ObjectId

public_bp = Blueprint('public', __name__)

@public_bp.route('/ingredients', methods=['GET'])
def get_ingredients():
    try:
        page = int(request.args.get('pageNo', 0))
        size = int(request.args.get('pageSize', 30))
        pattern = request.args.get('pattern', '')
        
        db = MongoDBConnection.get_primary_db()
        skip = page * size
        
        if pattern:
            query = {'vietnamese_name': {'$regex': pattern, '$options': 'i'}}
        else:
            query = {}
        
        ingredients = list(db.ingredients.find(query).skip(skip).limit(size))
        total = db.ingredients.count_documents(query)
        
        # Convert ObjectId to string
        for ingredient in ingredients:
            ingredient['_id'] = str(ingredient['_id'])
        
        return jsonify({
            'ingredients': ingredients,
            'numIngredients': total
        }), 200
        
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@public_bp.route('/dishes', methods=['GET'])
def get_dishes():
    try:
        page = int(request.args.get('pageNo', 0))
        size = int(request.args.get('pageSize', 30))
        pattern = request.args.get('pattern', '')
        
        db = MongoDBConnection.get_primary_db()
        skip = page * size
        
        if pattern:
            query = {'vietnamese_name': {'$regex': pattern, '$options': 'i'}}
        else:
            query = {}
        
        dishes = list(db.dishes.find(query).skip(skip).limit(size))
        total = db.dishes.count_documents(query)
        
        # Convert ObjectId to string
        for dish in dishes:
            dish['_id'] = str(dish['_id'])
        
        return jsonify({
            'dishes': dishes,
            'numDishes': total
        }), 200
        
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@public_bp.route('/ingredients/totalSize', methods=['GET'])
def get_total_ingredients():
    try:
        db = MongoDBConnection.get_primary_db()
        total = db.ingredients.count_documents({})
        return jsonify(total), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@public_bp.route('/dishes/totalSize', methods=['GET'])
def get_total_dishes():
    try:
        db = MongoDBConnection.get_primary_db()
        total = db.dishes.count_documents({})
        return jsonify(total), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500