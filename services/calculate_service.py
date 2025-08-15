import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import topsispy as tp

class CalculateService:
    
    def process_all_ingredients(self, basket_ingredients, basket_dishes):
        processed_ingredients = {}   
        
        # Process basket ingredients
        for ingredient in basket_ingredients:
            if isinstance(ingredient, dict) and ingredient.get('name'):
                name = ingredient['name'].strip()
                quantity = ingredient.get('quantity', 1)
                if not isinstance(quantity, (int, float)) or quantity <= 0:
                    quantity = 1
                
                # Loại bỏ net_unit_value khỏi ingredient vì không cần thiết
                processed_ingredients[name] = {
                    'name': name,
                    'category': ingredient.get('category', ''),
                    'vietnamese_name': ingredient.get('vietnamese_name', ''),
                    'unit': ingredient.get('unit', ''),
                    'total_quantity': quantity  # Chỉ cần quantity thôi
                }
        
        # Process dish ingredients
        for dish in basket_dishes:
            if isinstance(dish, dict):
                dish_servings = dish.get('servings', 1)
                    
                for dish_ingredient in dish.get('ingredients', []):
                    if isinstance(dish_ingredient, dict) and dish_ingredient.get('name'):
                        name = dish_ingredient['name'].strip()
                        ingredient_quantity = dish_ingredient.get('quantity', 1)
                        ingredient_unit = dish_ingredient.get('unit', '')
                        
                        # Tính total quantity dựa trên servings
                        total_dish_quantity = ingredient_quantity * dish_servings
                        
                        if name in processed_ingredients:
                            # Cộng dồn quantity nếu nguyên liệu đã tồn tại
                            processed_ingredients[name]['total_quantity'] += total_dish_quantity
                        else:
                            # Tạo mới nếu chưa tồn tại, loại bỏ net_unit_value
                            processed_ingredients[name] = {
                                'name': name,
                                'category': dish_ingredient.get('category', ''),
                                'vietnamese_name': dish_ingredient.get('vietnamese_name', ''),
                                'unit': ingredient_unit,
                                'total_quantity': total_dish_quantity
                            }
        
        return processed_ingredients

    def generate_ngrams_from_text(self, text, n=3):
        """Generate n-grams from text for comparison"""
        if not text:
            return set()
        
        text = text.lower().strip()
        ngrams = set()
        
        # Character n-grams
        for i in range(len(text) - n + 1):
            ngrams.add(text[i:i+n])
        
        # Word tokens
        words = text.split()
        for word in words:
            if len(word) >= 2:
                ngrams.add(word)
        
        return ngrams

    def calculate_fuzzy_match_score(self, ingredient_name, product_name, product_token_ngrams=None):
        """Enhanced fuzzy matching using token_ngrams for better accuracy"""
        if not ingredient_name or not product_name:
            return 0.0
        
        ingredient_name = ingredient_name.lower().strip()
        product_name = product_name.lower().strip()
        
        if ingredient_name == product_name:
            return 1.0
        
        if ingredient_name in product_name or product_name in ingredient_name:
            return 0.9
        
        if product_token_ngrams and isinstance(product_token_ngrams, list):
            # Generate ngrams for ingredient
            ingredient_ngrams = self.generate_ngrams_from_text(ingredient_name)
            product_ngrams = set(product_token_ngrams)
            
            if ingredient_ngrams and product_ngrams:
                # Calculate Jaccard similarity using ngrams
                intersection = len(ingredient_ngrams.intersection(product_ngrams))
                union = len(ingredient_ngrams.union(product_ngrams))
                ngram_similarity = intersection / union if union > 0 else 0.0
                
                # Boost score for good ngram matches
                if ngram_similarity >= 0.3:
                    return min(ngram_similarity + 0.2, 1.0)
                elif ngram_similarity >= 0.1:
                    return min(ngram_similarity + 0.1, 1.0)
        
        ingredient_words = set(ingredient_name.split())
        product_words = set(product_name.split())
        
        if ingredient_words and product_words:
            overlap = len(ingredient_words.intersection(product_words))
            total = len(ingredient_words.union(product_words))
            jaccard = overlap / total if total > 0 else 0.0
            
            if overlap > 0:
                return min(jaccard + 0.1, 1.0)
            return jaccard
        
        return 0.0


    def find_matched_products(self, metadata_db, candidate_stores, processed_ingredients):
        
        # Category to collection mapping
        CATEGORY_TO_COLLECTION = {
            'Alcoholic Beverages': 'alcoholic_beverages',
            'Beverages': 'beverages',
            'Cakes': 'cakes',
            'Candies': 'candies',
            'Cereals & Grains': 'cereals_&_grains',
            'Cold Cuts: Sausages & Ham': 'cold_cuts_sausages_&_ham',
            'Dried Fruits': 'dried_fruits',
            'Fresh Fruits': 'fresh_fruits',
            'Fresh Meat': 'fresh_meat',
            'Fruit Jam': 'fruit_jam',
            'Grains & Staples': 'grains_&_staples',
            'Ice Cream & Cheese': 'ice_cream_&_cheese',
            'Instant Foods': 'instant_foods',
            'Milk' : 'milk',
            'Seafood & Fish Balls': 'seafood_&_fish_balls',
            'Seasonings': 'seasonings',
            'Snacks': 'snacks',
            'Vegetables': 'vegetables',
            'Yogurt': 'yogurt'
        }
        
        def process_store(store):
            # """Process single store with optimized ingredient lookup and net_unit_value calculation"""
            store_id = store.get('store_id')
            store_name = store.get('store_name')
            store_distance = store.get('distance_km', 0)
            store_chain = store.get('chain')
            store_address = store.get('store_location')
            store_phone = store.get('phone', '')
            store_rating = store.get('totalScore', 0)
            store_reviews = store.get('reviewsCount', 0)
            
            if not store_id:
                return None
            
            ingredient_products = {}
            total_products_found = 0
            
            # Process each ingredient with its pre-computed info
            for ingredient_name, ingredient_info in processed_ingredients.items():
                ingredient_category = ingredient_info.get('category', '')
                collection_name = CATEGORY_TO_COLLECTION.get(ingredient_category)
                category_products = []
                for store_id_format in [store_id, str(store_id), int(store_id)]:
                    try:
                        category_products = list(metadata_db[collection_name].find({'store_id': store_id_format}))
                        if category_products:
                            break
                    except:
                        continue
                
                total_products_found += len(category_products)
                
                # Find best matches with enhanced scoring using token_ngrams
                ingredient_matches = []
                for product in category_products:                
                    # Check product names for matches
                    product_names = [product.get(field, '') for field in ['name_en'] if product.get(field)]
                    
                    best_score = 0.0
                    best_field = None
                    
                    for product_name in product_names:
                        product_ngrams = product.get('token_ngrams', [])
                        score = self.calculate_fuzzy_match_score(ingredient_name, product_name, product_ngrams)
                        if score > best_score:
                            best_score = score
                            best_field = product_name
                    
                    if best_score >= 0.2:  # Threshold
                        ingredient_matches.append({
                            'product': product,
                            'score': best_score,
                            'matched_field': best_field,
                            'ingredient_info': ingredient_info
                        })
                
                # Sort by score then price
                if ingredient_matches:
                    ingredient_matches.sort(key=lambda x: (-x['score'], x['product'].get('price', x['product'].get('price_per_unit', float('inf')))))
                    ingredient_products[ingredient_name] = ingredient_matches
                else:
                    ingredient_products[ingredient_name] = []
            
            if total_products_found == 0:
                return None
            
            total_cost = 0
            found_ingredients = 0
            missing_ingredients = []
            store_items = []
            
            for ingredient_name, ingredient_info in processed_ingredients.items():
                matches = ingredient_products.get(ingredient_name, [])
                
                ingredient_quantity_needed = ingredient_info['total_quantity']
                ingredient_unit = ingredient_info.get('unit', '')
                
                if matches:
                    best_match = matches[0]
                    best_product = best_match['product']
                    
                    # Get price and net_unit_value
                    price_per_unit = best_product.get('price')
                    
                    net_unit_value = best_product.get('net_unit_value', 1)
                    product_unit = best_product.get('unit', '')
                    actual_quantity_needed = ingredient_quantity_needed / net_unit_value
                    
                    units_to_buy = max(1, round(actual_quantity_needed, 3))
                    
                    # Calculate total cost
                    item_cost = price_per_unit * units_to_buy
                    total_cost += item_cost
                    found_ingredients += 1
                    
                    # Get top 5 alternative products with net_unit_value calculation
                    alternatives = []
                    for i, match in enumerate(matches[1:6]):  
                        alt_product = match['product']
                        alt_price = alt_product.get('price')
                        
                        alt_net_unit_value = alt_product.get('net_unit_value', 1)
                        alt_product_unit = alt_product.get('unit', '')
                        alt_units_to_buy = max(1, round(ingredient_quantity_needed / alt_net_unit_value if alt_net_unit_value > 0 else 1, 3))
                        
                        alternatives.append({
                            'product_name': alt_product.get('name', ''),
                            'product_name_en': alt_product.get('name_en', ''),
                            'product_image': alt_product.get('image', ''),
                            'product_sku': alt_product.get('sku', ''),
                            'product_category': alt_product.get('category', ''),
                            'product_unit': alt_product_unit,
                            'product_net_unit_value': alt_net_unit_value,
                            'price_per_unit': alt_price,
                            'original_price': alt_product.get('sys_price', alt_price),
                            'discount_percent': alt_product.get('discountPercent', 0),
                            'quantity_needed': round(alt_units_to_buy, 3),
                            'total_price': round(alt_price * alt_units_to_buy, 2),
                            'match_score': match['score'],
                            'matched_field': match['matched_field'],
                            'product_url': alt_product.get('url', ''),
                            'promotion': alt_product.get('promotion', ''),
                            'rank': i + 2  # Rank starting from 2 (since best is rank 1)
                        })
                    
                    # Enhanced product information with net_unit_value
                    store_items.append({
                        'ingredient_name': ingredient_name,
                        'ingredient_vietnamese_name': ingredient_info.get('vietnamese_name', ''),
                        'ingredient_category': ingredient_info.get('category', ''),
                        'ingredient_unit': ingredient_unit,
                        'product_name': best_product.get('name', ''),
                        'product_name_en': best_product.get('name_en', ''),
                        'product_image': best_product.get('image', ''),
                        'product_sku': best_product.get('sku', ''),
                        'product_category': best_product.get('category', ''),
                        'product_unit': product_unit,
                        'product_net_unit_value': net_unit_value,
                        'price_per_unit': price_per_unit,
                        'original_price': best_product.get('sys_price', price_per_unit),
                        'discount_percent': best_product.get('discountPercent', 0),
                        'quantity_needed': round(units_to_buy, 3),
                        'total_price': round(item_cost, 2),
                        'available': True,
                        'match_score': best_match['score'],
                        'matched_field': best_match['matched_field'],
                        'product_url': best_product.get('url', ''),
                        'promotion': best_product.get('promotion', ''),
                        'alternatives_count': len(matches) - 1,
                        'alternatives': alternatives,  # Top 5 alternative products
                        'rank': 1  # Best match rank
                    })
                else:
                    missing_ingredients.append(ingredient_name)
                    
                    store_items.append({
                        'ingredient_name': ingredient_name,
                        'ingredient_vietnamese_name': ingredient_info.get('vietnamese_name', ''),
                        'ingredient_category': ingredient_info.get('category', ''),
                        'ingredient_unit': ingredient_unit,
                        'product_id': None,
                        'product_name': None,
                        'product_name_en': None,
                        'product_vietnamese_name': None,
                        'product_image': None,
                        'product_sku': None,
                        'product_category': None,
                        'product_unit': None,
                        'product_net_unit_value': None,
                        'price_per_unit': 0,
                        'original_price': 0,
                        'discount_percent': 0,
                        'quantity_needed': ingredient_quantity_needed,
                        'total_price': 0,
                        'available': False,
                        'match_score': 0.0,
                        'matched_field': None,
                        'product_url': None,
                        'promotion': None,
                        'alternatives_count': 0
                    })
            
            availability_percentage = (found_ingredients / len(processed_ingredients) * 100) if processed_ingredients else 0
            
            return {
                'store_id': str(store_id),
                'store_name': store_name,
                'store_chain': store_chain,
                'store_address': store_address,
                'store_phone': store_phone,
                'store_rating': store_rating,
                'store_reviews_count': store_reviews,
                'distance_km': round(store_distance, 2),
                'total_cost': round(total_cost, 2),
                'availability_percentage': round(availability_percentage, 2),
                'found_ingredients': found_ingredients,
                'total_ingredients': len(processed_ingredients),
                'missing_ingredients': missing_ingredients,
                'items': store_items,
                'overall_score': 0,
                'products_analyzed': total_products_found,
                'average_match_score': round(sum(item['match_score'] for item in store_items if item['available']) / max(found_ingredients, 1), 2)
            }
        
        # Process stores in parallel
        store_calculations = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_store = {executor.submit(process_store, store): store for store in candidate_stores}
            
            for future in as_completed(future_to_store):
                try:
                    result = future.result()
                    if result:
                        store_calculations.append(result)
                except Exception:
                    continue  
        
        return store_calculations


    def calculate_store_scores(self, store_calculations, user_email, db_primary):
        """Scoring using TOPSIS method with familiarity consideration"""
        if not store_calculations:
            return store_calculations
        
        # Get user's favourite stores
        user_data = db_primary.users.find_one({'email': user_email})
        favourite_stores = set()
        if user_data and user_data.get('favourite_stores'):
            favourite_stores = set(str(store_id) for store_id in user_data['favourite_stores'])
        
        # Calculate familiarity score for each store
        for calc in store_calculations:
            store_id = str(calc.get('store_id', ''))
            calc['familiarity_score'] = 100 if store_id in favourite_stores else 0
        
        decision_matrix = []
        valid_stores = []
        
        for calc in store_calculations:
            total_cost = max(float(calc.get('total_cost', 1)), 1.0)
            distance_km = max(float(calc.get('distance_km', 0.1)), 0.1)
            store_rating = max(float(calc.get('store_rating', 0.1)), 0.1)
            availability_percentage = max(float(calc.get('availability_percentage', 0.1)), 0.1)
            familiarity_score = float(calc.get('familiarity_score', 0))
            
            # Skip invalid stores
            if total_cost <= 0 or distance_km <= 0:
                continue
                
            row = [total_cost, distance_km, store_rating, availability_percentage, familiarity_score]
            decision_matrix.append(row)
            valid_stores.append(calc)
        
        # TOPSIS calculation
        weights = [0.0872, 0.1499, 0.0487, 0.4572, 0.2596]  # Price, Distance, Rating, Available, Familiar
        signs = [-1, -1, 1, 1, 1]  # Lower is better for price/distance, higher is better for others
        
        # Handle identical columns by adding small variation
        matrix = np.array(decision_matrix, dtype=float)
        for j in range(matrix.shape[1]):
            if np.all(matrix[:, j] == matrix[0, j]):
                matrix[:, j] = matrix[:, j] + np.random.normal(0, 0.001, matrix.shape[0])
        
        topsis_result = tp.topsis(matrix.tolist(), weights, signs)
        
        if isinstance(topsis_result, tuple) and len(topsis_result) == 2:
            best_index, scores = topsis_result
            if hasattr(scores, 'tolist'):
                scores_list = scores.tolist()
            elif isinstance(scores, (list, tuple)):
                scores_list = list(scores)
            else:
                scores_list = [float(scores)] * len(valid_stores)
        else:
            scores_list = [0.5] * len(valid_stores)
        
        if len(scores_list) != len(valid_stores):
            if len(scores_list) < len(valid_stores):
                scores_list.extend([0.0] * (len(valid_stores) - len(scores_list)))
            else:
                scores_list = scores_list[:len(valid_stores)]
        
        for i, calc in enumerate(valid_stores):
            score = max(0.0, min(1.0, float(scores_list[i])))
            calc['overall_score'] = round(score * 100, 2)
            
            calc['score_breakdown'] = {
                'price_weight': weights[0],
                'distance_weight': weights[1], 
                'rating_weight': weights[2],
                'availability_weight': weights[3],
                'familiarity_weight': weights[4],
                'topsis_score': round(score, 4)
            }
            
            calc['raw_values'] = {
                'total_cost': calc.get('total_cost', 0),
                'distance_km': calc.get('distance_km', 0),
                'store_rating': calc.get('store_rating', 0), 
                'availability_percentage': calc.get('availability_percentage', 0),
                'familiarity_score': calc.get('familiarity_score', 0)
            }
        
        for calc in store_calculations:
            if 'overall_score' not in calc:
                calc['overall_score'] = 0.0
                calc['score_breakdown'] = {
                    'price_weight': 0,
                    'distance_weight': 0, 
                    'rating_weight': 0,
                    'availability_weight': 0,
                    'familiarity_weight': 0,
                    'topsis_score': 0.0,
                    'error': 'Invalid data'
                }
                calc['raw_values'] = {
                    'total_cost': calc.get('total_cost', 0),
                    'distance_km': calc.get('distance_km', 0),
                    'store_rating': calc.get('store_rating', 0), 
                    'availability_percentage': calc.get('availability_percentage', 0),
                    'familiarity_score': calc.get('familiarity_score', 0)
                }
        
        return store_calculations