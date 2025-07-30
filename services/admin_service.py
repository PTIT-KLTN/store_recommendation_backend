from database.mongodb import MongoDBConnection
from bson import ObjectId
from flask_bcrypt import generate_password_hash
from models.admin import Admin
from transformers import pipeline
import torch    
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import unidecode

# ===== PERFORMANCE =====
torch.set_num_threads(4)

# ===== TRANSLATION SETUP =====
tokenizer_vi2en = AutoTokenizer.from_pretrained(
    "vinai/vinai-translate-vi2en-v2",
    use_fast=False,
    src_lang="vi_VN",
    tgt_lang="en_XX"
)
model_vi2en = AutoModelForSeq2SeqLM.from_pretrained("vinai/vinai-translate-vi2en-v2")

def translate_vi2en(vi_text: str) -> str:
    """Translate Vietnamese text to English"""
    try:
        inputs = tokenizer_vi2en(vi_text, return_tensors="pt")
        decoder_start_token_id = tokenizer_vi2en.lang_code_to_id["en_XX"]
        outputs = model_vi2en.generate(
            **inputs,
            decoder_start_token_id=decoder_start_token_id,
            num_beams=5,
            early_stopping=True
        )
        return tokenizer_vi2en.decode(outputs[0], skip_special_tokens=True)
    except Exception:
        return ""

# ======= CALL DB ========
db = MongoDBConnection.get_primary_db()
metadata_db = MongoDBConnection.get_metadata_db()

def get_admin_role(user_email):
    admin_data = db.admins.find_one({'email': user_email})
    if not admin_data:
        return None, "User not found"
    
    return admin_data.get('role', 'ADMIN'), None

def check_super_admin_exists():
    """Check if super admin already exists"""
    super_admin = db.admins.find_one({'role': 'SUPER_ADMIN'})
    return super_admin is not None

def get_admin_role_and_type(admin_email):
    """Get user role and check if super admin"""
    admin_data = db.admins.find_one({'email': admin_email})
    if not admin_data:
        return None, None, "User not found"
    
    role = admin_data.get('role', 'ADMIN')
    is_super_admin = role == 'SUPER_ADMIN'
    
    return role, is_super_admin, None

def create_admin_account(admin_data, is_super_admin=False):
    # Check if admin already exists
    existing_admin = db.admins.find_one({'email': admin_data['email']})
    if existing_admin:
        return None, "Admin with this email already exists"
    
    # Hash password
    hashed_password = generate_password_hash(admin_data['password'])

    # Create admin user with appropriate role
    role = 'SUPER_ADMIN' if is_super_admin else 'ADMIN'
    admin = Admin(
        email=admin_data['email'], 
        password=hashed_password, 
        fullname=admin_data['fullname'],
        role=role
    )
    admin_dict = admin.to_dict()
    admin_result = db.admins.insert_one(admin_dict)

    # Return admin info (without password)
    admin_info = {
        'id': str(admin_result.inserted_id),
        'email': admin_data['email'],
        'fullname': admin_data['fullname'],
        'role': role,
        'created_at': admin_dict['created_at'],
        'updated_at': admin_dict['updated_at'],
    }
    
    return admin_info, None

# Dish CRUD operations
def create_dish(dish_data):    

    vi_name = dish_data.get('vietnamese_name', '').strip()
    if vi_name:
        translated = translate_vi2en(vi_name)
        dish_data['dish'] = translated or unidecode.unidecode(vi_name).lower()

    result = db.dishes.insert_one(dish_data)
    dish_data['_id'] = str(result.inserted_id)
    
    return dish_data, None

def get_dish_by_id(dish_id):
    try:
        dish = db.dishes.find_one({'_id': ObjectId(dish_id)})
        if not dish:
            return None, "Dish not found"
        
        dish['_id'] = str(dish['_id'])
        return dish, None
    except Exception as e:
        return None, str(e)

def update_dish(dish_id, update_data):
    try:
        if 'vietnamese_name' in update_data:
            vi_name = update_data['vietnamese_name'].strip()
            translated = translate_vi2en(vi_name)
            update_data['dish'] = translated or unidecode.unidecode(vi_name).lower()

        result = db.dishes.update_one(
            {'_id': ObjectId(dish_id)},
            {'$set': update_data}
        )

        if result.matched_count == 0:
            return None, "Dish not found"

        updated_dish = db.dishes.find_one({'_id': ObjectId(dish_id)})
        updated_dish['_id'] = str(updated_dish['_id'])

        return updated_dish, None
    except Exception as e:
        return None, str(e)

def delete_dish(dish_id):
    try:
        result = db.dishes.delete_one({'_id': ObjectId(dish_id)})
        
        if result.deleted_count == 0:
            return None, "Dish not found"
        
        return {'message': 'Dish deleted successfully', 'dish_id': dish_id}, None
    except Exception as e:
        return None, str(e)

def get_all_dishes(page, size, search_query=None):
    skip = page * size
    
    query = {}
    if search_query:
        pattern_regex = {'$regex': search_query, '$options': 'i'}
        query = {
            '$or': [
                {'dish': pattern_regex},
                {'vietnamese_name': pattern_regex},
                {'category': pattern_regex}
            ]
        }
    
    dishes = list(
        db.dishes.find(query)
        .sort('created_at', -1)
        .skip(skip)
        .limit(size)
    )
    total = db.dishes.count_documents(query)
    
    for dish in dishes:
        dish['_id'] = str(dish['_id'])
    
    total_pages = (total + size - 1) // size if size > 0 else 0
    
    return {
        'dishes': dishes,
        'pagination': {
            'currentPage': page,
            'pageSize': size,
            'totalPages': total_pages,
            'totalElements': total,
            'hasNext': page < total_pages - 1,
            'hasPrevious': page > 0
        }
    }, None

# Ingredient CRUD operations
def create_ingredient(ingredient_data):
    try:
        vietnamese_name = ingredient_data.get('name', '').strip()
        ingredient_data['name_en'] = translate_vi2en(vietnamese_name) if vietnamese_name else ''

        result = db.ingredients.insert_one(ingredient_data)
        ingredient_data['_id'] = str(result.inserted_id)
        return ingredient_data, None
    except Exception as e:
        return None, str(e)
    
def get_ingredient_by_id(ingredient_id):
    try:
        ingredient = db.ingredients.find_one({'_id': ObjectId(ingredient_id)})
        if not ingredient:
            return None, "Ingredient not found"
        
        ingredient['_id'] = str(ingredient['_id'])
        return ingredient, None
    except Exception as e:
        return None, str(e)

def update_ingredient(ingredient_id, update_data):
    try:
        if 'name' in update_data:
            vi_name = update_data['name'].strip()
            update_data['name_en'] = translate_vi2en(vi_name)

        result = db.ingredients.update_one(
            {'_id': ObjectId(ingredient_id)},
            {'$set': update_data}
        )

        if result.matched_count == 0:
            return None, "Ingredient not found"

        updated_ingredient = db.ingredients.find_one({'_id': ObjectId(ingredient_id)})
        updated_ingredient['_id'] = str(updated_ingredient['_id'])
        return updated_ingredient, None

    except Exception as e:
        return None, str(e)


def delete_ingredient(ingredient_id):
    try:
        ingr = db.ingredients.find_one({'_id': ObjectId(ingredient_id)})
        if not ingr:
            return None, "Ingredient not found"

        name = ingr.get('name', '').strip()
        print(f"name: {name}")
        # Kiểm tra dùng trong dish
        if db.dishes.find_one({'ingredients.vietnamese_name': name}):
            return None, "Ingredient is used in dishes and cannot be deleted"
        
        print(db.dishes.find_one({'ingredients.vietnamese_name': name}))

        result = db.ingredients.delete_one({'_id': ingr['_id']})
        return (
            {'message': 'Ingredient deleted successfully', 'ingredient_id': ingredient_id},
            None
        ) if result.deleted_count else (None, "Ingredient not found")
    except Exception as e:
        return None, str(e)


def get_all_ingredients(page, size, search_query=None, category=None):
    skip = page * size

    # 1. Xây dựng điều kiện tìm kiếm chung
    query_parts = []
    if search_query:
        pattern = {'$regex': search_query, '$options': 'i'}
        query_parts.append({
            '$or': [
                {'name': pattern},
                {'name_en': pattern},
                {'vietnamese_name': pattern},
                {'category': pattern},       # chỉ để search linh hoạt
            ]
        })

    # 2. Thêm điều kiện lọc category chính xác (nếu có)
    if category:
        cat_pattern = {'$regex': f'^{category}$', '$options': 'i'}
        query_parts.append({'category': cat_pattern})

    # 3. Kết hợp các điều kiện
    if not query_parts:
        query = {}
    elif len(query_parts) == 1:
        query = query_parts[0]
    else:
        query = {'$and': query_parts}

    # 4. Truy vấn và phân trang
    ingredients = list(
        db.ingredients
          .find(query)
          .sort('$natural', -1)
          .skip(skip)
          .limit(size)
    )
    total = db.ingredients.count_documents(query)

    # 5. Chuyển ObjectId sang string
    for ing in ingredients:
        ing['_id'] = str(ing['_id'])

    total_pages = (total + size - 1) // size if size > 0 else 0

    return {
        'ingredients': ingredients,
        'pagination': {
            'currentPage':   page,
            'pageSize':      size,
            'totalPages':    total_pages,
            'totalElements': total,
            'hasNext':       page < total_pages - 1,
            'hasPrevious':   page > 0
        }
    }, None



def get_all_categories():
    """
    Lấy danh sách tất cả categories từ metadata database,
    chỉ lấy trường 'name' và trả về list các tên.
    """
    try:
        cursor = metadata_db.categories.find({}, {'_id': 1, 'name': 1})
        names = [doc['name'] for doc in cursor]
        return names, None
    except Exception as e:
        return None, str(e)