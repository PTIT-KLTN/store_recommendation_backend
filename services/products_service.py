from database.mongodb import MongoDBConnection
from bson import ObjectId
import re

metadata_db = MongoDBConnection.get_metadata_db()

# Category to collection mapping
CATEGORY_COLLECTIONS = {
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
    'Seafood & Fish Balls': 'seafood_&_fish_balls',
    'Seasonings': 'seasonings',
    'Snacks': 'snacks',
    'Vegetables': 'vegetables',
    'Yogurt': 'yogurt'
}

def get_store_products_data(store_id, page=0, size=50, category=None, search=None, min_price=None, max_price=None):
    """Lấy tất cả sản phẩm của store từ các collection categories"""
    try:
        store_ids = [store_id, str(store_id)]
        try:
            store_ids.append(int(store_id))
        except ValueError:
            pass

        skip = page * size
        all_products = []
        
        # Determine which collections to search
        collections_to_search = CATEGORY_COLLECTIONS.copy()
        if category:
            # Filter by specific category
            category_key = next((k for k in CATEGORY_COLLECTIONS.keys() 
                               if k.lower() == category.lower()), None)
            if category_key:
                collections_to_search = {category_key: CATEGORY_COLLECTIONS[category_key]}
            else:
                return {'products': [], 'total': 0, 'message': 'Category not found'}, None
        
        # Search in each collection
        for category_name, collection_name in collections_to_search.items():
            try:
                collection = metadata_db[collection_name]
                
                # Build query
                query = {'store_id': {'$in': store_ids}}
                
                # Add search filter
                if search:
                    search_regex = {'$regex': re.escape(search), '$options': 'i'}
                    query['$or'] = [
                        {'name': search_regex},
                        {'description': search_regex}
                    ]
                
                # Add price filter
                if min_price is not None or max_price is not None:
                    price_query = {}
                    if min_price is not None:
                        price_query['$gte'] = min_price
                    if max_price is not None:
                        price_query['$lte'] = max_price
                    query['price'] = price_query
                
                # Get products from this collection
                products = list(collection.find(query))
                
                # Add category info to each product
                for product in products:
                    product['category'] = category_name
                    product['_id'] = str(product['_id'])
                    # Ensure price is numeric
                    if 'price' in product:
                        try:
                            product['price'] = float(product['price'])
                        except (ValueError, TypeError):
                            product['price'] = 0.0
                
                all_products.extend(products)
                
            except Exception as e:
                print(f"Error searching in {collection_name}: {e}")
                continue
        
        # Sort by category then by name
        all_products.sort(key=lambda x: (x.get('category', ''), x.get('name', '')))
        
        # Apply pagination
        total = len(all_products)
        paginated_products = all_products[skip:skip + size]
        
        # Check if store exists
        if total == 0:
            store_exists = metadata_db.stores.find_one({'store_id': {'$in': store_ids}})
            if not store_exists:
                return None, "Store not found"
        
        return {
            'products': paginated_products,
            'pagination': {
                'current_page': page,
                'page_size': size,
                'total_pages': (total + size - 1) // size if size > 0 else 0,
                'total_elements': total,
                'has_next': skip + size < total,
                'has_previous': page > 0
            },
            'filters': {
                'store_id': store_id,
                'category': category,
                'search': search,
                'min_price': min_price,
                'max_price': max_price
            }
        }, None
        
    except Exception as e:
        return None, str(e)

def get_store_categories_data(store_id):
    """Lấy danh sách categories có sản phẩm trong store"""
    try:
        store_ids = [store_id, str(store_id)]
        try:
            store_ids.append(int(store_id))
        except ValueError:
            pass
            
        categories_with_count = []
        
        for category_name, collection_name in CATEGORY_COLLECTIONS.items():
            try:
                collection = metadata_db[collection_name]
                count = collection.count_documents({'store_id': {'$in': store_ids}})
                
                if count > 0:
                    categories_with_count.append({
                        'category': category_name,
                        'collection': collection_name,
                        'product_count': count
                    })
                    
            except Exception as e:
                print(f"Error counting in {collection_name}: {e}")
                continue
        
        # Sort by product count descending
        categories_with_count.sort(key=lambda x: x['product_count'], reverse=True)
        
        total_categories = len(categories_with_count)
        total_products = sum(cat['product_count'] for cat in categories_with_count)
        
        return {
            'categories': categories_with_count,
            'total_categories': total_categories,
            'total_products': total_products,
            'store_id': store_id
        }, None
        
    except Exception as e:
        return None, str(e)

def get_store_stats_data(store_id):
    """Lấy thống kê chi tiết sản phẩm của store"""
    try:
        # Tạo danh sách các variant của store_id để tìm kiếm
        store_ids = [str(store_id)]
        
        # Thêm variant số nguyên nếu có thể
        try:
            numeric_store_id = int(str(store_id))
            store_ids.append(numeric_store_id)
        except ValueError:
            pass
        
        # Thêm variant float nếu chuỗi chứa số thập phân
        try:
            float_store_id = float(str(store_id))
            if float_store_id.is_integer():
                store_ids.append(int(float_store_id))
            else:
                store_ids.append(float_store_id)
        except ValueError:
            pass
        
        # Loại bỏ duplicate và giữ thứ tự
        store_ids = list(dict.fromkeys(store_ids))
                    
        # Get store info
        store_info = metadata_db.stores.find_one({'store_id': {'$in': store_ids}})
        print(store_info)
        if not store_info:
            return None, "Không tìm thấy cửa hàng"
        
        stats = {
            'store_info': {
                'store_id': store_info.get('store_id'),
                'store_name': store_info.get('store_name'),
                'chain': store_info.get('chain'),
                'location': store_info.get('store_location')
            },
            'categories': [],
            'price_range': {},
            'total_products': 0
        }
        
        all_prices = []
        store_id = store_info.get('store_id')
        for category_name, collection_name in CATEGORY_COLLECTIONS.items():
            try:
                collection = metadata_db[collection_name]
                products = list(collection.find({'store_id': {'$in': store_ids}}))
                print("products",products)
                if products:
                    # Extract prices for this category
                    category_prices = []
                    for product in products:
                        try:
                            price = float(product.get('price', 0))
                            if price > 0:
                                category_prices.append(price)
                                all_prices.append(price)
                        except (ValueError, TypeError):
                            continue
                    print(category_name, len(products))
                    stats['categories'].append({
                        'category': category_name,
                        'product_count': len(products),     
                        'price_stats': {
                            'min_price': min(category_prices) if category_prices else 0,
                            'max_price': max(category_prices) if category_prices else 0,
                            'avg_price': round(sum(category_prices) / len(category_prices), 2) if category_prices else 0
                        }
                    })
                    
            except Exception as e:
                print(f"Error processing {collection_name}: {e}")
                continue
        
        # Overall price statistics
        if all_prices:
            stats['price_range'] = {
                'min_price': min(all_prices),
                'max_price': max(all_prices),
                'avg_price': round(sum(all_prices) / len(all_prices), 2)
            }
        
        stats['total_products'] = sum(cat['product_count'] for cat in stats['categories'])
        stats['total_categories'] = len(stats['categories'])
        
        return stats, None
        
    except Exception as e:
        return None, str(e)

    