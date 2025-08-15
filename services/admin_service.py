from datetime import datetime
from database.mongodb import MongoDBConnection
from bson import ObjectId
from flask_bcrypt import generate_password_hash
from models.admin import Admin
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

def get_admin_role(email):
    admin_data = db.admins.find_one({'email': email})
    if not admin_data:
        return None, "Không tìm thấy tài khoản admin"
    
    return admin_data.get('role', 'ADMIN'), None

def check_super_admin_exists():
    """Check if super admin already exists"""
    super_admin = db.admins.find_one({'role': 'SUPER_ADMIN'})
    return super_admin is not None

def get_admin_role_and_type(email):
    """Get user role and check if super admin"""
    admin_data = db.admins.find_one({'email': email})
    if not admin_data:
        return None, None, "Không tìm thấy tài khoản admin"
    
    role = admin_data.get('role', 'ADMIN')
    is_super_admin = role == 'SUPER_ADMIN'
    
    return role, is_super_admin, None

def create_admin_account(admin_data, is_super_admin=False):
    existing_email = db.admins.find_one({'email': admin_data['email']})
    if existing_email:
        return None, "Email đã tồn tại"
    
    if not is_super_admin:
        today_str = datetime.utcnow().strftime('%Y%m%d')
        admin_data['password'] = f"{admin_data['fullname']}@{today_str}"
    
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
            return None, "Không tìm thấy món ăn"
        
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
            return None, "Không tìm thấy món ăn"

        # Lấy bản ghi dish mới
        updated_dish = db.dishes.find_one({'_id': ObjectId(dish_id)})
        updated_dish['_id'] = str(updated_dish['_id'])

        # Cập nhật trong baskets
        db.baskets.update_many(
            { 'dishes.id': dish_id },
            { '$set': { f'dishes.$.{k}': v for k, v in update_data.items() } }
        )
        # Cập nhật trong saved_baskets của user
        db.users.update_many(
            { 'saved_baskets.dishes.id': dish_id },
            {
                '$set': {
                    'saved_baskets.$[b].dishes.$[d].' + k: v
                    for k, v in update_data.items()
                }
            },
            array_filters=[
                { 'b.dishes.id': dish_id },
                { 'd.id': dish_id }
            ]
        )

        return updated_dish, None
    except Exception as e:
        return None, str(e)

def delete_dish(dish_id):
    try:
        if db.baskets.find_one({'dishes.id': dish_id}):
            return None, "Món ăn này đang có trong giỏ hàng của user, không thể xóa"

        result = db.dishes.delete_one({'_id': ObjectId(dish_id)})
        
        if result.deleted_count == 0:
            return None, "Không tìm thấy món ăn"
        
        return {'message': 'Món ăn được xóa thành công', 'dish_id': dish_id}, None
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
        db.dishes
        .find(query)
        .sort([('$natural', -1)])
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

        # Lấy bản ghi ingredient
        updated_ingredient = db.ingredients.find_one({'_id': ObjectId(ingredient_id)})
        updated_ingredient['_id'] = str(updated_ingredient['_id'])

        # Nếu ingredients tồn tại trong baskets, cập nhật luôn
        db.baskets.update_many(
            { 'ingredients.id': ingredient_id },
            { '$set': { f'ingredients.$.{k}': v for k, v in update_data.items() } }
        )

        # Nếu ingredients tồn tại trong saved_baskets của user
        db.users.update_many(
            { 'saved_baskets.ingredients.id': ingredient_id },
            {
                '$set': {
                    'saved_baskets.$[b].ingredients.$[i].' + k: v
                    for k, v in update_data.items()
                }
            },
            array_filters=[
                { 'b.ingredients.id': ingredient_id },
                { 'i.id': ingredient_id }
            ]
        )

        return updated_ingredient, None

    except Exception as e:
        return None, str(e)


def delete_ingredient(ingredient_id):
    try:
        if db.baskets.find_one({'ingredients.id': ingredient_id}):
            return None, "Nguyên liệu này đang có trong giỏ hàng của user, không thể xóa"

        ingr = db.ingredients.find_one({'_id': ObjectId(ingredient_id)})
        if not ingr:
            return None, "Không tìm thấy nguyên liệu"

        name = ingr.get('name', '').strip()
        if db.dishes.find_one({'ingredients.vietnamese_name': name}):
            return None, "Nguyên liệu này đang được sử dụng trong món ăn, không thể xóa"

        result = db.ingredients.delete_one({'_id': ingr['_id']})
        return (
            {'message': 'Nguyên liệu đã được xóa thành công', 'ingredient_id': ingredient_id},
            None
        ) if result.deleted_count else (None, "Không tìm thấy nguyên liệu")
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
                {'category': pattern},
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
    try:
        cursor = metadata_db.categories.find({}, {'_id': 1, 'name': 1})
        names = [doc['name'] for doc in cursor]
        return names, None
    except Exception as e:
        return None, str(e)

# =========== CRUD for account admin =============
# Lấy danh sách admin thường (không bao gồm super_admin)
def get_all_admins(page=0, size=20, search=None):
    skip = page * size
    query = {'role': 'ADMIN'}
    if search:
        regex = {'$regex': search, '$options': 'i'}
        query['$or'] = [{'email': regex}, {'fullname': regex}]
    
    admins = list(
        db.admins.find(query)
        .sort('created_at', -1)
        .skip(skip)
        .limit(size)
    )
    total = db.admins.count_documents(query)
    total_pages = (total + size - 1) // size if size > 0 else 0

    # Chuyển sang dạng public_dict (ẩn mật khẩu)
    from models.admin import Admin
    for i, a in enumerate(admins):
        admins[i] = Admin.from_dict(a).to_public_dict()

    return {
        'admins': admins,
        'pagination': {
            'currentPage': page,
            'pageSize': size,
            'totalPages': total_pages,
            'totalElements': total,
            'hasNext': page < total_pages - 1,
            'hasPrevious': page > 0
        }
    }, None


def update_admin_account(admin_id, update_data):
    try:
        allowed_fields = ['email', 'fullname']
        set_data = {k: v for k, v in update_data.items() if k in allowed_fields}
        if not set_data:
            return None, "Không có trường nào hợp lệ để cập nhật"
        
        set_data['updated_at'] = datetime.utcnow()
        
        result = db.admins.update_one(
            {'_id': ObjectId(admin_id)},
            {'$set': set_data}
        )
        if result.matched_count == 0:
            return None, "Không tìm thấy tài khoản admin"
        
        admin = db.admins.find_one({'_id': ObjectId(admin_id)})
        return {
            'id': str(admin['_id']),
            'email': admin['email'],
            'fullname': admin['fullname'],
            'role': admin.get('role'),
            'is_enabled': admin.get('is_enabled', True),
            'created_at': admin.get('created_at'),
            'updated_at': admin.get('updated_at')
        }, None

    except Exception as e:
        return None, str(e)


# Bật/tắt tài khoản admin
def toggle_admin_status(admin_id, enable: bool):
    result = db.admins.update_one(
        {'_id': ObjectId(admin_id)},
        {'$set': {'is_enabled': enable, 'updated_at': datetime.utcnow()}}
    )
    if result.matched_count == 0:
        return None, "Admin not found"

    updated = db.admins.find_one({'_id': ObjectId(admin_id)})
    public = Admin.from_dict(updated).to_public_dict()
    return public, None


