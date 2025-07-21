from database.mongodb import MongoDBConnection

db = MongoDBConnection.get_primary_db()

def get_dishes_data(page, size, pattern, dish_name, category, vietnamese_name):
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
    
    return {
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
    }

def get_dish_categories_data():
    categories = db.dishes.distinct('category')
    categories = [cat for cat in categories if cat and cat.strip()]
    
    return {
        'categories': sorted(categories),
        'total': len(categories)
    }

def get_dish_suggestions_data(query, limit):
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
                'dish': {'$not': regex_pattern}
            },
            {'dish': 1, 'vietnamese_name': 1, '_id': 0}
        ).limit(limit - len(suggestions))
        
        for match in vietnamese_matches:
            suggestions.append({
                'text': match.get('vietnamese_name', ''),
                'vietnamese_text': match['dish'],
                'type': 'vietnamese_name'
            })
    
    return {
        'suggestions': suggestions[:limit],
        'query': query
    }

def get_ingredients_data(page, size, pattern, name, name_en, vietnamese_name, category, unit):
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
        .sort([('name', 1), ('vietnamese_name', 1)])
        .skip(skip)
        .limit(size)
    )
    total = db.ingredients.count_documents(query)
    
    for ingredient in ingredients:
        ingredient['_id'] = str(ingredient['_id'])
        
        if 'token_ngrams' in ingredient and not isinstance(ingredient['token_ngrams'], list):
            ingredient['token_ngrams'] = []
    
    total_pages = (total + size - 1) // size if size > 0 else 0
    has_next = page < total_pages - 1
    has_prev = page > 0
    
    return {
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
    }

def get_ingredient_categories_data():
    categories = db.ingredients.distinct('category')
    categories = [cat for cat in categories if cat and cat.strip()]
    categories = sorted(set(categories))
    
    return {
        'categories': categories,
        'total': len(categories)
    }

def get_ingredient_suggestions_data(query, limit, suggestion_type):
    regex_pattern = {'$regex': f'^{query}', '$options': 'i'}
    contains_pattern = {'$regex': query, '$options': 'i'}
    
    suggestions = []
    
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
        remaining_limit = limit - len(suggestions)
        if remaining_limit > 0:
            vietnamese_matches = db.ingredients.find(
                {
                    'vietnamese_name': regex_pattern,
                    'name': {'$not': regex_pattern}
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
        remaining_limit = limit - len(suggestions)
        if remaining_limit > 0:
            category_matches = db.ingredients.find(
                {'category': contains_pattern},
                {'category': 1, '_id': 0}
            ).limit(remaining_limit)
            
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
    
    suggestions.sort(key=lambda x: (x['priority'], x['text'].lower()))
    
    return {
        'suggestions': suggestions[:limit],
        'query': query,
        'type': suggestion_type
    }