from flask import Blueprint, request, jsonify
from database.mongodb import MongoDBConnection
from bson import ObjectId

db = MongoDBConnection.get_primary_db()


public_bp = Blueprint('public', __name__)

# Dishes endpoint
@public_bp.route('/dishes', methods=['GET'])
def get_dishes():
    try:
        page = int(request.args.get('pageNo', 0))
        size = int(request.args.get('pageSize', 30))
        
        pattern = request.args.get('pattern', '').strip()
        dish_name = request.args.get('dish', '').strip()
        category = request.args.get('category', '').strip()
        vietnamese_name = request.args.get('vietnamese_name', '').strip()
        
        skip = page * size
        
        query_conditions = []
        
        if pattern:
            pattern_regex = {'$regex': pattern, '$options': 'i'}
            query_conditions.append({
                '$or': [
                    {'dish': pattern_regex},
                    {'vietnamese_name': pattern_regex}
                ]
            })
        
        if dish_name:
            query_conditions.append({
                'dish': {'$regex': dish_name, '$options': 'i'}
            })
        
        if vietnamese_name:
            query_conditions.append({
                'vietnamese_name': {'$regex': vietnamese_name, '$options': 'i'}
            })
        
        if category:
            query_conditions.append({
                'category': {'$regex': f'^{category}$', '$options': 'i'}
            })
        
        if query_conditions:
            if len(query_conditions) == 1:
                query = query_conditions[0]
            else:
                query = {'$and': query_conditions}
        else:
            query = {}
        
        dishes = list(db.dishes.find(query).skip(skip).limit(size))
        total = db.dishes.count_documents(query)
        
        for dish in dishes:
            dish['_id'] = str(dish['_id'])
            
            if 'ingredients' in dish and isinstance(dish['ingredients'], list):
                for ingredient in dish['ingredients']:
                    if '_id' in ingredient and hasattr(ingredient['_id'], 'inserted_id'):
                        ingredient['_id'] = str(ingredient['_id'])
        
        total_pages = (total + size - 1) // size if size > 0 else 0
        has_next = page < total_pages - 1
        has_prev = page > 0
        
        return jsonify({
            'dishes': dishes,
            'numDishes': total,
            'pagination': {
                'currentPage': page,
                'pageSize': size,
                'totalPages': total_pages,
                'totalElements': total,
                'hasNext': has_next,
                'hasPrevious': has_prev
            },
            'filters': {
                'pattern': pattern,
                'dish': dish_name,
                'vietnamese_name': vietnamese_name,
                'category': category
            }
        }), 200
        
    except ValueError as ve:
        return jsonify({
            'message': f'Invalid parameter value: {str(ve)}',
            'error': 'INVALID_PARAMETER'
        }), 400
    except Exception as e:
        return jsonify({
            'message': f'Error retrieving dishes: {str(e)}',
            'error': 'INTERNAL_ERROR'
        }), 500


@public_bp.route('/dishes/categories', methods=['GET'])
def get_dish_categories():
    try:
        
        categories = db.dishes.distinct('category')
        
        categories = [cat for cat in categories if cat and cat.strip()]
        
        return jsonify({
            'categories': sorted(categories),
            'total': len(categories)
        }), 200
        
    except Exception as e:
        return jsonify({
            'message': f'Error retrieving categories: {str(e)}',
            'error': 'INTERNAL_ERROR'
        }), 500


@public_bp.route('/dishes/suggestions', methods=['GET'])
def get_dish_suggestions():
    try:
        query = request.args.get('q', '').strip()
        limit = int(request.args.get('limit', 10))
        
        if not query or len(query) < 2:
            return jsonify({'suggestions': []}), 200
                
        regex_pattern = {'$regex': f'^{query}', '$options': 'i'}
        
        suggestions = []
        
        dish_matches = db.dishes.find(
            {'dish': regex_pattern},
            {'dish': 1, 'vietnamese_name': 1, '_id': 0}
        ).limit(limit)
        
        for match in dish_matches:
            suggestions.append({
                'text': match['dish'],
                'vietnamese_text': match.get('vietnamese_name', ''),
                'type': 'dish_name'
            })
        
        if len(suggestions) < limit:
            vietnamese_matches = db.dishes.find(
                {
                    'vietnamese_name': regex_pattern,
                    'dish': {'$not': regex_pattern}  # Exclude already found items
                },
                {'dish': 1, 'vietnamese_name': 1, '_id': 0}
            ).limit(limit - len(suggestions))
            
            for match in vietnamese_matches:
                suggestions.append({
                    'text': match.get('vietnamese_name', ''),
                    'vietnamese_text': match['dish'],
                    'type': 'vietnamese_name'
                })
        
        return jsonify({
            'suggestions': suggestions[:limit],
            'query': query
        }), 200
        
    except ValueError as ve:
        return jsonify({
            'message': f'Invalid parameter: {str(ve)}',
            'error': 'INVALID_PARAMETER'
        }), 400
    except Exception as e:
        return jsonify({
            'message': f'Error getting suggestions: {str(e)}',
            'error': 'INTERNAL_ERROR'
        }), 500


# Ingredients endpoint
@public_bp.route('/ingredients', methods=['GET'])
def get_ingredients():
    try:
        page = int(request.args.get('pageNo', 0))
        size = int(request.args.get('pageSize', 30))
        
        pattern = request.args.get('pattern', '').strip()
        name = request.args.get('name', '').strip()
        name_en = request.args.get('name_en', '').strip()
        vietnamese_name = request.args.get('vietnamese_name', '').strip()
        category = request.args.get('category', '').strip()
        unit = request.args.get('unit', '').strip()
        
        skip = page * size
        
        query_conditions = []
        
        if pattern:
            pattern_regex = {'$regex': pattern, '$options': 'i'}
            query_conditions.append({
                '$or': [
                    {'name': pattern_regex},
                    {'name_en': pattern_regex},
                    {'vietnamese_name': pattern_regex}
                ]
            })
        
        if name:
            query_conditions.append({
                'name': {'$regex': name, '$options': 'i'}
            })
        
        if name_en:
            query_conditions.append({
                'name_en': {'$regex': name_en, '$options': 'i'}
            })
        
        if vietnamese_name:
            query_conditions.append({
                'vietnamese_name': {'$regex': vietnamese_name, '$options': 'i'}
            })
        
        if category:
            query_conditions.append({
                'category': {'$regex': f'^{category}$', '$options': 'i'}
            })
        
        if unit:
            query_conditions.append({
                'unit': {'$regex': f'^{unit}$', '$options': 'i'}
            })
        
        if query_conditions:
            if len(query_conditions) == 1:
                query = query_conditions[0]
            else:
                query = {'$and': query_conditions}
        else:
            query = {}
        
        ingredients = list(
            db.ingredients.find(query)
            .sort([('name', 1), ('vietnamese_name', 1)])  # Sort by name then vietnamese_name
            .skip(skip)
            .limit(size)
        )
        total = db.ingredients.count_documents(query)
        
        for ingredient in ingredients:
            ingredient['_id'] = str(ingredient['_id'])
            
            if 'token_ngrams' in ingredient and not isinstance(ingredient['token_ngrams'], list):
                ingredient['token_ngrams'] = []
        
        # Calculate pagination info
        total_pages = (total + size - 1) // size if size > 0 else 0
        has_next = page < total_pages - 1
        has_prev = page > 0
        
        return jsonify({
            'ingredients': ingredients,
            'numIngredients': total,
            'pagination': {
                'currentPage': page,
                'pageSize': size,
                'totalPages': total_pages,
                'totalElements': total,
                'hasNext': has_next,
                'hasPrevious': has_prev
            },
            'filters': {
                'pattern': pattern,
                'name': name,
                'name_en': name_en,
                'vietnamese_name': vietnamese_name,
                'category': category,
                'unit': unit
            }
        }), 200
        
    except ValueError as ve:
        return jsonify({
            'message': f'Invalid parameter value: {str(ve)}',
            'error': 'INVALID_PARAMETER'
        }), 400
    except Exception as e:
        return jsonify({
            'message': f'Error retrieving ingredients: {str(e)}',
            'error': 'INTERNAL_ERROR'
        }), 500


@public_bp.route('/ingredients/categories', methods=['GET'])
def get_ingredient_categories():
    try:        
        categories = db.ingredients.distinct('category')
        
        categories = [cat for cat in categories if cat and cat.strip()]
        categories = sorted(set(categories))  # Remove duplicates and sort
        
        return jsonify({
            'categories': categories,
            'total': len(categories)
        }), 200
        
    except Exception as e:
        return jsonify({
            'message': f'Error retrieving categories: {str(e)}',
            'error': 'INTERNAL_ERROR'
        }), 500


@public_bp.route('/ingredients/suggestions', methods=['GET'])
def get_ingredient_suggestions():
    try:
        query = request.args.get('q', '').strip()
        limit = int(request.args.get('limit', 10))
        suggestion_type = request.args.get('type', 'all')  # all, name, vietnamese, category
        
        if not query or len(query) < 2:
            return jsonify({'suggestions': []}), 200
                
        regex_pattern = {'$regex': f'^{query}', '$options': 'i'}
        contains_pattern = {'$regex': query, '$options': 'i'}
        
        suggestions = []
        
        db = MongoDBConnection.get_primary_db()
        # Search based on type
        if suggestion_type in ['all', 'name']:
            name_matches = db.ingredients.find(
                {'name': regex_pattern},
                {'name': 1, 'vietnamese_name': 1, 'category': 1, '_id': 0}
            ).limit(limit // 2)
            
            for match in name_matches:
                suggestions.append({
                    'text': match['name'],
                    'vietnamese_text': match.get('vietnamese_name', ''),
                    'category': match.get('category', ''),
                    'type': 'name',
                    'priority': 1
                })
        
        if suggestion_type in ['all', 'vietnamese']:
            # Search in vietnamese names
            remaining_limit = limit - len(suggestions)
            if remaining_limit > 0:
                vietnamese_matches = db.ingredients.find(
                    {
                        'vietnamese_name': regex_pattern,
                        'name': {'$not': regex_pattern}  # Exclude already found items
                    },
                    {'name': 1, 'vietnamese_name': 1, 'category': 1, '_id': 0}
                ).limit(remaining_limit)
                
                for match in vietnamese_matches:
                    suggestions.append({
                        'text': match.get('vietnamese_name', ''),
                        'vietnamese_text': match['name'],
                        'category': match.get('category', ''),
                        'type': 'vietnamese_name',
                        'priority': 2
                    })
        
        if suggestion_type in ['all', 'category']:
            # Search in categories
            remaining_limit = limit - len(suggestions)
            if remaining_limit > 0:
                category_matches = db.ingredients.find(
                    {'category': contains_pattern},
                    {'category': 1, '_id': 0}
                ).limit(remaining_limit)
                
                # Get unique categories
                categories = list(set([match['category'] for match in category_matches if match.get('category')]))
                
                for category in categories[:remaining_limit]:
                    if category.lower().startswith(query.lower()):
                        suggestions.append({
                            'text': category,
                            'vietnamese_text': '',
                            'category': category,
                            'type': 'category',
                            'priority': 3
                        })
        
        # Sort suggestions by priority and then alphabetically
        suggestions.sort(key=lambda x: (x['priority'], x['text'].lower()))
        
        return jsonify({
            'suggestions': suggestions[:limit],
            'query': query,
            'type': suggestion_type
        }), 200
        
    except ValueError as ve:
        return jsonify({
            'message': f'Invalid parameter: {str(ve)}',
            'error': 'INVALID_PARAMETER'
        }), 400
    except Exception as e:
        return jsonify({
            'message': f'Error getting suggestions: {str(e)}',
            'error': 'INTERNAL_ERROR'
        }), 500


    try:
        data = request.get_json()
        
        # Pagination
        page = data.get('pageNo', 0)
        size = data.get('pageSize', 30)
        
        # Search criteria
        search_criteria = data.get('criteria', {})
        
        # Sort options
        sort_by = data.get('sortBy', 'name')  # name, vietnamese_name, category
        sort_order = data.get('sortOrder', 'asc')  # asc, desc
        
        db = MongoDBConnection.get_primary_db()
        skip = page * size
        
        # Build query from criteria
        query = {}
        for field, value in search_criteria.items():
            if value and value.strip():
                if field in ['name', 'name_en', 'vietnamese_name', 'category']:
                    query[field] = {'$regex': value, '$options': 'i'}
                elif field == 'unit':
                    query[field] = {'$regex': f'^{value}$', '$options': 'i'}
        
        # Build sort criteria
        sort_direction = 1 if sort_order == 'asc' else -1
        sort_criteria = [(sort_by, sort_direction)]
        
        # Execute query
        ingredients = list(
            db.ingredients.find(query)
            .sort(sort_criteria)
            .skip(skip)
            .limit(size)
        )
        total = db.ingredients.count_documents(query)
        
        # Convert ObjectId to string
        for ingredient in ingredients:
            ingredient['_id'] = str(ingredient['_id'])
        
        # Calculate pagination
        total_pages = (total + size - 1) // size if size > 0 else 0
        
        return jsonify({
            'ingredients': ingredients,
            'numIngredients': total,
            'pagination': {
                'currentPage': page,
                'pageSize': size,
                'totalPages': total_pages,
                'totalElements': total,
                'hasNext': page < total_pages - 1,
                'hasPrevious': page > 0
            },
            'searchCriteria': search_criteria,
            'sortBy': sort_by,
            'sortOrder': sort_order
        }), 200
        
    except Exception as e:
        return jsonify({
            'message': f'Error in advanced search: {str(e)}',
            'error': 'INTERNAL_ERROR'
        }), 500