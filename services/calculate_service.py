from services.embedding_service import EmbeddingService
import numpy as np
import topsispy as tp
import re
from difflib import SequenceMatcher

class CalculateService:
    def __init__(self):
        # Initialize embedding service
        self.embedding_service = EmbeddingService(
            model_name='keepitreal/vietnamese-sbert',
            index_dir='scripts/faiss_indexes'
        )

        # Load all indexes on startup
        self._load_all_indexes()

        # MongoDB database reference (will be set when needed)
        self.metadata_db = None
    
    def _load_all_indexes(self):
        """Load all FAISS indexes on service initialization"""
        collections = [
            'alcoholic_beverages', 'beverages', 'cakes', 'candies',
            'cereals_&_grains', 'cold_cuts:_sausages_&_ham', 'dried_fruits',
            'fresh_fruits', 'fresh_meat', 'fruit_jam', 'grains_&_staples',
            'ice_cream_&_cheese', 'instant_foods', 'milk', 'seafood_&_fish_balls',
            'seasonings', 'snacks', 'vegetables', 'yogurt'
        ]

        self.embedding_service.load_all_indexes(collections)

    def _calculate_string_similarity(self, str1, str2):
        """Calculate similarity ratio between two strings using SequenceMatcher"""
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
   

    def _fuzzy_search_products(self, collection_name, query, store_id, top_k=6, min_similarity=0.3):
        """
        Fallback fuzzy search using MongoDB regex and string similarity

        Args:
            collection_name: MongoDB collection name
            query: Search query string
            store_id: Store ID to filter products
            top_k: Number of top results to return
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            List of matched products with similarity scores
        """
        if self.metadata_db is None:
            return []

        try:
            collection = self.metadata_db[collection_name]

            # Prepare store IDs in different formats
            store_ids = [store_id, str(store_id)]
            try:
                store_ids.append(int(store_id))
            except (ValueError, TypeError):
                pass

            # First, try regex search for broader matches
            search_regex = {'$regex': re.escape(query), '$options': 'i'}
            regex_query = {
                'store_id': {'$in': store_ids},
                '$or': [
                    {'name': search_regex},
                    {'name_en': search_regex},
                    {'description': search_regex}
                ]
            }

            # Get products from regex search
            products = list(collection.find(regex_query).limit(50))

            # If regex doesn't find enough results, get more products for fuzzy matching
            if len(products) < top_k:
                additional_products = list(collection.find(
                    {'store_id': {'$in': store_ids}}
                ).limit(100))

                # Merge and deduplicate
                seen_ids = {str(p.get('_id')) for p in products}
                for p in additional_products:
                    if str(p.get('_id')) not in seen_ids:
                        products.append(p)

            # Calculate similarity scores for all products
            results = []
            for product in products:
                product_name = product.get('name', '')
                product_name_en = product.get('name_en', '')

                name_similarity = self._calculate_string_similarity(query, product_name)
                name_en_similarity = self._calculate_string_similarity(query, product_name_en) if product_name_en else 0

                similarity_score = max(name_similarity, name_en_similarity)

                # Only include if above minimum threshold
                if similarity_score >= min_similarity:
                    results.append({
                        'name': product_name,
                        'name_en': product_name_en,
                        'image': product.get('image', ''),
                        'sku': product.get('sku', ''),
                        'category': product.get('category', ''),
                        'unit': product.get('unit', ''),
                        'net_unit_value': product.get('net_unit_value', 1),
                        'price': product.get('price', 0),
                        'sys_price': product.get('sys_price', product.get('price', 0)),
                        'discountPercent': product.get('discountPercent', 0),
                        'url': product.get('url', ''),
                        'promotion': product.get('promotion', ''),
                        'similarity_score': similarity_score,
                        'search_method': 'fuzzy'
                    })

            # Sort by similarity score and price
            results.sort(key=lambda x: (-x['similarity_score'], x.get('price', float('inf'))))

            # Return top K results
            return results[:top_k]

        except Exception as e:
            print(f"⚠️  Fuzzy search error in {collection_name}: {str(e)}")
            return []
    
    def process_all_ingredients(self, basket_ingredients, basket_dishes):
        processed_ingredients = {}   
        
        # Category normalization mapping (lowercase with underscores -> proper format)
        NORMALIZED_CATEGORIES = {
            'alcoholic_beverages': 'Alcoholic Beverages',
            'beverages': 'Beverages',
            'cakes': 'Cakes',
            'candies': 'Candies',
            'cereals_&_grains': 'Cereals & Grains',
            'cold_cuts_sausages_&_ham': 'Cold Cuts: Sausages & Ham',
            'dried_fruits': 'Dried Fruits',
            'fresh_fruits': 'Fresh Fruits',
            'fresh_meat': 'Fresh Meat',
            'fruit_jam': 'Fruit Jam',
            'grains_&_staples': 'Grains & Staples',
            'grains_staples': 'Grains & Staples',  # Handle variant without &
            'ice_cream_&_cheese': 'Ice Cream & Cheese',
            'instant_foods': 'Instant Foods',
            'milk': 'Milk',
            'seafood_&_fish_balls': 'Seafood & Fish Balls',
            'seasonings': 'Seasonings',
            'snacks': 'Snacks',
            'vegetables': 'Vegetables',
            'yogurt': 'Yogurt'
        }
        
        # Process basket ingredients
        for ingredient in basket_ingredients:
            if isinstance(ingredient, dict) and ingredient.get('name'):
                name = ingredient['name'].strip()
                quantity = ingredient.get('quantity', 1)
                if not isinstance(quantity, (int, float)) or quantity <= 0:
                    quantity = 1
                
                # Normalize category
                category = ingredient.get('category', '')
                normalized_key = category.lower().replace(' ', '_').replace(':', '')
                standardized_category = NORMALIZED_CATEGORIES.get(normalized_key, category)
                
                processed_ingredients[name] = {
                    'name': name,
                    'category': standardized_category,
                    'vietnamese_name': ingredient.get('vietnamese_name', ''),
                    'unit': ingredient.get('unit', ''),
                    'total_quantity': quantity
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
                        
                        # Normalize category
                        category = dish_ingredient.get('category', '')
                        normalized_key = category.lower().replace(' ', '_').replace(':', '')
                        standardized_category = NORMALIZED_CATEGORIES.get(normalized_key, category)
                        
                        if name in processed_ingredients:
                            # Cộng dồn quantity nếu nguyên liệu đã tồn tại
                            processed_ingredients[name]['total_quantity'] += total_dish_quantity
                        else:
                            # Tạo mới nếu chưa tồn tại
                            processed_ingredients[name] = {
                                'name': name,
                                'category': standardized_category,
                                'vietnamese_name': dish_ingredient.get('vietnamese_name', ''),
                                'unit': ingredient_unit,
                                'total_quantity': total_dish_quantity
                            }
        
        return processed_ingredients
    
    def find_matched_products(self, metadata_db, candidate_stores, processed_ingredients):
        self.metadata_db = metadata_db
        # Category to collection name mapping
        CATEGORY_TO_COLLECTION = {
            'Alcoholic Beverages': 'alcoholic_beverages',
            'Beverages': 'beverages',
            'Cakes': 'cakes',
            'Candies': 'candies',
            'Cereals & Grains': 'cereals_&_grains',
            'Cold Cuts: Sausages & Ham': 'cold_cuts:_sausages_&_ham',
            'Dried Fruits': 'dried_fruits',
            'Fresh Fruits': 'fresh_fruits',
            'Fresh Meat': 'fresh_meat',
            'Fruit Jam': 'fruit_jam',
            'Grains & Staples': 'grains_&_staples',
            'Ice Cream & Cheese': 'ice_cream_&_cheese',
            'Instant Foods': 'instant_foods',
            'Milk': 'milk',
            'Seafood & Fish Balls': 'seafood_&_fish_balls',
            'Seasonings': 'seasonings',
            'Snacks': 'snacks',
            'Vegetables': 'vegetables',
            'Yogurt': 'yogurt'
        }

        store_calculations = []

        for store in candidate_stores:
            store_id = store.get('store_id')
            store_name = store.get('store_name', store.get('name', 'Unknown'))
            store_distance = store.get('distance_km', 0)
            store_chain = store.get('chain', '')
            store_address = store.get('store_location', store.get('address', ''))
            store_phone = store.get('phone', '')
            store_rating = store.get('totalScore', 0)
            store_reviews = store.get('reviewsCount', 0)

            if not store_id:
                continue

            total_cost = 0
            found_ingredients = 0
            missing_ingredients = []
            store_items = []

            for ingredient_name, ingredient_info in processed_ingredients.items():
                try:
                    category_display = ingredient_info.get('category', 'Vegetables')
                    collection_name = CATEGORY_TO_COLLECTION.get(category_display, 'vegetables')

                    ingredient_quantity_needed = ingredient_info.get('total_quantity', 1)
                    ingredient_unit = ingredient_info.get('unit', '')
                    vietnamese_name = ingredient_info.get('vietnamese_name', '')

                    search_query = vietnamese_name if vietnamese_name else ingredient_name

                    # Try FAISS search first
                    results = self.embedding_service.search(
                        collection_name=collection_name,
                        query=search_query,
                        store_id=store_id,
                        top_k=6, 
                        threshold=0.35, 
                        category=category_display 
                    )

                    # If FAISS returns no results or low-quality results, use fuzzy search as fallback
                    faiss_score = results[0].get('similarity_score', 0) if results else 0
                    if not results or faiss_score < 0.5:
                        print(f"🔍 Using fuzzy search fallback for '{ingredient_name}' (FAISS score: {faiss_score:.2f})")
                        fuzzy_results = self._fuzzy_search_products(
                            collection_name=collection_name,
                            query=search_query,
                            store_id=store_id,
                            top_k=6,
                            min_similarity=0.3
                        )

                        # Use fuzzy results if they're better or FAISS had no results
                        if fuzzy_results:
                            fuzzy_score = fuzzy_results[0].get('similarity_score', 0)
                            if not results:
                                print(f"   ✓ Fuzzy search found {len(fuzzy_results)} results (best: {fuzzy_score:.2f})")
                                results = fuzzy_results
                            elif fuzzy_score > faiss_score:
                                print(f"   ✓ Merging FAISS and fuzzy results (fuzzy better: {fuzzy_score:.2f} > {faiss_score:.2f})")
                                # Merge results, prioritizing better scores
                                combined = results + fuzzy_results
                                # Remove duplicates by SKU
                                seen_skus = set()
                                unique_results = []
                                for r in combined:
                                    sku = r.get('sku', '')
                                    if sku and sku not in seen_skus:
                                        seen_skus.add(sku)
                                        unique_results.append(r)
                                    elif not sku:
                                        unique_results.append(r)
                                results = sorted(unique_results, key=lambda x: (-x['similarity_score'], x.get('price', float('inf'))))[:6]
                            else:
                                print(f"   ⓘ Keeping FAISS results (FAISS: {faiss_score:.2f} >= fuzzy: {fuzzy_score:.2f})")
                        else:
                            print(f"   ✗ Fuzzy search found no results")

                    if results:
                        # Sort by similarity score and price
                        results.sort(key=lambda x: (-x['similarity_score'], x.get('price', float('inf'))))

                        best_product = results[0]

                        # Calculate quantity and cost (matching fuzzy search logic)
                        price_per_unit = best_product.get('price', 0)
                        net_unit_value = best_product.get('net_unit_value', 1)
                        product_unit = best_product.get('unit', '')

                        actual_quantity_needed = ingredient_quantity_needed / net_unit_value if net_unit_value > 0 else ingredient_quantity_needed
                        units_to_buy = max(1, round(actual_quantity_needed, 3))
                        item_cost = price_per_unit * units_to_buy

                        total_cost += item_cost
                        found_ingredients += 1

                        # Build alternatives list (top 5 after best match)
                        alternatives = []
                        for i, alt_product in enumerate(results[1:6]):
                            alt_price = alt_product.get('price', 0)
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
                                'match_score': alt_product.get('similarity_score', 0),
                                'matched_field': alt_product.get('name', ''),
                                'product_url': alt_product.get('url', ''),
                                'promotion': alt_product.get('promotion', ''),
                                'rank': i + 2
                            })

                        # Add matched product to store items
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
                            'match_score': best_product.get('similarity_score', 0),
                            'matched_field': best_product.get('name', ''),
                            'product_url': best_product.get('url', ''),
                            'promotion': best_product.get('promotion', ''),
                            'alternatives_count': len(alternatives),
                            'alternatives': alternatives,
                            'rank': 1
                        })
                    else:
                        # No match found
                        missing_ingredients.append(ingredient_name)

                        store_items.append({
                            'ingredient_name': ingredient_name,
                            'ingredient_vietnamese_name': ingredient_info.get('vietnamese_name', ''),
                            'ingredient_category': ingredient_info.get('category', ''),
                            'ingredient_unit': ingredient_unit,
                            'product_id': None,
                            'product_name': None,
                            'product_name_en': None,
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

                except Exception as e:
                    print(f"⚠️  Error processing {ingredient_name}: {str(e)}")
                    missing_ingredients.append(ingredient_name)

                    store_items.append({
                        'ingredient_name': ingredient_name,
                        'ingredient_vietnamese_name': ingredient_info.get('vietnamese_name', ''),
                        'ingredient_category': ingredient_info.get('category', ''),
                        'ingredient_unit': ingredient_info.get('unit', ''),
                        'available': False,
                        'match_score': 0.0,
                        'total_price': 0
                    })

            # Calculate availability percentage
            availability_percentage = (found_ingredients / len(processed_ingredients) * 100) if processed_ingredients else 0

            # Build store calculation result (matching fuzzy search format)
            store_calculations.append({
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
                'average_match_score': round(sum(item['match_score'] for item in store_items if item.get('available', False)) / max(found_ingredients, 1), 2)
            })

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